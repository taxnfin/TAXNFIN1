"""
Treasury Decisions Module
Provides actionable insights, alerts, KPIs and working capital intelligence
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id

def safe_parse_date(date_str) -> datetime:
    """Parse date string ensuring timezone awareness"""
    if not date_str:
        return None
    try:
        if isinstance(date_str, datetime):
            return date_str.replace(tzinfo=timezone.utc) if date_str.tzinfo is None else date_str
        dt = datetime.fromisoformat(str(date_str).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

router = APIRouter(prefix="/treasury", tags=["Treasury"])
logger = logging.getLogger(__name__)


def get_week_number(date_str: str) -> int:
    """Get ISO week number from date string"""
    try:
        if isinstance(date_str, str):
            dt = safe_parse_date(date_str)
        else:
            dt = date_str
        return dt.isocalendar()[1]
    except:
        return datetime.now().isocalendar()[1]


def get_week_label(week_offset: int) -> str:
    """Get week label like S1, S2, etc."""
    return f"S{week_offset + 1}"


@router.get("/dashboard")
async def get_treasury_dashboard(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    weeks_ahead: int = Query(16, description="Number of weeks to analyze")
):
    """
    Get complete treasury dashboard with:
    - Actionable alerts
    - Recommendations
    - Treasury calendar
    - Concentration KPIs
    - Working capital intelligence
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Get company settings for thresholds
    company = await db.companies.find_one({'id': company_id}, {'_id': 0}) or {}
    min_balance_threshold = company.get('min_balance_threshold', 100000)
    
    # Calculate all metrics
    alerts = await calculate_alerts(company_id, min_balance_threshold, weeks_ahead)
    recommendations = await generate_recommendations(company_id, weeks_ahead)
    calendar = await get_treasury_calendar(company_id, weeks_ahead)
    concentration_kpis = await calculate_concentration_kpis(company_id)
    working_capital = await calculate_working_capital_intelligence(company_id)
    cash_position = await get_current_cash_position(company_id)
    
    return {
        "alerts": alerts,
        "recommendations": recommendations,
        "calendar": calendar,
        "concentration_kpis": concentration_kpis,
        "working_capital": working_capital,
        "cash_position": cash_position,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


async def get_current_cash_position(company_id: str) -> dict:
    """Get current cash position summary"""
    # Get bank accounts with balances
    accounts = await db.bank_accounts.find(
        {'company_id': company_id, '$or': [{'activa': True}, {'activo': True}]},
        {'_id': 0}
    ).to_list(100)
    
    # Cargar tipos de cambio reales de la BD
    fx_docs = await db.fx_rates.find(
        {'company_id': company_id},
        {'_id': 0, 'moneda_cotizada': 1, 'tipo_cambio': 1}
    ).sort('fecha_vigencia', -1).to_list(50)
    fx_map: dict = {'MXN': 1.0}
    for fx in fx_docs:
        code = fx.get('moneda_cotizada')
        if code and code not in fx_map:
            fx_map[code] = float(fx.get('tipo_cambio', 1) or 1)

    total_mxn = 0
    for acc in accounts:
        balance = acc.get('saldo_actual') or acc.get('saldo') or acc.get('saldo_inicial') or acc.get('balance', 0) or 0
        currency = acc.get('moneda', 'MXN')
        rate = fx_map.get(currency, 1.0)
        total_mxn += balance * rate
    
    # Get pending collections and payments — from payments collection
    pending_collections = await db.payments.aggregate([
        {'$match': {'company_id': company_id, 'tipo': 'cobro', 'estatus': {'$in': ['pendiente', 'parcial']}}},
        {'$group': {'_id': None, 'total': {'$sum': {'$ifNull': ['$saldo_pendiente', '$monto']}}}}
    ]).to_list(1)
    
    pending_payments = await db.payments.aggregate([
        {'$match': {'company_id': company_id, 'tipo': 'pago', 'estatus': {'$in': ['pendiente', 'parcial']}}},
        {'$group': {'_id': None, 'total': {'$sum': {'$ifNull': ['$saldo_pendiente', '$monto']}}}}
    ]).to_list(1)
    
    cxc = pending_collections[0]['total'] if pending_collections else 0
    cxp = pending_payments[0]['total'] if pending_payments else 0

    # Fallback: usar cache de Contalink CxC/CxP cuando no hay pagos pendientes
    if cxc == 0:
        cxc_cache = await db.contalink_cache.find_one({"key": f"cxc_{company_id}_latest"})
        if cxc_cache and cxc_cache.get("data"):
            cxc = cxc_cache["data"].get("total_pendiente", 0) if isinstance(cxc_cache["data"], dict) else 0

    if cxp == 0:
        cxp_cache = await db.contalink_cache.find_one({"key": f"cxp_{company_id}_latest"})
        if cxp_cache and cxp_cache.get("data"):
            cxp = cxp_cache["data"].get("total_pendiente", 0) if isinstance(cxp_cache["data"], dict) else 0
    
    return {
        "saldo_actual": total_mxn,
        "cuentas_por_cobrar": cxc,
        "cuentas_por_pagar": cxp,
        "flujo_neto_esperado": cxc - cxp,
        "posicion_proyectada": total_mxn + cxc - cxp
    }


def _get_fecha_efectiva(item: dict, today_date) -> str:
    """Return ISO date string for due date, estimating from dias_vencido when fecha_vencimiento is absent."""
    fv = item.get('fecha_vencimiento', '')
    if fv:
        return str(fv)[:10]
    dias = int(item.get('dias_vencido', 0) or 0)
    if dias > 30:
        return today_date.isoformat()
    elif dias > 0:
        return (today_date + timedelta(days=7)).isoformat()
    else:
        dias_restantes = abs(dias) if dias < 0 else 14
        return (today_date + timedelta(days=min(dias_restantes, 90))).isoformat()


async def calculate_alerts(company_id: str, threshold: float, weeks_ahead: int) -> List[dict]:
    """Calculate actionable alerts based on cash flow projections"""
    alerts = []
    today = datetime.now(timezone.utc)
    today_date = today.date()

    # Get pending payments grouped by week — from payments collection
    pending_payments = await db.payments.find(
        {'company_id': company_id, 'tipo': 'pago', 'estatus': {'$in': ['pendiente', 'parcial']}},
        {'_id': 0}
    ).to_list(5000)
    
    pending_collections = await db.payments.find(
        {'company_id': company_id, 'tipo': 'cobro', 'estatus': {'$in': ['pendiente', 'parcial']}},
        {'_id': 0}
    ).to_list(5000)

    # Fallback: usar cache de Contalink CxC/CxP para proyecciones semanales
    if not pending_collections:
        cxc_cache = await db.contalink_cache.find_one({"key": f"cxc_{company_id}_latest"})
        if cxc_cache:
            raw = cxc_cache.get('data', {})
            facturas = next((v for v in raw.values() if isinstance(v, list)), []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
            pending_collections = [
                {
                    'tipo': 'cobro',
                    'monto': float(f.get('saldo_pendiente') or f.get('saldo') or f.get('total') or 0),
                    'fecha_vencimiento': f.get('fecha_vence') or f.get('fecha_vencimiento') or f.get('fecha'),
                    'beneficiario': f.get('cliente') or f.get('nombre') or f.get('razon_social', ''),
                }
                for f in facturas
                if float(f.get('saldo_pendiente') or f.get('saldo') or f.get('total') or 0) > 0
            ]

    if not pending_payments:
        cxp_cache = await db.contalink_cache.find_one({"key": f"cxp_{company_id}_latest"})
        if cxp_cache:
            raw = cxp_cache.get('data', {})
            facturas = next((v for v in raw.values() if isinstance(v, list)), []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
            pending_payments = [
                {
                    'tipo': 'pago',
                    'monto': float(f.get('saldo_pendiente') or f.get('saldo') or f.get('total') or 0),
                    'fecha_vencimiento': f.get('fecha_vence') or f.get('fecha_vencimiento') or f.get('fecha'),
                    'beneficiario': f.get('proveedor') or f.get('nombre') or f.get('razon_social', ''),
                }
                for f in facturas
                if float(f.get('saldo_pendiente') or f.get('saldo') or f.get('total') or 0) > 0
            ]
    
    # Get current balance
    cash_position = await get_current_cash_position(company_id)
    current_balance = cash_position['saldo_actual']
    
    # Simulate cash flow week by week
    weekly_balance = current_balance
    for week_offset in range(weeks_ahead):
        week_start = today + timedelta(weeks=week_offset)
        week_end = week_start + timedelta(days=7)
        
        # Calculate week's inflows and outflows
        week_collections = sum(
            (p.get('saldo_pendiente') or p.get('monto', 0)) for p in pending_collections
            if week_start.isoformat()[:10] <= _get_fecha_efectiva(p, today_date) < week_end.isoformat()[:10]
        )

        week_payments = sum(
            (p.get('saldo_pendiente') or p.get('monto', 0)) for p in pending_payments
            if week_start.isoformat()[:10] <= _get_fecha_efectiva(p, today_date) < week_end.isoformat()[:10]
        )
        
        weekly_balance += week_collections - week_payments
        
        # Check if balance falls below threshold
        if weekly_balance < threshold:
            deficit = threshold - weekly_balance
            alerts.append({
                "type": "balance_critical",
                "severity": "high" if weekly_balance < 0 else "medium",
                "week": get_week_label(week_offset),
                "week_date": week_start.strftime("%d/%m"),
                "message": f"Saldo cae por debajo del umbral en {get_week_label(week_offset)}",
                "detail": f"Saldo proyectado: ${weekly_balance:,.0f} MXN (déficit: ${deficit:,.0f})",
                "impact": -deficit,
                "action": "Acelerar cobranza o diferir pagos"
            })
    
    # Check for late collections (clients that might delay)
    for collection in pending_collections:
        try:
            due_date = safe_parse_date(_get_fecha_efectiva(collection, today_date))
            if due_date is None:
                continue
            if due_date.tzinfo is None:
                due_date = due_date.replace(tzinfo=timezone.utc)
        except:
            continue
        days_until_due = (due_date - today).days
        amount = (collection.get('saldo_pendiente') or collection.get('monto', 0))

        # If client delays 7 days, what happens?
        if 0 <= days_until_due <= 14 and amount > 50000:
            # Simulate delay impact
            delay_week = (days_until_due + 7) // 7
            alerts.append({
                "type": "collection_delay_risk",
                "severity": "medium",
                "week": get_week_label(delay_week),
                "week_date": (today + timedelta(days=days_until_due + 7)).strftime("%d/%m"),
                "message": f"Si {collection.get('beneficiario', 'cliente')[:30]} se retrasa 7 días",
                "detail": f"Impacto: -${amount:,.0f} MXN en {get_week_label(delay_week)}",
                "impact": -amount,
                "action": f"Dar seguimiento a cobro de ${amount:,.0f}"
            })
    
    # Check for payments that can be moved without risk
    for payment in pending_payments:
        try:
            due_date = safe_parse_date(_get_fecha_efectiva(payment, today_date))
            if due_date is None:
                continue
            if due_date.tzinfo is None:
                due_date = due_date.replace(tzinfo=timezone.utc)
        except:
            continue
        days_until_due = (due_date - today).days
        amount = (payment.get('saldo_pendiente') or payment.get('monto', 0))

        # Payments due in next 2 weeks that could potentially be delayed
        if 0 <= days_until_due <= 14 and amount > 30000:
            alerts.append({
                "type": "payment_flexibility",
                "severity": "low",
                "week": get_week_label(days_until_due // 7),
                "week_date": due_date.strftime("%d/%m"),
                "message": f"{payment.get('beneficiario', 'Proveedor')[:30]} puede moverse 1 semana",
                "detail": f"Libera ${amount:,.0f} MXN temporalmente",
                "impact": amount,
                "action": "Evaluar reprogramación si hay presión de liquidez"
            })
    
    # Sort by severity and week
    severity_order = {'high': 0, 'medium': 1, 'low': 2}
    alerts.sort(key=lambda x: (severity_order.get(x['severity'], 3), x.get('week', 'S99')))
    
    return alerts[:15]  # Limit to top 15 alerts


async def generate_recommendations(company_id: str, weeks_ahead: int) -> List[dict]:
    """Generate actionable recommendations"""
    recommendations = []
    today = datetime.now(timezone.utc)
    
    # Get pending items
    pending_collections = await db.payments.find(
        {'company_id': company_id, 'tipo': 'cobro', 'estatus': {'$in': ['pendiente', 'parcial']}},
        {'_id': 0}
    ).to_list(1000)
    
    pending_payments = await db.payments.find(
        {'company_id': company_id, 'tipo': 'pago', 'estatus': {'$in': ['pendiente', 'parcial']}},
        {'_id': 0}
    ).to_list(1000)
    
    # Sort collections by amount (prioritize larger ones)
    sorted_collections = sorted(pending_collections, key=lambda x: x.get('saldo_pendiente', 0), reverse=True)
    
    # Recommendation: Prioritize collection A vs B
    if len(sorted_collections) >= 2:
        top1 = sorted_collections[0]
        top2 = sorted_collections[1]
        recommendations.append({
            "type": "collection_priority",
            "priority": "high",
            "icon": "💰",
            "title": "Priorizar Cobranza",
            "message": f"Prioriza cobro a {top1.get('beneficiario', 'Cliente A')[:25]} (${(top1.get('saldo_pendiente') or top1.get('monto', 0)):,.0f}) sobre {top2.get('beneficiario', 'Cliente B')[:25]} (${(top2.get('saldo_pendiente') or top2.get('monto', 0)):,.0f})",
            "impact": f"+${(top1.get('saldo_pendiente') or top1.get('monto', 0)):,.0f} MXN",
            "action": "contact_client",
            "entity_id": top1.get('id')
        })
    
    # Recommendation: Payments that can be rescheduled
    flexible_payments = [p for p in pending_payments if (p.get('saldo_pendiente') or p.get('monto', 0)) > 20000]
    flexible_payments.sort(key=lambda x: x.get('fecha_vencimiento', ''), reverse=True)
    
    if flexible_payments:
        payment = flexible_payments[0]
        recommendations.append({
            "type": "reschedule_payment",
            "priority": "medium",
            "icon": "🔄",
            "title": "Reprogramar Pago",
            "message": f"Evalúa mover pago a {payment.get('beneficiario', 'Proveedor')[:25]} 1 semana",
            "impact": f"Libera ${(payment.get('saldo_pendiente') or payment.get('monto', 0)):,.0f} MXN temporalmente",
            "action": "reschedule",
            "entity_id": payment.get('id')
        })
    
    # Recommendation: Anticipated cash flow
    near_term_collections = [c for c in sorted_collections 
                            if c.get('fecha_vencimiento') and 
                            c.get('fecha_vencimiento', '')[:10] <= (today + timedelta(days=7)).isoformat()[:10]]
    
    total_near_term = sum((c.get('saldo_pendiente') or c.get('monto', 0)) for c in near_term_collections)
    if total_near_term > 100000:
        recommendations.append({
            "type": "anticipated_flow",
            "priority": "info",
            "icon": "📈",
            "title": "Flujo Anticipado",
            "message": f"Se esperan ${total_near_term:,.0f} MXN en los próximos 7 días",
            "impact": f"+${total_near_term:,.0f} MXN",
            "action": "monitor",
            "entity_id": None
        })
    
    # Check for overdue items
    overdue_collections = [c for c in pending_collections 
                          if c.get('fecha_vencimiento') and 
                          c.get('fecha_vencimiento', '')[:10] < today.isoformat()[:10]]
    
    total_overdue = sum((c.get('saldo_pendiente') or c.get('monto', 0)) for c in overdue_collections)
    if total_overdue > 0:
        recommendations.append({
            "type": "overdue_collection",
            "priority": "high",
            "icon": "⚠️",
            "title": "Cobranza Vencida",
            "message": f"{len(overdue_collections)} facturas vencidas por ${total_overdue:,.0f} MXN",
            "impact": f"${total_overdue:,.0f} MXN atrasados",
            "action": "urgent_collection",
            "entity_id": None
        })
    
    return recommendations


async def get_treasury_calendar(company_id: str, weeks_ahead: int) -> dict:
    """Get treasury calendar — fuentes: CxC/CxP Aging cache + proyecciones"""
    today = datetime.now(timezone.utc).date()

    # ── FUENTE 1: CxC del Aging (cobranza pendiente) ──
    cxc_doc = await db.contalink_cache.find_one({'key': f'cxc_{company_id}_latest'})
    cobros_pendientes = []
    if cxc_doc:
        raw = cxc_doc.get('data', {})
        items = next((v for v in raw.values() if isinstance(v, list)), []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
        for item in items:
            monto = float(item.get('saldo_pendiente') or item.get('saldo') or item.get('total') or 0)
            if monto <= 0:
                continue
            dias_vencido = int(item.get('dias_vencido', 0) or 0)
            if dias_vencido >= 91:
                fecha_estimada = today + timedelta(days=30)
            elif dias_vencido >= 61:
                fecha_estimada = today + timedelta(days=21)
            elif dias_vencido >= 31:
                fecha_estimada = today + timedelta(days=14)
            elif dias_vencido >= 1:
                fecha_estimada = today + timedelta(days=7)
            else:
                fecha_estimada = today + timedelta(days=14)
            cobros_pendientes.append({
                'concepto': item.get('nombre', 'Sin nombre'),
                'monto': monto,
                'fecha_estimada': fecha_estimada,
                'tipo': 'cobro',
                'categoria': 'cobranza_programada',
                'dias_vencido': dias_vencido,
            })

    # ── FUENTE 2: CxP del Aging (pagos pendientes) ──
    cxp_doc = await db.contalink_cache.find_one({'key': f'cxp_{company_id}_latest'})
    pagos_pendientes = []
    if cxp_doc:
        raw = cxp_doc.get('data', {})
        items = next((v for v in raw.values() if isinstance(v, list)), []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
        for item in items:
            monto = float(item.get('saldo_pendiente') or item.get('saldo') or item.get('total') or 0)
            if monto <= 0:
                continue
            dias_vencido = int(item.get('dias_vencido', 0) or 0)
            if dias_vencido >= 91:
                fecha_estimada = today + timedelta(days=30)
            elif dias_vencido >= 61:
                fecha_estimada = today + timedelta(days=21)
            elif dias_vencido >= 31:
                fecha_estimada = today + timedelta(days=14)
            elif dias_vencido >= 1:
                fecha_estimada = today + timedelta(days=7)
            else:
                fecha_estimada = today + timedelta(days=14)
            pagos_pendientes.append({
                'concepto': item.get('nombre', 'Sin nombre'),
                'monto': monto,
                'fecha_estimada': fecha_estimada,
                'tipo': 'pago',
                'categoria': 'pagos_programados',
                'dias_vencido': dias_vencido,
            })

    # ── FUENTE 3: Proyecciones del Cash Flow ──
    proyecciones = await db.transactions.find(
        {'company_id': company_id, 'es_proyeccion': True},
        {'_id': 0}
    ).to_list(500)

    # ── Diagnóstico temporal ──
    logger.info(f"[CAL DEBUG] today={today} cobros={len(cobros_pendientes)} pagos={len(pagos_pendientes)}")
    if cobros_pendientes:
        logger.info(f"[CAL DEBUG] primer cobro: concepto={cobros_pendientes[0]['concepto']} fecha_estimada={cobros_pendientes[0]['fecha_estimada']} monto={cobros_pendientes[0]['monto']}")
    if pagos_pendientes:
        logger.info(f"[CAL DEBUG] primer pago: concepto={pagos_pendientes[0]['concepto']} fecha_estimada={pagos_pendientes[0]['fecha_estimada']} monto={pagos_pendientes[0]['monto']}")
    week_start_s1 = today + timedelta(days=0)
    week_end_s1 = today + timedelta(days=7)
    s1_cobros = [c for c in cobros_pendientes if week_start_s1 <= c['fecha_estimada'] < week_end_s1]
    s1_pagos  = [p for p in pagos_pendientes  if week_start_s1 <= p['fecha_estimada'] < week_end_s1]
    logger.info(f"[CAL DEBUG] S1 ({week_start_s1} - {week_end_s1}): cobros={len(s1_cobros)} pagos={len(s1_pagos)}")

    # ── Asignar todo a semanas ──
    calendar_weeks = []
    for week_offset in range(weeks_ahead):
        week_start = today + timedelta(weeks=week_offset)
        week_end = week_start + timedelta(days=7)

        semana_cobros = [c for c in cobros_pendientes if week_start <= c['fecha_estimada'] < week_end]
        semana_pagos  = [p for p in pagos_pendientes  if week_start <= p['fecha_estimada'] < week_end]
        semana_proy   = [
            t for t in proyecciones
            if week_start.isoformat() <= (t.get('fecha_transaccion', '') or '')[:10] < week_end.isoformat()
        ]

        total_cobros   = sum(c['monto'] for c in semana_cobros)
        total_pagos    = sum(p['monto'] for p in semana_pagos)
        total_proy_ing = sum(t['monto'] for t in semana_proy if t.get('tipo_transaccion') == 'ingreso')
        total_proy_egr = sum(t['monto'] for t in semana_proy if t.get('tipo_transaccion') == 'egreso')

        calendar_weeks.append({
            'label': f'S{week_offset + 1}',
            'date_range': f'{week_start.strftime("%d/%m")} - {week_end.strftime("%d/%m")}',
            'week_start': week_start.isoformat(),
            'payments': {
                'cobranza_programada': semana_cobros,
                'pagos_programados': semana_pagos,
                'proyecciones_ingreso': [
                    {'concepto': t.get('concepto', ''), 'monto': t['monto']}
                    for t in semana_proy if t.get('tipo_transaccion') == 'ingreso'
                ],
                'proyecciones_egreso': [
                    {'concepto': t.get('concepto', ''), 'monto': t['monto']}
                    for t in semana_proy if t.get('tipo_transaccion') == 'egreso'
                ],
            },
            'totals': {
                'cobranza_programada': total_cobros,
                'pagos_programados': total_pagos,
                'proyecciones_ingreso': total_proy_ing,
                'proyecciones_egreso': total_proy_egr,
            },
            'total_ingresos': total_cobros + total_proy_ing,
            'total_egresos':  total_pagos  + total_proy_egr,
            'flujo_neto': (total_cobros + total_proy_ing) - (total_pagos + total_proy_egr),
        })

    return {
        'weeks': calendar_weeks,
        'categories': {
            'cobranza_programada': {'name': 'Cobranza Programada (CxC)', 'color': '#10B981', 'icon': '💰'},
            'pagos_programados':   {'name': 'Pagos Programados (CxP)',   'color': '#EF4444', 'icon': '📋'},
            'proyecciones_ingreso': {'name': 'Proyecciones Ingreso',     'color': '#3B82F6', 'icon': '📈'},
            'proyecciones_egreso':  {'name': 'Proyecciones Egreso',      'color': '#F59E0B', 'icon': '📉'},
        },
        'totals_by_category': {
            'cobranza_programada':  sum(c['monto'] for c in cobros_pendientes),
            'pagos_programados':    sum(p['monto'] for p in pagos_pendientes),
            'proyecciones_ingreso': sum(t['monto'] for t in proyecciones if t.get('tipo_transaccion') == 'ingreso'),
            'proyecciones_egreso':  sum(t['monto'] for t in proyecciones if t.get('tipo_transaccion') == 'egreso'),
        },
    }


async def calculate_concentration_kpis(company_id: str) -> dict:
    """Calculate client/vendor concentration KPIs"""
    # Get all collections grouped by client
    collections_by_client = await db.payments.aggregate([
        {'$match': {'company_id': company_id, 'tipo': 'cobro'}},
        {'$group': {
            '_id': '$beneficiario',
            'total': {'$sum': '$monto'},
            'pending': {'$sum': {'$cond': [{'$in': ['$estatus', ['pendiente', 'parcial']]}, {'$ifNull': ['$saldo_pendiente', '$monto']}, 0]}}
        }},
        {'$sort': {'total': -1}}
    ]).to_list(100)
    
    # Get all payments grouped by vendor
    payments_by_vendor = await db.payments.aggregate([
        {'$match': {'company_id': company_id, 'tipo': 'pago'}},
        {'$group': {
            '_id': '$beneficiario',
            'total': {'$sum': '$monto'},
            'pending': {'$sum': {'$cond': [{'$in': ['$estatus', ['pendiente', 'parcial']]}, {'$ifNull': ['$saldo_pendiente', '$monto']}, 0]}}
        }},
        {'$sort': {'total': -1}}
    ]).to_list(100)
    
    # Calculate totals
    total_collections = sum(c['total'] for c in collections_by_client)
    total_payments = sum(p['total'] for p in payments_by_vendor)
    total_pending_collections = sum(c['pending'] for c in collections_by_client)
    
    # Top 3 clients concentration
    top3_clients = collections_by_client[:3]
    top3_clients_total = sum(c['total'] for c in top3_clients)
    top3_clients_pct = (top3_clients_total / total_collections * 100) if total_collections > 0 else 0
    
    # Top 5 vendors concentration
    top5_vendors = payments_by_vendor[:5]
    top5_vendors_total = sum(v['total'] for v in top5_vendors)
    top5_vendors_pct = (top5_vendors_total / total_payments * 100) if total_payments > 0 else 0
    
    # Calculate weeks dependent on single client
    if collections_by_client and total_pending_collections > 0:
        top_client = collections_by_client[0]
        top_client_pending = top_client['pending']
        top_client_pct_pending = (top_client_pending / total_pending_collections * 100) if total_pending_collections > 0 else 0
        
        # Estimate weeks of dependency
        avg_weekly_collections = total_collections / 52  # Approximate annual to weekly
        weeks_dependent = top_client_pending / avg_weekly_collections if avg_weekly_collections > 0 else 0
    else:
        top_client_pct_pending = 0
        weeks_dependent = 0
    
    # Determine risk levels
    def get_risk_level(pct: float, thresholds: tuple) -> str:
        if pct >= thresholds[1]:
            return "high"
        elif pct >= thresholds[0]:
            return "medium"
        return "low"
    
    return {
        "top_3_clients": {
            "names": [(c['_id'] or '')[:25] or 'N/A' for c in top3_clients],
            "amounts": [c['total'] for c in top3_clients],
            "percentage": round(top3_clients_pct, 1),
            "risk_level": get_risk_level(top3_clients_pct, (50, 70)),
            "detail": f"Top 3 clientes representan {top3_clients_pct:.1f}% de ingresos"
        },
        "top_5_vendors": {
            "names": [(v['_id'] or '')[:25] or 'N/A' for v in top5_vendors],
            "amounts": [v['total'] for v in top5_vendors],
            "percentage": round(top5_vendors_pct, 1),
            "risk_level": get_risk_level(top5_vendors_pct, (60, 80)),
            "detail": f"Top 5 proveedores representan {top5_vendors_pct:.1f}% de egresos"
        },
        "single_client_dependency": {
            "client_name": (collections_by_client[0]['_id'] or '')[:30] or 'N/A' if collections_by_client else 'N/A',
            "pending_amount": collections_by_client[0]['pending'] if collections_by_client else 0,
            "percentage_of_pending": round(top_client_pct_pending, 1) if collections_by_client else 0,
            "weeks_dependent": round(weeks_dependent, 1),
            "risk_level": get_risk_level(top_client_pct_pending, (30, 50)),
            "detail": f"Dependes {weeks_dependent:.1f} semanas de un solo cliente" if weeks_dependent > 0 else "Sin dependencia crítica"
        }
    }


async def calculate_working_capital_intelligence(company_id: str) -> dict:
    """Calculate DSO, DPO, Cash Conversion Cycle and trends"""
    today = datetime.now(timezone.utc)
    
    # Get collections for DSO calculation
    # DSO = (Average Accounts Receivable / Total Credit Sales) * Number of Days
    all_collections = await db.payments.find(
        {'company_id': company_id, 'tipo': 'cobro'},
        {'_id': 0, 'monto': 1, 'fecha_pago': 1, 'fecha_vencimiento': 1, 'created_at': 1, 'estatus': 1, 'saldo_pendiente': 1}
    ).to_list(10000)
    
    # Get payments for DPO calculation
    all_payments = await db.payments.find(
        {'company_id': company_id, 'tipo': 'pago'},
        {'_id': 0, 'monto': 1, 'fecha_pago': 1, 'fecha_vencimiento': 1, 'created_at': 1, 'estatus': 1, 'saldo_pendiente': 1}
    ).to_list(10000)
    
    # Calculate DSO (Days Sales Outstanding)
    # DSO = días entre fecha de emisión (vencimiento) y fecha de cobro real
    collection_days = []
    for c in all_collections:
        if c.get('fecha_pago') and c.get('fecha_vencimiento'):
            try:
                due = safe_parse_date(c['fecha_vencimiento'])
                paid = safe_parse_date(c['fecha_pago'])
                if due and paid:
                    days = (paid - due).days
                    if -30 <= days <= 365:  # Negativo = cobró antes del vencimiento
                        collection_days.append(days)
            except:
                pass

    dso = sum(collection_days) / len(collection_days) if collection_days else 0

    # Calculate DPO (Days Payable Outstanding)
    # DPO = días entre fecha de vencimiento del proveedor y fecha de pago real
    payment_days = []
    for p in all_payments:
        if p.get('fecha_pago') and p.get('fecha_vencimiento'):
            try:
                due = safe_parse_date(p['fecha_vencimiento'])
                paid = safe_parse_date(p['fecha_pago'])
                if due and paid:
                    days = (paid - due).days
                    if -30 <= days <= 365:
                        payment_days.append(days)
            except:
                pass

    dpo = sum(payment_days) / len(payment_days) if payment_days else 0
    
    # Cash Conversion Cycle = DSO - DPO (simplified, without inventory)
    # Negative CCC means you're getting paid before you pay suppliers (good)
    ccc = dso - dpo
    
    # Calculate trends (compare last 30 days vs previous 30 days)
    thirty_days_ago = today - timedelta(days=30)
    sixty_days_ago = today - timedelta(days=60)
    
    recent_collections = [c for c in all_collections 
                         if c.get('created_at') and c['created_at'][:10] >= thirty_days_ago.isoformat()[:10]]
    older_collections = [c for c in all_collections 
                        if c.get('created_at') and sixty_days_ago.isoformat()[:10] <= c['created_at'][:10] < thirty_days_ago.isoformat()[:10]]
    
    # Calculate recent DSO trend
    recent_dso_days = []
    for c in recent_collections:
        if c.get('fecha_pago') and c.get('fecha_vencimiento'):
            try:
                due = safe_parse_date(c['fecha_vencimiento'])
                paid = safe_parse_date(c['fecha_pago'])
                if due and paid:
                    days = (paid - due).days
                    if -30 <= days <= 365:
                        recent_dso_days.append(days)
            except:
                pass

    recent_dso = sum(recent_dso_days) / len(recent_dso_days) if recent_dso_days else dso

    older_dso_days = []
    for c in older_collections:
        if c.get('fecha_pago') and c.get('fecha_vencimiento'):
            try:
                due = safe_parse_date(c['fecha_vencimiento'])
                paid = safe_parse_date(c['fecha_pago'])
                if due and paid:
                    days = (paid - due).days
                    if -30 <= days <= 365:
                        older_dso_days.append(days)
            except:
                pass

    older_dso = sum(older_dso_days) / len(older_dso_days) if older_dso_days else dso
    
    dso_trend = "improving" if recent_dso < older_dso else ("worsening" if recent_dso > older_dso else "stable")
    dso_change = recent_dso - older_dso
    
    # Health indicators
    def get_dso_health(days: float) -> str:
        if days <= 30:
            return "excellent"
        elif days <= 45:
            return "good"
        elif days <= 60:
            return "fair"
        return "poor"
    
    def get_ccc_health(days: float) -> str:
        if days <= 0:
            return "excellent"
        elif days <= 30:
            return "good"
        elif days <= 60:
            return "fair"
        return "poor"
    
    return {
        "dso": {
            "value": round(dso, 1),
            "label": "DSO (Días de Cobranza)",
            "description": f"En promedio, cobras en {dso:.0f} días",
            "health": get_dso_health(dso),
            "trend": dso_trend,
            "trend_value": round(dso_change, 1),
            "trend_description": f"{'↓ Mejorando' if dso_trend == 'improving' else '↑ Empeorando' if dso_trend == 'worsening' else '→ Estable'} ({abs(dso_change):.1f} días)"
        },
        "dpo": {
            "value": round(dpo, 1),
            "label": "DPO (Días de Pago)",
            "description": f"En promedio, pagas en {dpo:.0f} días",
            "health": "good" if dpo >= 30 else "fair",
            "trend": "stable",
            "trend_value": 0
        },
        "ccc": {
            "value": round(ccc, 1),
            "label": "Ciclo de Conversión de Efectivo",
            "description": f"{'Recibes dinero ' + str(abs(int(ccc))) + ' días antes de pagar' if ccc < 0 else 'Pagas ' + str(int(ccc)) + ' días antes de cobrar'}",
            "health": get_ccc_health(ccc),
            "is_positive": ccc <= 0,
            "interpretation": "Excelente: tu flujo es positivo" if ccc <= 0 else "Atención: necesitas capital de trabajo"
        },
        "summary": {
            "message": f"Tu ciclo de efectivo es de {ccc:.0f} días",
            "recommendation": "Mantén la estrategia actual" if ccc <= 0 else "Considera acelerar cobranza o negociar plazos con proveedores"
        }
    }


@router.get("/alerts")
async def get_alerts(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    weeks_ahead: int = Query(16)
):
    """Get only alerts"""
    company_id = await get_active_company_id(request, current_user)
    company = await db.companies.find_one({'id': company_id}, {'_id': 0})
    threshold = company.get('min_balance_threshold', 100000)
    
    return await calculate_alerts(company_id, threshold, weeks_ahead)


@router.get("/recommendations")
async def get_recommendations(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    weeks_ahead: int = Query(16)
):
    """Get only recommendations"""
    company_id = await get_active_company_id(request, current_user)
    return await generate_recommendations(company_id, weeks_ahead)


@router.get("/calendar")
async def get_calendar(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    weeks_ahead: int = Query(16)
):
    """Get treasury calendar"""
    company_id = await get_active_company_id(request, current_user)
    return await get_treasury_calendar(company_id, weeks_ahead)


@router.get("/working-capital")
async def get_working_capital(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Get working capital intelligence"""
    company_id = await get_active_company_id(request, current_user)
    return await calculate_working_capital_intelligence(company_id)


@router.get("/concentration")
async def get_concentration(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Get concentration KPIs"""
    company_id = await get_active_company_id(request, current_user)
    return await calculate_concentration_kpis(company_id)
