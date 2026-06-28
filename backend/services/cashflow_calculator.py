"""
Servicio único de cálculo de semanas de cashflow. v2.2 - 2026-06-27
Fuentes: db.cashflow_weeks (estructura) + db.cfdis (por fecha_emision) + db.cxc_proyecciones + Alegra CxC/CxP pendientes.

CAMBIO v2.2: Anclas bancarias reales.
El saldo semanal rolling se ancla a los saldos reales de db.bank_accounts (campo fecha_saldo).
Cada vez que el rolling pasa por una semana que CONTIENE una fecha_saldo de banco,
se reemplaza el saldo acumulado con el saldo real verificado (MXN + USD×TC).
Esto garantiza que el saldo de fin de mes siempre cuadre con el estado de cuenta bancario.
"""
import re
import uuid as _uuid
import logging
from datetime import date, timedelta
from typing import List, Dict, Optional

from core.database import db as _db_default
from services.fx import get_fx_rate_by_date

logger = logging.getLogger(__name__)


def _parse_date(val) -> str:
    """Extrae YYYY-MM-DD de cualquier formato."""
    if not val:
        return ''
    m = re.search(r'(\d{4}-\d{2}-\d{2})', str(val))
    return m.group(1) if m else ''


async def _build_bank_anchors(company_id: str, db) -> Dict[str, float]:
    """
    Construye un dict de anclas bancarias: {fecha_iso: saldo_total_mxn}.

    Fuentes (en orden de prioridad):
    1. db.bank_account_history — saldos históricos verificados por corte mensual
    2. db.bank_accounts.saldo_inicial + fecha_saldo — saldo actual de la cuenta

    Para cada fecha, suma todos los saldos de todas las cuentas activas,
    convirtiendo moneda extranjera a MXN con el TC de esa fecha.
    """
    # ── Fuente 1: Historial de saldos verificados ─────────────────
    # Agrupar por fecha → {fecha: {account_id: {saldo, moneda}}}
    history_docs = await db.bank_account_history.find(
        {'company_id': company_id},
        {'_id': 0, 'account_id': 1, 'fecha': 1, 'saldo': 1, 'moneda': 1}
    ).to_list(1000)

    # Obtener monedas por account_id (para historial que no guarda moneda)
    accounts = await db.bank_accounts.find(
        {'company_id': company_id, 'activo': True},
        {'_id': 0, 'id': 1, 'moneda': 1, 'saldo_inicial': 1, 'fecha_saldo': 1}
    ).to_list(100)
    moneda_by_id = {a['id']: a.get('moneda', 'MXN') for a in accounts}

    # Agrupar historial por fecha — si hay duplicados, queda el de mayor saldo (más reciente cargado)
    history_by_date: Dict[str, Dict[str, dict]] = {}
    for h in history_docs:
        fecha = _parse_date(h.get('fecha'))
        if not fecha:
            continue
        acct_id = h.get('account_id', '')
        saldo_h = float(h.get('saldo', 0) or 0)
        # Si ya hay una entrada para (fecha, acct_id), conservar la de mayor saldo
        # (el script de carga puede haber insertado duplicados antes del fix upsert)
        if fecha not in history_by_date:
            history_by_date[fecha] = {}
        prev = history_by_date[fecha].get(acct_id)
        if prev is None or saldo_h > prev.get('saldo', 0):
            history_by_date[fecha][acct_id] = {
                'saldo': saldo_h,
                'moneda': h.get('moneda') or moneda_by_id.get(acct_id, 'MXN'),
            }

    # ── Fuente 2: Saldo actual de bank_accounts ───────────────────
    for acc in accounts:
        fecha_str = _parse_date(acc.get('fecha_saldo'))
        if not fecha_str:
            continue
        acct_id = acc['id']
        # Solo agregar si NO hay historial para esta cuenta en esta fecha
        if fecha_str not in history_by_date:
            history_by_date[fecha_str] = {}
        if acct_id not in history_by_date[fecha_str]:
            history_by_date[fecha_str][acct_id] = {
                'saldo': float(acc.get('saldo_inicial', 0) or 0),
                'moneda': acc.get('moneda', 'MXN'),
            }

    # ── Convertir a MXN y sumar por fecha ────────────────────────
    anchors: Dict[str, float] = {}
    for fecha_str, accts in history_by_date.items():
        total_mxn = 0.0
        for acct_id, data in accts.items():
            saldo = data['saldo']
            moneda = data['moneda']
            if moneda != 'MXN' and saldo > 0:
                try:
                    from datetime import datetime as _dt
                    fecha_dt = _dt.fromisoformat(fecha_str)
                    tc = await get_fx_rate_by_date(company_id, moneda, fecha_dt)
                except Exception:
                    tc = 1.0
                total_mxn += saldo * tc
            else:
                total_mxn += saldo
        anchors[fecha_str] = total_mxn

    logger.info(f"[cashflow-anchors] {company_id}: {len(anchors)} anclas → {anchors}")
    return anchors


def _get_anchor_for_week(
    anchors: Dict[str, float],
    fi: str,
    ff: str,
) -> Optional[float]:
    """
    Si alguna fecha de ancla bancaria cae DENTRO de la semana [fi, ff],
    devuelve el saldo de ancla más reciente de esa semana.
    Retorna None si no hay ancla en esa semana.
    """
    best_date = None
    best_val = None
    for fecha_str, saldo_mxn in anchors.items():
        if fi <= fecha_str <= ff:
            if best_date is None or fecha_str > best_date:
                best_date = fecha_str
                best_val = saldo_mxn
    return best_val


async def calcular_semanas_cashflow(company_id: str, num_weeks: int = 52, db=None) -> List[Dict]:
    if db is None:
        db = _db_default

    # ── 0. Cargar anclas bancarias reales ─────────────────────────
    # Dict {fecha_iso: saldo_total_mxn} — se usa para resetear el rolling
    # cuando el calendario pasa por una fecha de corte bancario verificada.
    bank_anchors = await _build_bank_anchors(company_id, db)

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

    # ── Fuente 4: Payments reales de Alegra ──────────────────────
    # DESACTIVADO para Alegra: los bank_transactions (Fuente 5) ya representan
    # los mismos movimientos con category_name correcto. Usar ambos duplica cada pago.
    # Fuente 4 solo se usa para fuentes no-Alegra (Contalink, manual).
    payments_reales_no_alegra = await db.payments.find({
        'company_id': company_id,
        'source': {'$ne': 'alegra'},
        'estatus': 'completado',
        'es_real': True,
    }, {'_id': 0, 'tipo': 1, 'monto': 1, 'fecha_pago': 1,
        'concepto': 1, 'beneficiario': 1, 'nombre': 1, 'id': 1}).to_list(5000)

    processed_payments = []
    for p in payments_reales_no_alegra:
        fecha = _parse_date(p.get('fecha_pago'))
        if not fecha:
            continue
        monto = float(p.get('monto', 0) or 0)
        if monto <= 0:
            continue
        tipo = str(p.get('tipo', '') or '').lower()
        concepto_raw = p.get('concepto', '')
        beneficiario_raw = p.get('beneficiario', '')
        if concepto_raw and not concepto_raw.startswith('Factura') and not concepto_raw.startswith('CUSTINVC'):
            nombre = concepto_raw
        else:
            nombre = beneficiario_raw or concepto_raw or 'Sin nombre'
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
        'descripcion': 1, 'contacto': 1, 'cuenta_bancaria': 1, 'id': 1,
        'category_name': 1, 'alegra_id': 1}).to_list(5000)

    # Categorías que son traspasos internos — no representan flujo real de caja
    TRASPASO_CATS = {'traspaso entre cuentas', 'transferencia entre cuentas', 'comisiones bancarias'}
    TRASPASO_KW   = ['operacion cambios', 'operación cambios', 'cambio de divisa',
                     'traspaso', 'retiro por operacion', 'deposito por operacion']
    # Categorías genéricas que indican movimiento sin categorizar — preferir las específicas
    GENERIC_CATS  = {'cobro_alegra', 'banco_alegra', 'pago_alegra', ''}

    # ── Deduplicar bank_transactions por alegra_id ────────────────
    # El sync de Alegra puede generar dos registros para el mismo movimiento:
    # uno desde conciliaciones (categoría real) y otro desde payments (cobro_alegra).
    # Deduplicamos por alegra_id conservando el de categoría más específica.
    # Si no hay alegra_id, usamos (fecha, monto, tipo) como clave secundaria.
    seen: dict = {}  # clave → mejor registro
    for t in bank_txns_alegra:
        cat_name = (t.get('category_name') or '').lower().strip()
        descripcion = (t.get('descripcion') or t.get('contacto') or '').lower()
        # Excluir traspasos
        if cat_name in TRASPASO_CATS or any(kw in descripcion for kw in TRASPASO_KW):
            continue
        monto = float(t.get('monto', 0) or 0)
        if monto <= 0:
            continue
        fecha = _parse_date(t.get('fecha') or t.get('fecha_movimiento'))
        if not fecha:
            continue
        tipo_raw = str(t.get('tipo', '') or '').lower()
        # Clave de deduplicación: alegra_id si existe, sino (fecha, monto, tipo_normalizado)
        alegra_id = t.get('alegra_id') or ''
        # Normalizar tipo: deposito/credito/ingreso → IN, retiro/debito/egreso → OUT
        tipo_norm = 'IN' if tipo_raw in ('deposito', 'ingreso', 'credito', 'deposito_transferencia') else 'OUT'
        clave = str(alegra_id) if alegra_id else f"{fecha}|{round(monto,2)}|{tipo_norm}"
        # Puntaje: categoría específica > genérica
        score = 0 if cat_name in GENERIC_CATS else 1
        prev = seen.get(clave)
        if prev is None:
            seen[clave] = (score, t)
        else:
            if score > prev[0]:
                seen[clave] = (score, t)

    processed_bank_txns = []
    for clave, (score, t) in seen.items():
        cat_name = (t.get('category_name') or '').lower().strip()
        tipo_raw  = str(t.get('tipo', '') or '').lower()
        tipo = 'ingreso' if tipo_raw in ('deposito', 'ingreso', 'credito') else 'egreso'
        nombre = t.get('contacto') or t.get('descripcion') or 'Movimiento bancario'
        fecha  = _parse_date(t.get('fecha') or t.get('fecha_movimiento'))
        monto  = float(t.get('monto', 0) or 0)
        processed_bank_txns.append({
            'fecha': fecha,
            'monto': monto,
            'tipo': tipo,
            'nombre': nombre,
            'cuenta_bancaria': t.get('cuenta_bancaria', ''),
            'id': t.get('id', ''),
            'category_name': t.get('category_name', ''),
            'es_real': True,
        })

    if processed_bank_txns:
        sample = processed_bank_txns[0]
        logger.info(f"[cashflow-debug] sample bt: nombre='{sample.get('nombre')}' cuenta='{sample.get('cuenta_bancaria')}'")

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
                    'concepto': bt.get('nombre') or bt.get('descripcion') or bt.get('cuenta_bancaria') or 'Transferencia bancaria',
                    'nombre': bt.get('nombre') or bt.get('descripcion') or bt.get('cuenta_bancaria') or 'Transferencia bancaria',
                    'monto': bt['monto'],
                    'fecha': bt['fecha'],
                    'categoria': bt.get('category_name') or ('cobro_alegra' if bt.get('tipo') == 'ingreso' else 'banco_alegra'),
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

        # ── Saldo rolling con anclas bancarias ─────────────────────
        # Prioridad: 1) ancla bancaria verificada dentro de la semana
        #            2) saldo acumulado del periodo anterior
        #            3) saldo_inicial de DB (solo semana S1 sin ancla)
        anchor = _get_anchor_for_week(bank_anchors, fi, ff)
        if anchor is not None:
            # Hay saldo real bancario para esta semana → anclar
            saldo_ini = anchor
            logger.info(f"[cashflow-anchor] S{num} ({fi}→{ff}): anclado a ${anchor:,.2f} MXN")
        elif saldo_acumulado is None:
            # Primera semana sin ancla → usar valor de DB (o 0)
            saldo_ini = float(week.get('saldo_inicial', 0) or 0)
        else:
            # Rolling normal
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
            'saldo_anclado': anchor is not None,  # True = saldo verificado con banco
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
                    item = {'id': bt['id'], 'concepto': bt.get('nombre') or bt.get('descripcion') or bt.get('cuenta_bancaria') or 'Transferencia bancaria',
                            'nombre': bt.get('nombre') or bt.get('descripcion') or bt.get('cuenta_bancaria') or 'Transferencia bancaria',
                            'monto': bt['monto'], 'fecha': bt['fecha'],
                            'categoria': bt.get('category_name') or ('cobro_alegra' if bt.get('tipo') == 'ingreso' else 'banco_alegra'),
                            'es_real': True}
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

            # Rolling saldo con anclas (también aplica en semanas futuras generadas)
            anchor = _get_anchor_for_week(bank_anchors, fi_s, ff_s)
            if anchor is not None:
                saldo_ini = anchor
                logger.info(f"[cashflow-anchor-gen] S{num} ({fi_s}→{ff_s}): anclado a ${anchor:,.2f} MXN")
            else:
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
                'saldo_anclado': anchor is not None,
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
