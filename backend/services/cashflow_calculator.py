"""Single source of truth for weekly cashflow calculation.

Used by both /cashflow/weeks and /treasury/calendar to guarantee identical numbers.
"""
import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from core.database import db
from services.fx import get_fx_rate_by_date

logger = logging.getLogger(__name__)


async def calcular_semanas_cashflow(company_id: str, num_weeks: int = 52) -> List[Dict]:
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

    if len(weeks) < num_weeks:
        if weeks:
            ultima = weeks[-1]
            fecha_raw = ultima.get('fecha_fin') or ultima.get('fecha_inicio')
            if isinstance(fecha_raw, str):
                ultima_fecha = date.fromisoformat(fecha_raw[:10])
            elif hasattr(fecha_raw, 'date'):
                ultima_fecha = fecha_raw.date()
            else:
                ultima_fecha = date.today()
            numero_inicial = int(ultima.get('numero_semana', len(weeks))) + 1
            next_start = ultima_fecha + timedelta(days=1)
        else:
            today_d = date.today()
            next_start = today_d - timedelta(days=today_d.weekday())
            numero_inicial = 1

        for i in range(num_weeks - len(weeks)):
            week_start = next_start + timedelta(weeks=i)
            week_end = week_start + timedelta(days=6)
            weeks.append({
                'id': str(uuid.uuid4()),
                'company_id': company_id,
                'numero_semana': numero_inicial + i,
                'fecha_inicio': week_start.isoformat(),
                'fecha_fin': week_end.isoformat(),
                'saldo_inicial': 0,
                'es_generada': True,
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

    # ── Fuente 1: CFDIs ──
    cfdis = await db.cfdis.find(
        {'company_id': company_id},
        {'_id': 0, 'tipo_cfdi': 1, 'total': 1, 'fecha_emision': 1,
         'receptor_nombre': 1, 'emisor_nombre': 1, 'estado_conciliacion': 1}
    ).to_list(5000)

    # ── Proyecciones manuales ──
    proyecciones = await db.transactions.find(
        {'company_id': company_id, 'es_proyeccion': True}, {'_id': 0}
    ).to_list(500)

    # ── Fuente 3: Transacciones reales (banco, CSV, manual, ERP sync) ──
    txns_reales = await db.transactions.find(
        {'company_id': company_id, 'es_real': True},
        {'_id': 0, 'id': 1, 'concepto': 1, 'monto': 1,
         'fecha_transaccion': 1, 'tipo_transaccion': 1, 'categoria': 1}
    ).to_list(2000)

    def _to_date_str(val) -> str:
        if not val:
            return ''
        if isinstance(val, datetime):
            return val.strftime('%Y-%m-%d')
        if isinstance(val, date):
            return val.strftime('%Y-%m-%d')
        m = re.search(r'(\d{4}-\d{2}-\d{2})', str(val))
        return m.group(1) if m else ''

    # ── Normalizar fechas de semanas a YYYY-MM-DD string ──
    for week in weeks:
        week['_fi'] = week['fecha_inicio'] = _to_date_str(week.get('fecha_inicio'))
        week['_ff'] = week['fecha_fin'] = _to_date_str(week.get('fecha_fin'))

    # ── Fuente 1: distribuir CFDIs en semanas ──
    # Índice por id de semana para match por cashflow_week_id (O(1))
    weeks_by_id = {w.get('id', ''): w for w in weeks if w.get('id')}

    for cfdi in cfdis:
        monto = float(cfdi.get('total', 0) or 0)
        if monto <= 0:
            continue
        tipo = str(cfdi.get('tipo_cfdi', '') or '').strip().upper()
        nombre = (cfdi.get('receptor_nombre') or cfdi.get('emisor_nombre') or
                  cfdi.get('concepto') or 'Sin nombre')
        fecha_str = _to_date_str(cfdi.get('fecha_emision') or cfdi.get('fecha'))

        # Buscar semana: primero por cashflow_week_id, fallback por fecha_emision
        cfdi_week_id = cfdi.get('cashflow_week_id', '')
        matched_week = weeks_by_id.get(cfdi_week_id) if cfdi_week_id else None
        if matched_week is None and fecha_str:
            for week in weeks:
                if week['_fi'] <= fecha_str <= week['_ff']:
                    matched_week = week
                    break

        if matched_week is None:
            continue

        item = {
            'id': cfdi.get('id', ''),
            'concepto': nombre,
            'monto': monto,
            'fecha': fecha_str,
            'categoria': cfdi.get('categoria', 'otros'),
            'fuente': 'cfdis',
        }
        if tipo.upper() in ('I', 'INGRESO', 'INCOME', 'ENTRADA'):
            matched_week.setdefault('ingresos_detalle', []).append(item)
            matched_week['total_ingresos'] = matched_week.get('total_ingresos', 0) + monto
        elif tipo.upper() in ('E', 'EGRESO', 'EXPENSE', 'SALIDA', 'GASTO'):
            matched_week.setdefault('egresos_detalle', []).append(item)
            matched_week['total_egresos'] = matched_week.get('total_egresos', 0) + monto
        matched_week['flujo_neto'] = matched_week.get('total_ingresos', 0) - matched_week.get('total_egresos', 0)

    running_balance = saldo_inicial_total
    result: List[Dict] = []

    for i, week in enumerate(weeks):
        ws = week.get('fecha_inicio', '')
        we = week.get('fecha_fin', '')
        if not ws or not we:
            continue

        semana_cobros = week.get('ingresos_detalle', [])
        semana_pagos = week.get('egresos_detalle', [])
        week_ingresos = sum(item.get('monto', 0) for item in semana_cobros)
        week_egresos = sum(item.get('monto', 0) for item in semana_pagos)

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
        week['label'] = f"S{week.get('numero_semana', i + 1)}"
        week['date_range'] = f'{ws[8:10]}/{ws[5:7]} - {we[8:10]}/{we[5:7]}'
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

    def _set_tops(week: Dict) -> None:
        ing = week.get('ingresos_detalle', [])
        egr = week.get('egresos_detalle', [])
        week['top_ingresos'] = sorted(ing, key=lambda x: x.get('monto', 0), reverse=True)[:5]
        week['top_egresos'] = sorted(egr, key=lambda x: x.get('monto', 0), reverse=True)[:5]

    # ── Segundo: tops de CFDIs (antes de agregar fuentes complementarias) ──
    for week in result:
        _set_tops(week)

    # ── Tercero: CxC/CxP del cache — SOLO semanas sin CFDIs (total == 0) ──
    today = date.today()
    for cache_key, tipo_movimiento in [
        (f"cxc_{company_id}_latest", "ingreso"),
        (f"cxp_{company_id}_latest", "egreso"),
    ]:
        cache_doc = await db.contalink_cache.find_one({'key': cache_key})
        if not cache_doc:
            continue
        raw = cache_doc.get('data', {})
        items = (
            next((v for v in raw.values() if isinstance(v, list)), [])
            if isinstance(raw, dict)
            else (raw if isinstance(raw, list) else [])
        )
        for item in items:
            monto = float(item.get('saldo_pendiente') or item.get('saldo') or item.get('total') or 0)
            if monto <= 0:
                continue
            nombre = item.get('nombre') or item.get('razon_social') or 'Sin nombre'
            dias_vencido = int(item.get('dias_vencido', 0) or 0)
            if dias_vencido > 60:
                fecha_estimada = today + timedelta(days=30)
            elif dias_vencido > 30:
                fecha_estimada = today + timedelta(days=14)
            elif dias_vencido > 0:
                fecha_estimada = today + timedelta(days=7)
            else:
                fecha_estimada = today + timedelta(days=14)

            for week in weeks:
                fi = str(week.get('fecha_inicio', ''))[:10]
                ff = str(week.get('fecha_fin', ''))[:10]
                if fi <= fecha_estimada.isoformat() <= ff:
                    if week.get('total_ingresos', 0) == 0 and week.get('total_egresos', 0) == 0:
                        item_norm = {
                            'id': f"cache_{nombre}_{fecha_estimada}",
                            'concepto': nombre,
                            'monto': monto,
                            'fecha': fecha_estimada.isoformat(),
                            'categoria': 'cobranza_programada' if tipo_movimiento == 'ingreso' else 'pagos_programados',
                            'fuente': 'contalink_cache',
                            'dias_vencido': dias_vencido,
                        }
                        if tipo_movimiento == 'ingreso':
                            week.setdefault('ingresos_detalle', []).append(item_norm)
                            week['total_ingresos'] = week.get('total_ingresos', 0) + monto
                        else:
                            week.setdefault('egresos_detalle', []).append(item_norm)
                            week['total_egresos'] = week.get('total_egresos', 0) + monto
                        week['flujo_neto'] = week.get('total_ingresos', 0) - week.get('total_egresos', 0)
                    break

    # ── Cuarto: transacciones reales — SOLO semanas sin CFDIs (total == 0) ──
    for txn in txns_reales:
        fecha_raw = txn.get('fecha_transaccion', '')
        if not fecha_raw:
            continue
        fecha_str = str(fecha_raw)[:10]
        monto = float(txn.get('monto', 0) or 0)
        if monto <= 0:
            continue
        for week in weeks:
            fi = str(week.get('fecha_inicio', ''))[:10]
            ff = str(week.get('fecha_fin', ''))[:10]
            if fi <= fecha_str <= ff:
                if week.get('total_ingresos', 0) == 0 and week.get('total_egresos', 0) == 0:
                    item_norm = {
                        'id': txn.get('id', ''),
                        'concepto': txn.get('concepto', 'Sin nombre'),
                        'monto': monto,
                        'fecha': fecha_str,
                        'categoria': txn.get('categoria', 'otros'),
                        'fuente': 'transactions',
                    }
                    tipo = txn.get('tipo_transaccion', '')
                    if tipo == 'ingreso':
                        week.setdefault('ingresos_detalle', []).append(item_norm)
                        week['total_ingresos'] = week.get('total_ingresos', 0) + monto
                    else:
                        week.setdefault('egresos_detalle', []).append(item_norm)
                        week['total_egresos'] = week.get('total_egresos', 0) + monto
                    week['flujo_neto'] = week.get('total_ingresos', 0) - week.get('total_egresos', 0)
                break

    # ── Tops finales: recalcular para semanas llenadas por Fuente 2/3 ──
    for week in result:
        _set_tops(week)

    return result
