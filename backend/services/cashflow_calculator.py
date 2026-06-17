"""
Servicio único de cálculo de semanas de cashflow.
Fuentes: db.cashflow_weeks (estructura) + db.cfdis (por fecha_emision) + db.cxc_proyecciones + Alegra CxC/CxP pendientes.
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

    # ── Fuente 2: Proyecciones manuales de CxC/CxP ───────────────
    proyecciones = await db.cxc_proyecciones.find(
        {'company_id': company_id},
        {'_id': 0, 'nombre': 1, 'tipo': 1, 'semana': 1, 'monto': 1}
    ).to_list(1000)

    proy_por_semana = {}  # {'S25': {'ingresos': [...], 'egresos': [...]}}
    for p in proyecciones:
        semana_label = p.get('semana', '')
        if not semana_label:
            continue
        monto = float(p.get('monto', 0) or 0)
        if monto <= 0:
            continue
        if semana_label not in proy_por_semana:
            proy_por_semana[semana_label] = {'ingresos': [], 'egresos': []}
        item = {
            'id': '',
            'concepto': p.get('nombre', 'Sin nombre'),
            'monto': monto,
            'fecha': '',
            'categoria': 'proyeccion',
            'es_proyeccion': True,
        }
        if p.get('tipo') == 'cxc':
            proy_por_semana[semana_label]['ingresos'].append(item)
        else:
            proy_por_semana[semana_label]['egresos'].append(item)

    # ── Fuente 3: CxC/CxP reales de Alegra (facturas pendientes) ─
    today = date.today()

    cfdis_pendientes = await db.cfdis.find({
        'company_id': company_id,
        'source': 'alegra',
        'estado_conciliacion': {'$in': ['pendiente', 'parcial']},
        'estatus': {'$ne': 'cancelado'},
    }, {'_id': 0, 'tipo_cfdi': 1, 'saldo_pendiente': 1, 'total': 1,
        'monto_cobrado': 1, 'monto_pagado': 1, 'fecha_vencimiento': 1,
        'receptor_nombre': 1, 'emisor_nombre': 1, 'folio_alegra': 1}).to_list(5000)

    # Construir mapa de rangos de semanas para lookup por fecha_vencimiento
    week_ranges = []
    for w in weeks_raw:
        wfi = _parse_date(w.get('fecha_inicio'))
        wff = _parse_date(w.get('fecha_fin'))
        wnum = int(w.get('numero_semana', 0))
        if wfi and wff:
            week_ranges.append((wfi, wff, f'S{wnum}'))

    for cfdi_p in cfdis_pendientes:
        fv = _parse_date(cfdi_p.get('fecha_vencimiento'))
        if not fv:
            continue
        total = float(cfdi_p.get('total', 0) or 0)
        monto_cob = float(cfdi_p.get('monto_cobrado', 0) or 0)
        monto_pag = float(cfdi_p.get('monto_pagado', 0) or 0)
        tipo_c = str(cfdi_p.get('tipo_cfdi', '') or '').lower().strip()

        if tipo_c in ('ingreso', 'i', 'income'):
            saldo = total - monto_cob
            fuente = 'alegra_cxc'
            bucket = 'ingresos'
        else:
            saldo = total - monto_pag
            fuente = 'alegra_cxp'
            bucket = 'egresos'

        if saldo <= 0.01:
            continue

        label = None
        week_ff_str = None
        for (wfi, wff, lbl) in week_ranges:
            if wfi <= fv <= wff:
                label = lbl
                week_ff_str = wff
                break

        if not label:
            continue

        # No agregar si la semana ya es pasada (datos reales ya la cubren)
        if week_ff_str:
            try:
                if date.fromisoformat(week_ff_str) < today:
                    continue
            except Exception:
                pass

        nombre = (cfdi_p.get('receptor_nombre') or cfdi_p.get('emisor_nombre') or
                  cfdi_p.get('folio_alegra') or 'Sin nombre')

        if label not in proy_por_semana:
            proy_por_semana[label] = {'ingresos': [], 'egresos': []}

        proy_por_semana[label][bucket].append({
            'id': '',
            'concepto': nombre,
            'monto': saldo,
            'fecha': fv,
            'categoria': 'cxc' if fuente == 'alegra_cxc' else 'cxp',
            'es_proyeccion': True,
            'fuente': fuente,
        })

    # ── 4. Construir resultado por semana ─────────────────────────
    result = []
    saldo_acumulado = None  # Para rolling saldo_inicial

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

        # Solo agregar proyecciones si la semana no tiene CFDIs reales
        label = f'S{num}'
        if label in proy_por_semana:
            tiene_cfdis_reales = (
                any(not i.get('es_proyeccion') for i in ingresos) or
                any(not e.get('es_proyeccion') for e in egresos)
            )
            if not tiene_cfdis_reales:
                proy = proy_por_semana[label]
                ingresos.extend(proy['ingresos'])
                egresos.extend(proy['egresos'])
        total_ing = sum(i['monto'] for i in ingresos)
        total_egr = sum(e['monto'] for e in egresos)

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

        # Rolling saldo_inicial: primera semana usa valor de DB, las siguientes acumulan
        if saldo_acumulado is None:
            saldo_ini = float(week.get('saldo_inicial', 0) or 0)
        else:
            saldo_ini = saldo_acumulado
        saldo_acumulado = saldo_ini + (total_ing - total_egr)

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
            'saldo_inicial': saldo_ini,
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

            # Solo agregar proyecciones si la semana generada no tiene CFDIs reales
            label = f'S{num}'
            if label in proy_por_semana:
                tiene_cfdis_reales = (
                    any(not i.get('es_proyeccion') for i in ingresos) or
                    any(not e.get('es_proyeccion') for e in egresos)
                )
                if not tiene_cfdis_reales:
                    proy = proy_por_semana[label]
                    ingresos.extend(proy['ingresos'])
                    egresos.extend(proy['egresos'])

            total_ing = sum(i['monto'] for i in ingresos)
            total_egr = sum(e['monto'] for e in egresos)

            # Rolling saldo_inicial continúa desde donde terminó el loop anterior
            saldo_ini = saldo_acumulado if saldo_acumulado is not None else 0
            saldo_acumulado = saldo_ini + (total_ing - total_egr)

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
                'saldo_inicial': saldo_ini,
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
