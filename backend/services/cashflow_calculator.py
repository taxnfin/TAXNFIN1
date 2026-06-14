"""
Servicio único de cálculo de semanas de cashflow.
Fuente de verdad: db.cashflow_weeks (estructura) + db.cfdis (totales por fecha_emision).
"""
import re
import uuid as _uuid
import logging
from datetime import date, timedelta
from typing import List, Dict

from core.database import db as _db_default

logger = logging.getLogger(__name__)


def _parse_date(val) -> str:
    """Extrae YYYY-MM-DD de cualquier formato."""
    if not val:
        return ''
    m = re.search(r'(\d{4}-\d{2}-\d{2})', str(val))
    return m.group(1) if m else ''


async def calcular_semanas_cashflow(company_id: str, num_weeks: int = 52, db=None) -> List[Dict]:
    if db is None:
        db = _db_default

    # ── 1. Leer semanas de DB ──────────────────────────────────────
    weeks_raw = await db.cashflow_weeks.find(
        {'company_id': company_id}, {'_id': 0}
    ).sort('numero_semana', 1).to_list(200)

    # ── 2. Leer TODOS los CFDIs una sola vez ──────────────────────
    cfdis = await db.cfdis.find(
        {'company_id': company_id},
        {'_id': 0, 'tipo_cfdi': 1, 'total': 1, 'fecha_emision': 1,
         'receptor_nombre': 1, 'emisor_nombre': 1, 'concepto': 1, 'categoria': 1, 'id': 1}
    ).to_list(10000)

    # ── 3. Pre-procesar CFDIs ──────────────────────────────────────
    processed_cfdis = []
    for c in cfdis:
        fecha = _parse_date(c.get('fecha_emision') or c.get('fecha'))
        if not fecha:
            continue
        monto = float(c.get('total', 0) or 0)
        if monto <= 0:
            continue
        tipo = str(c.get('tipo_cfdi', '') or '').lower().strip()
        nombre = (c.get('receptor_nombre') or c.get('emisor_nombre') or
                  c.get('concepto') or 'Sin nombre')
        processed_cfdis.append({
            'fecha': fecha,
            'monto': monto,
            'tipo': tipo,
            'nombre': nombre,
            'categoria': c.get('categoria', 'otros'),
            'id': c.get('id', ''),
        })

    # ── 4. Construir resultado por semana ─────────────────────────
    result = []
    today = date.today()

    for week in weeks_raw:
        fi = _parse_date(week.get('fecha_inicio'))
        ff = _parse_date(week.get('fecha_fin'))
        num = int(week.get('numero_semana', len(result) + 1))

        if not fi or not ff:
            continue

        ingresos = []
        egresos = []
        for c in processed_cfdis:
            if fi <= c['fecha'] <= ff:
                item = {
                    'id': c['id'],
                    'concepto': c['nombre'],
                    'monto': c['monto'],
                    'fecha': c['fecha'],
                    'categoria': c['categoria'],
                }
                if c['tipo'] in ('i', 'ingreso', 'income', 'entrada'):
                    ingresos.append(item)
                elif c['tipo'] in ('e', 'egreso', 'expense', 'salida', 'gasto'):
                    egresos.append(item)

        total_ing = sum(i['monto'] for i in ingresos)
        total_egr = sum(e['monto'] for e in egresos)

        # Fallback: si no hay CFDIs, usar totales guardados en DB
        if total_ing == 0 and total_egr == 0:
            total_ing = float(week.get('total_ingresos', 0) or 0)
            total_egr = float(week.get('total_egresos', 0) or 0)
            if total_ing > 0:
                ingresos = [{'id': '', 'concepto': 'Ingresos del período',
                             'monto': total_ing, 'fecha': fi, 'categoria': 'sync'}]
            if total_egr > 0:
                egresos = [{'id': '', 'concepto': 'Egresos del período',
                            'monto': total_egr, 'fecha': fi, 'categoria': 'sync'}]

        top_ing = sorted(ingresos, key=lambda x: x['monto'], reverse=True)[:5]
        top_egr = sorted(egresos, key=lambda x: x['monto'], reverse=True)[:5]

        try:
            fi_date = date.fromisoformat(fi)
            ff_date = date.fromisoformat(ff)
            es_real = ff_date < today
            date_range = f"{fi_date.strftime('%d/%m')} - {ff_date.strftime('%d/%m')}"
        except Exception:
            es_real = False
            date_range = f"{fi[8:10]}/{fi[5:7]} - {ff[8:10]}/{ff[5:7]}"

        result.append({
            'id': week.get('id', ''),
            'company_id': company_id,
            'numero_semana': num,
            'label': f'S{num}',
            'fecha_inicio': fi,
            'fecha_fin': ff,
            'date_range': date_range,
            'week_start': fi,
            'week_end': ff,
            'es_real': es_real,
            'saldo_inicial': float(week.get('saldo_inicial', 0) or 0),
            'total_ingresos': total_ing,
            'total_egresos': total_egr,
            'flujo_neto': total_ing - total_egr,
            'ingresos_detalle': ingresos,
            'egresos_detalle': egresos,
            'top_ingresos': top_ing,
            'top_egresos': top_egr,
            'notas': week.get('notas', ''),
        })

    # ── 5. Generar semanas futuras si faltan ──────────────────────
    if result and len(result) < num_weeks:
        ultima = result[-1]
        try:
            next_start = date.fromisoformat(ultima['fecha_fin']) + timedelta(days=1)
        except Exception:
            next_start = today
        num_ini = ultima['numero_semana'] + 1

        for i in range(num_weeks - len(result)):
            ws = next_start + timedelta(weeks=i)
            we = ws + timedelta(days=6)
            num = num_ini + i
            fi_s = ws.isoformat()
            ff_s = we.isoformat()

            ingresos = []
            egresos = []
            for c in processed_cfdis:
                if fi_s <= c['fecha'] <= ff_s:
                    item = {'id': c['id'], 'concepto': c['nombre'],
                            'monto': c['monto'], 'fecha': c['fecha'], 'categoria': c['categoria']}
                    if c['tipo'] in ('i', 'ingreso', 'income', 'entrada'):
                        ingresos.append(item)
                    elif c['tipo'] in ('e', 'egreso', 'expense', 'salida', 'gasto'):
                        egresos.append(item)

            total_ing = sum(i['monto'] for i in ingresos)
            total_egr = sum(e['monto'] for e in egresos)

            result.append({
                'id': str(_uuid.uuid4()),
                'company_id': company_id,
                'numero_semana': num,
                'label': f'S{num}',
                'fecha_inicio': fi_s,
                'fecha_fin': ff_s,
                'date_range': f"{ws.strftime('%d/%m')} - {we.strftime('%d/%m')}",
                'week_start': fi_s,
                'week_end': ff_s,
                'es_real': False,
                'es_generada': True,
                'saldo_inicial': 0,
                'total_ingresos': total_ing,
                'total_egresos': total_egr,
                'flujo_neto': total_ing - total_egr,
                'ingresos_detalle': ingresos,
                'egresos_detalle': egresos,
                'top_ingresos': sorted(ingresos, key=lambda x: x['monto'], reverse=True)[:5],
                'top_egresos': sorted(egresos, key=lambda x: x['monto'], reverse=True)[:5],
                'notas': '',
            })

    return result
