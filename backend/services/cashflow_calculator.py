"""Single source of truth for weekly cashflow calculation.

Used by both /cashflow/weeks and /treasury/calendar to guarantee identical numbers.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from core.database import db
from services.fx import get_fx_rate_by_date

logger = logging.getLogger(__name__)


async def calcular_semanas_cashflow(company_id: str, num_weeks: int = 16) -> List[Dict]:
    """
    Calcula semanas de cashflow con ingresos/egresos reales (CFDIs) y proyecciones.

    Retorna dicts compatibles con el modelo CashFlowWeek más campos extra
    para el calendario de tesorería (ingresos_detalle, egresos_detalle, label, etc.).
    Los campos extra son ignorados por el response_model de FastAPI.
    """
    # ── Semanas desde DB (o generadas si no existen) ──
    weeks = await db.cashflow_weeks.find(
        {'company_id': company_id}, {'_id': 0}
    ).sort('fecha_inicio', 1).to_list(num_weeks)

    if not weeks:
        today = datetime.now(timezone.utc)
        start_of_week = today - timedelta(days=today.weekday())
        weeks = []
        for i in range(num_weeks):
            week_start = start_of_week + timedelta(weeks=i)
            week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
            weeks.append({
                'id': str(uuid.uuid4()),
                'company_id': company_id,
                'año': week_start.year,
                'numero_semana': week_start.isocalendar()[1],
                'fecha_inicio': week_start,
                'fecha_fin': week_end,
                'total_ingresos_reales': 0,
                'total_egresos_reales': 0,
                'total_ingresos_proyectados': 0,
                'total_egresos_proyectados': 0,
                'saldo_inicial': 0,
                'saldo_final_real': 0,
                'saldo_final_proyectado': 0,
                'created_at': today,
            })

    # ── FX rates ──
    fx_rates = await db.fx_rates.find(
        {'company_id': company_id},
        {'_id': 0, 'moneda_origen': 1, 'moneda_destino': 1, 'tasa': 1}
    ).sort('fecha_vigencia', -1).to_list(100)

    fx_map: Dict[str, float] = {'MXN': 1.0}
    for rate in fx_rates:
        if rate.get('moneda_destino') == 'MXN':
            fx_map[rate['moneda_origen']] = rate['tasa']
        elif rate.get('moneda_origen') == 'MXN':
            fx_map[rate['moneda_destino']] = 1 / rate['tasa']
    fx_map.setdefault('USD', 17.50)
    fx_map.setdefault('EUR', 19.00)

    # ── Saldo inicial desde cuentas bancarias ──
    bank_accounts = await db.bank_accounts.find(
        {'company_id': company_id, 'activo': True}, {'_id': 0}
    ).to_list(100)

    saldo_inicial_total = 0.0
    for acc in bank_accounts:
        saldo = acc.get('saldo_inicial', 0)
        moneda = acc.get('moneda', 'MXN')
        fecha_saldo = acc.get('fecha_saldo')
        if fecha_saldo:
            if isinstance(fecha_saldo, str):
                fecha_saldo = datetime.fromisoformat(fecha_saldo.replace('Z', '+00:00'))
            tasa = await get_fx_rate_by_date(company_id, moneda, fecha_saldo)
        else:
            tasa = fx_map.get(moneda, 1.0)
        saldo_inicial_total += saldo * tasa

    # ── CFDIs (misma fuente que cashflow.py) ──
    cfdis = await db.cfdis.find(
        {'company_id': company_id},
        {'_id': 0, 'tipo_cfdi': 1, 'total': 1, 'fecha_emision': 1,
         'receptor_nombre': 1, 'emisor_nombre': 1, 'estado_conciliacion': 1}
    ).to_list(5000)

    # ── Proyecciones manuales ──
    proyecciones = await db.transactions.find(
        {'company_id': company_id, 'es_proyeccion': True}, {'_id': 0}
    ).to_list(500)

    def _parse(val) -> Optional[datetime]:
        if not val:
            return None
        if isinstance(val, datetime):
            return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        try:
            dt = datetime.fromisoformat(str(val).replace('Z', '+00:00'))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None

    running_balance = saldo_inicial_total
    result: List[Dict] = []

    for i, week in enumerate(weeks):
        for field in ('fecha_inicio', 'fecha_fin', 'created_at'):
            week[field] = _parse(week.get(field))

        week_start = week.get('fecha_inicio')
        week_end = week.get('fecha_fin')
        if not week_start or not week_end:
            continue

        ws = week_start.strftime('%Y-%m-%d')
        we = week_end.strftime('%Y-%m-%d')

        semana_cobros: List[Dict] = []
        semana_pagos: List[Dict] = []
        week_ingresos = 0.0
        week_egresos = 0.0

        for cfdi in cfdis:
            cfdi_date = _parse(cfdi.get('fecha_emision'))
            if not cfdi_date or not (week_start <= cfdi_date <= week_end):
                continue
            monto = float(cfdi.get('total', 0) or 0)
            if monto <= 0:
                continue
            nombre = cfdi.get('receptor_nombre') or cfdi.get('emisor_nombre') or 'Sin nombre'
            item: Dict = {'concepto': nombre, 'monto': monto, 'estado': cfdi.get('estado_conciliacion', '')}
            if cfdi.get('tipo_cfdi') == 'ingreso':
                week_ingresos += monto
                semana_cobros.append(item)
            else:
                week_egresos += monto
                semana_pagos.append(item)

        semana_proy_ing = [
            t for t in proyecciones
            if t.get('tipo_transaccion') == 'ingreso'
            and ws <= (t.get('fecha_transaccion', '') or '')[:10] <= we
        ]
        semana_proy_egr = [
            t for t in proyecciones
            if t.get('tipo_transaccion') == 'egreso'
            and ws <= (t.get('fecha_transaccion', '') or '')[:10] <= we
        ]

        total_proy_ing = sum(float(t.get('monto', 0) or 0) for t in semana_proy_ing)
        total_proy_egr = sum(float(t.get('monto', 0) or 0) for t in semana_proy_egr)

        total_ingresos = week_ingresos + total_proy_ing
        total_egresos = week_egresos + total_proy_egr

        # ── CashFlowWeek model-compatible fields ──
        week['total_ingresos_reales'] = week_ingresos
        week['total_egresos_reales'] = week_egresos
        week['total_ingresos_proyectados'] = total_proy_ing
        week['total_egresos_proyectados'] = total_proy_egr
        week['saldo_inicial'] = running_balance
        week['saldo_final_real'] = running_balance + week_ingresos - week_egresos
        week['saldo_final_proyectado'] = running_balance + total_ingresos - total_egresos
        running_balance = week['saldo_final_real']

        # ── Treasury calendar extras (ignored by CashFlowWeek response_model) ──
        week['label'] = f'S{i + 1}'
        week['date_range'] = f'{week_start.strftime("%d/%m")} - {week_end.strftime("%d/%m")}'
        week['week_start'] = ws
        week['ingresos_detalle'] = semana_cobros
        week['egresos_detalle'] = semana_pagos
        week['proyecciones_ingreso'] = [
            {'concepto': t.get('concepto', ''), 'monto': float(t.get('monto', 0) or 0)}
            for t in semana_proy_ing
        ]
        week['proyecciones_egreso'] = [
            {'concepto': t.get('concepto', ''), 'monto': float(t.get('monto', 0) or 0)}
            for t in semana_proy_egr
        ]
        week['total_ingresos'] = total_ingresos
        week['total_egresos'] = total_egresos
        week['flujo_neto'] = total_ingresos - total_egresos

        result.append(week)

    return result
