"""
Servicio único de cálculo de semanas de cashflow. v2.1 - 2026-06-17
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

    # ── 2. Leer CFDIs de fuentes NO-Alegra (Contalink, SAT, manual, etc.) ──
    cfdis = await db.cfdis.find(
        {
            'company_id': company_id,
            'source': {'$ne': 'alegra'},
        },
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

    # ── Fuente 4: Payments reales de Alegra (cobros/pagos efectivos) ─
    payments_reales = await db.payments.find({
        'company_id': company_id,
        'source': 'alegra',
        'estatus': 'completado',
        'es_real': True,
    }, {'_id': 0, 'tipo': 1, 'monto': 1, 'fecha_pago': 1,
        'concepto': 1, 'beneficiario': 1, 'id': 1}).to_list(5000)

    processed_payments = []
    for p in payments_reales:
        fecha = _parse_date(p.get('fecha_pago'))
        if not fecha:
            continue
        monto = float(p.get('monto', 0) or 0)
        if monto <= 0:
            continue
        tipo = str(p.get('tipo', '') or '').lower()
        nombre = p.get('concepto') or p.get('beneficiario') or 'Sin nombre'
        processed_payments.append({
            'fecha': fecha,
            'monto': monto,
            'tipo': 'cobro' if tipo == 'cobro' else 'pago',
            'nombre': nombre,
            'categoria': 'cobro_alegra' if tipo == 'cobro' else 'pago_alegra',
            'id': p.get('id', ''),
            'es_real': True,
        })

    # ── Fuente 5: Movimientos bancarios reales de Alegra (conciliaciones) ─
    bank_txns_alegra = await db.bank_transactions.find({
        'company_id': company_id,
        'source': 'alegra',
        'es_real': True,
    }, {'_id': 0, 'tipo': 1, 'monto': 1, 'fecha': 1, 'fecha_movimiento': 1,
        'descripcion': 1, 'contacto': 1, 'id': 1}).to_list(5000)

    processed_bank_txns = []
    for t in bank_txns_alegra:
        fecha = _parse_date(t.get('fecha') or t.get('fecha_movimiento'))
        if not fecha:
            continue
        monto = float(t.get('monto', 0) or 0)
        if monto <= 0:
            continue
        tipo_raw = str(t.get('tipo', '') or '').lower()
        tipo = 'ingreso' if tipo_raw in ('deposito', 'ingreso', 'credito') else 'egreso'
        nombre = t.get('contacto') or t.get('descripcion') or 'Movimiento bancario'
        processed_bank_txns.append({
            'fecha': fecha,
            'monto': monto,
            'tipo': tipo,
            'nombre': nombre,
            'id': t.get('id', ''),
            'es_real': True,
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

    today = date.today()

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

        for p in processed_payments:
            if fi <= p['fecha'] <= ff:
                item = {
                    'id': p['id'],
                    'concepto': p['nombre'],
                    'monto': p['monto'],
                    'fecha': p['fecha'],
                    'categoria': p['categoria'],
                    'es_real': True,
                }
                if p['tipo'] == 'cobro':
                    ingresos.append(item)
                else:
                    egresos.append(item)

        for bt in processed_bank_txns:
            if fi <= bt['fecha'] <= ff:
                item = {
                    'id': bt['id'],
                    'concepto': bt.get('contacto') or bt.get('descripcion') or bt.get('nombre', 'Movimiento bancario'),
                    'monto': bt['monto'],
                    'fecha': bt['fecha'],
                    'categoria': 'banco_alegra',
                    'es_real': True,
                }
                if bt['tipo'] == 'ingreso':
                    ingresos.append(item)
                else:
                    egresos.append(item)

        total_ing = sum(i['monto'] for i in ingresos)
        total_egr = sum(e['monto'] for e in egresos)

        try:
            fi_date = date.fromisoformat(fi)
            ff_date = date.fromisoformat(ff)
            es_real = ff_date < today
            date_range = f"{fi_date.strftime('%d/%m')} - {ff_date.strftime('%d/%m')}"
        except Exception:
            fi_date = None
            ff_date = None
            es_real = False
            date_range = f"{fi[8:10]}/{fi[5:7]} - {ff[8:10]}/{ff[5:7]}"

        # Solo agregar proyecciones si la semana no tiene CFDIs reales
        label = f'S{num}'
        if label in proy_por_semana:
            tiene_cfdis_reales = (
                any(not i.get('es_proyeccion') for i in ingresos) or
                any(not e.get('es_proyeccion') for e in egresos)
            )
            if not tiene_cfdis_reales:
                proy = proy_por_semana[label]
                semana_es_futura = fi_date is not None and fi_date > today
                if semana_es_futura:
                    ingresos.extend(proy['ingresos'])
                    egresos.extend(proy['egresos'])
                else:
                    # Semanas pasadas/actuales: solo proyecciones manuales, no Alegra CxC/CxP
                    ingresos.extend([i for i in proy['ingresos'] if i.get('fuente') not in ('alegra_cxc', 'alegra_cxp')])
                    egresos.extend([e for e in proy['egresos'] if e.get('fuente') not in ('alegra_cxc', 'alegra_cxp')])
        total_ing = sum(i['monto'] for i in ingresos)
        total_egr = sum(e['monto'] for e in egresos)

        top_ing = sorted(ingresos, key=lambda x: x['monto'], reverse=True)[:5]
        top_egr = sorted(egresos, key=lambda x: x['monto'], reverse=True)[:5]

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

            for p in processed_payments:
                if fi_s <= p['fecha'] <= ff_s:
                    item = {'id': p['id'], 'concepto': p['nombre'],
                            'monto': p['monto'], 'fecha': p['fecha'],
                            'categoria': p['categoria'], 'es_real': True}
                    if p['tipo'] == 'cobro':
                        ingresos.append(item)
                    else:
                        egresos.append(item)

            for bt in processed_bank_txns:
                if fi_s <= bt['fecha'] <= ff_s:
                    item = {'id': bt['id'], 'concepto': bt.get('contacto') or bt.get('descripcion') or bt.get('nombre', 'Movimiento bancario'),
                            'monto': bt['monto'], 'fecha': bt['fecha'],
                            'categoria': 'banco_alegra', 'es_real': True}
                    if bt['tipo'] == 'ingreso':
                        ingresos.append(item)
                    else:
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
