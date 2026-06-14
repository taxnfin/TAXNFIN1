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
from routes.cashflow import get_semanas_data

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


async def get_treasury_calendar(company_id: str, weeks_ahead: int = 52) -> dict:
    """Get treasury calendar — usa EXACTAMENTE los mismos datos que el Cash Flow."""
    semanas = await get_semanas_data(company_id, weeks_ahead)

    calendar_weeks = []
    for w in semanas:
        calendar_weeks.append({
            'label': w['label'],
            'date_range': w['date_range'],
            'week_start': w['fecha_inicio'],
            'week_end': w['fecha_fin'],
            'numero_semana': w['numero_semana'],
            'es_real': w.get('es_real', False),
            'total_ingresos': w['total_ingresos'],
            'total_egresos': w['total_egresos'],
            'flujo_neto': w['flujo_neto'],
            'notas': w.get('notas', ''),
            'id': w.get('id', ''),
            'payments': {
                'cobranza_programada': w.get('ingresos_detalle', []),
                'pagos_programados': w.get('egresos_detalle', []),
            },
            'top_ingresos': w.get('top_ingresos', []),
            'top_egresos': w.get('top_egresos', []),
        })

    return {
        'weeks': calendar_weeks,
        'categories': {
            'cobranza_programada': {'name': 'Cobranza Programada (CxC)', 'color': '#10B981', 'icon': '💰'},
            'pagos_programados': {'name': 'Pagos Programados (CxP)', 'color': '#EF4444', 'icon': '📋'},
        },
        'totals_by_category': {
            'cobranza_programada': sum(w['total_ingresos'] for w in calendar_weeks),
            'pagos_programados': sum(w['total_egresos'] for w in calendar_weeks),
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


async def calculate_working_capital_intelligence(company_id: str) -> Dict:
    # DSO desde CFDIs emitidos (ingresos)
    cfdis_ingreso = await db.cfdis.find(
        {'company_id': company_id, 'tipo_cfdi': {'$in': ['I', 'ingreso']}},
        {'_id': 0, 'fecha_emision': 1, 'total': 1, 'estado_conciliacion': 1}
    ).to_list(1000)

    # DPO desde CFDIs recibidos (egresos)
    cfdis_egreso = await db.cfdis.find(
        {'company_id': company_id, 'tipo_cfdi': {'$in': ['E', 'egreso']}},
        {'_id': 0, 'fecha_emision': 1, 'total': 1, 'estado_conciliacion': 1}
    ).to_list(1000)

    # CxC pendiente (para DSO)
    cxc_doc = await db.contalink_cache.find_one({'key': f'cxc_{company_id}_latest'})
    cxc_total = 0
    if cxc_doc:
        raw = cxc_doc.get('data', {})
        items = next((v for v in raw.values() if isinstance(v, list)), []) if isinstance(raw, dict) else []
        cxc_total = sum(float(i.get('saldo_pendiente') or i.get('saldo') or 0) for i in items)

    # CxP pendiente (para DPO)
    cxp_doc = await db.contalink_cache.find_one({'key': f'cxp_{company_id}_latest'})
    cxp_total = 0
    if cxp_doc:
        raw = cxp_doc.get('data', {})
        items = next((v for v in raw.values() if isinstance(v, list)), []) if isinstance(raw, dict) else []
        cxp_total = sum(float(i.get('saldo_pendiente') or i.get('saldo') or 0) for i in items)

    # Ventas promedio diarias (últimos 90 días)
    today = datetime.now(timezone.utc)
    hace_90 = today - timedelta(days=90)

    ventas_90 = []
    compras_90 = []
    for c in cfdis_ingreso:
        fe = c.get('fecha_emision', '')
        if fe:
            try:
                fd = datetime.fromisoformat(str(fe).replace('Z', '+00:00'))
                if fd.tzinfo is None:
                    fd = fd.replace(tzinfo=timezone.utc)
                if fd >= hace_90:
                    ventas_90.append(float(c.get('total', 0) or 0))
            except Exception:
                pass

    for c in cfdis_egreso:
        fe = c.get('fecha_emision', '')
        if fe:
            try:
                fd = datetime.fromisoformat(str(fe).replace('Z', '+00:00'))
                if fd.tzinfo is None:
                    fd = fd.replace(tzinfo=timezone.utc)
                if fd >= hace_90:
                    compras_90.append(float(c.get('total', 0) or 0))
            except Exception:
                pass

    ventas_diarias = sum(ventas_90) / 90 if ventas_90 else 1
    compras_diarias = sum(compras_90) / 90 if compras_90 else 1

    dso = round(cxc_total / ventas_diarias) if ventas_diarias > 0 else 0
    dpo = round(cxp_total / compras_diarias) if compras_diarias > 0 else 0
    ccc = dso - dpo

    # Generar análisis IA
    try:
        import anthropic, os
        client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))
        prompt = f"""Eres un CFO experto en empresas mexicanas. Analiza estos indicadores de capital de trabajo:

DSO (Días de Cobranza): {dso} días — cobras en promedio en {dso} días
DPO (Días de Pago): {dpo} días — pagas en promedio en {dpo} días
CCC (Ciclo de Conversión): {ccc} días
CxC pendiente: ${cxc_total:,.0f}
CxP pendiente: ${cxp_total:,.0f}
Ventas últimos 90 días: ${sum(ventas_90):,.0f}
Compras últimos 90 días: ${sum(compras_90):,.0f}

Datos tomados de: CFDIs de los últimos 90 días y saldos del Aging de Contalink.

Proporciona un análisis ejecutivo en español de máximo 120 palabras que explique:
1. Qué significan estos números para la empresa
2. Si el DSO/DPO es bueno o malo para su industria
3. Una recomendación accionable concreta"""

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}]
        )
        ai_analysis = msg.content[0].text
    except Exception:
        ai_analysis = (
            f"DSO de {dso} días indica que tus clientes tardan en pagar. "
            f"Con DPO de {dpo} días, el ciclo neto es de {ccc} días. "
            f"Recomendación: implementar descuentos por pronto pago para reducir el DSO."
        )

    return {
        'dso': {
            'value': dso,
            'label': 'DSO (Días de Cobranza)',
            'description': f'En promedio, cobras en {dso} días',
            'status': 'good' if dso < 30 else 'warning' if dso < 60 else 'bad',
            'trend': '→ Estable',
        },
        'dpo': {
            'value': dpo,
            'label': 'DPO (Días de Pago)',
            'description': f'En promedio, pagas en {dpo} días',
            'status': 'good' if dpo > 30 else 'warning',
            'trend': '→ Estable',
        },
        'ccc': {
            'value': ccc,
            'label': 'Ciclo de Conversión',
            'description': f'{"Cobras" if ccc > 0 else "Pagas"} {abs(ccc)} días {"antes de cobrar" if ccc > 0 else "después de cobrar"}',
            'status': 'good' if ccc <= 0 else 'warning' if ccc < 30 else 'bad',
        },
        'summary': f'Tu ciclo de efectivo es de {abs(ccc)} días. {"Optimiza cobranza." if ccc > 30 else "Mantén la estrategia actual."}',
        'raw': {
            'cxc_total': cxc_total,
            'cxp_total': cxp_total,
            'ventas_90_dias': sum(ventas_90),
            'compras_90_dias': sum(compras_90),
        },
        'ai_analysis': ai_analysis,
        'data_source': 'CFDIs últimos 90 días + Aging Contalink',
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


@router.patch("/weeks/{week_id}/notas")
async def update_week_notas(
    week_id: str,
    data: dict,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    company_id = await get_active_company_id(request, current_user)
    await db.cashflow_weeks.update_one(
        {'id': week_id, 'company_id': company_id},
        {'$set': {'notas': data.get('notas', '')}}
    )
    return {'status': 'success'}


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
