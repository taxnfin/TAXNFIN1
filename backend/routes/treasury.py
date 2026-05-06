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
    weeks_ahead: int = Query(8, description="Number of weeks to analyze")
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
    company = await db.companies.find_one({'id': company_id}, {'_id': 0})
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
        {'company_id': company_id, 'activa': True},
        {'_id': 0}
    ).to_list(100)
    
    total_mxn = 0
    for acc in accounts:
        balance = acc.get('saldo_actual', 0) or 0
        currency = acc.get('moneda', 'MXN')
        if currency == 'MXN':
            total_mxn += balance
        elif currency == 'USD':
            total_mxn += balance * 17.5  # Approximate
        elif currency == 'EUR':
            total_mxn += balance * 19.0
    
    # Get pending collections and payments
    pending_collections = await db.payments.aggregate([
        {'$match': {'company_id': company_id, 'tipo': 'cobro', 'estatus': {'$in': ['pendiente', 'parcial']}}},
        {'$group': {'_id': None, 'total': {'$sum': '$saldo_pendiente'}}}
    ]).to_list(1)
    
    pending_payments = await db.payments.aggregate([
        {'$match': {'company_id': company_id, 'tipo': 'pago', 'estatus': {'$in': ['pendiente', 'parcial']}}},
        {'$group': {'_id': None, 'total': {'$sum': '$saldo_pendiente'}}}
    ]).to_list(1)
    
    cxc = pending_collections[0]['total'] if pending_collections else 0
    cxp = pending_payments[0]['total'] if pending_payments else 0
    
    return {
        "saldo_actual": total_mxn,
        "cuentas_por_cobrar": cxc,
        "cuentas_por_pagar": cxp,
        "flujo_neto_esperado": cxc - cxp,
        "posicion_proyectada": total_mxn + cxc - cxp
    }


async def calculate_alerts(company_id: str, threshold: float, weeks_ahead: int) -> List[dict]:
    """Calculate actionable alerts based on cash flow projections"""
    alerts = []
    today = datetime.now(timezone.utc)
    
    # Get pending payments grouped by week
    pending_payments = await db.payments.find(
        {'company_id': company_id, 'tipo': 'pago', 'estatus': {'$in': ['pendiente', 'parcial']}},
        {'_id': 0}
    ).to_list(5000)
    
    pending_collections = await db.payments.find(
        {'company_id': company_id, 'tipo': 'cobro', 'estatus': {'$in': ['pendiente', 'parcial']}},
        {'_id': 0}
    ).to_list(5000)
    
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
            p.get('saldo_pendiente', 0) for p in pending_collections
            if p.get('fecha_vencimiento') and 
            week_start.isoformat()[:10] <= p.get('fecha_vencimiento', '')[:10] < week_end.isoformat()[:10]
        )
        
        week_payments = sum(
            p.get('saldo_pendiente', 0) for p in pending_payments
            if p.get('fecha_vencimiento') and 
            week_start.isoformat()[:10] <= p.get('fecha_vencimiento', '')[:10] < week_end.isoformat()[:10]
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
        if collection.get('fecha_vencimiento'):
            try:
                due_date = safe_parse_date(collection['fecha_vencimiento'])
                if due_date.tzinfo is None:
                    due_date = due_date.replace(tzinfo=timezone.utc)
            except:
                continue
            days_until_due = (due_date - today).days
            amount = collection.get('saldo_pendiente', 0)
            
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
        if payment.get('fecha_vencimiento'):
            try:
                due_date = safe_parse_date(payment['fecha_vencimiento'])
                if due_date.tzinfo is None:
                    due_date = due_date.replace(tzinfo=timezone.utc)
            except:
                continue
            days_until_due = (due_date - today).days
            amount = payment.get('saldo_pendiente', 0)
            
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
            "message": f"Prioriza cobro a {top1.get('beneficiario', 'Cliente A')[:25]} (${top1.get('saldo_pendiente', 0):,.0f}) sobre {top2.get('beneficiario', 'Cliente B')[:25]} (${top2.get('saldo_pendiente', 0):,.0f})",
            "impact": f"+${top1.get('saldo_pendiente', 0):,.0f} MXN",
            "action": "contact_client",
            "entity_id": top1.get('id')
        })
    
    # Recommendation: Payments that can be rescheduled
    flexible_payments = [p for p in pending_payments if p.get('saldo_pendiente', 0) > 20000]
    flexible_payments.sort(key=lambda x: x.get('fecha_vencimiento', ''), reverse=True)
    
    if flexible_payments:
        payment = flexible_payments[0]
        recommendations.append({
            "type": "reschedule_payment",
            "priority": "medium",
            "icon": "🔄",
            "title": "Reprogramar Pago",
            "message": f"Evalúa mover pago a {payment.get('beneficiario', 'Proveedor')[:25]} 1 semana",
            "impact": f"Libera ${payment.get('saldo_pendiente', 0):,.0f} MXN temporalmente",
            "action": "reschedule",
            "entity_id": payment.get('id')
        })
    
    # Recommendation: Anticipated cash flow
    near_term_collections = [c for c in sorted_collections 
                            if c.get('fecha_vencimiento') and 
                            c.get('fecha_vencimiento', '')[:10] <= (today + timedelta(days=7)).isoformat()[:10]]
    
    total_near_term = sum(c.get('saldo_pendiente', 0) for c in near_term_collections)
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
    
    total_overdue = sum(c.get('saldo_pendiente', 0) for c in overdue_collections)
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
    """Get treasury calendar with fixed payments by category"""
    today = datetime.now(timezone.utc)
    
    # Get all pending payments
    pending_payments = await db.payments.find(
        {'company_id': company_id, 'tipo': 'pago', 'estatus': {'$in': ['pendiente', 'parcial']}},
        {'_id': 0}
    ).to_list(5000)
    
    # Categories to track
    categories = {
        "nomina": {"name": "Nómina", "icon": "👥", "keywords": ["nomina", "nómina", "sueldos", "salario", "payroll"]},
        "impuestos": {"name": "Impuestos", "icon": "🏛️", "keywords": ["iva", "isr", "isn", "imss", "infonavit", "impuesto", "sat", "tax"]},
        "creditos": {"name": "Créditos", "icon": "🏦", "keywords": ["credito", "crédito", "prestamo", "préstamo", "bank", "banco", "financ"]},
        "rentas": {"name": "Rentas", "icon": "🏢", "keywords": ["renta", "arrendamiento", "alquiler", "rent", "lease"]},
        "servicios": {"name": "Servicios Fijos", "icon": "⚡", "keywords": ["luz", "agua", "gas", "telefono", "internet", "cfe", "telmex"]},
        "otros": {"name": "Otros Pagos", "icon": "📋", "keywords": []}
    }
    
    def categorize_payment(payment: dict) -> str:
        concepto = (payment.get('concepto', '') + ' ' + payment.get('beneficiario', '')).lower()
        for cat_id, cat_info in categories.items():
            if cat_id == 'otros':
                continue
            for keyword in cat_info['keywords']:
                if keyword in concepto:
                    return cat_id
        return 'otros'
    
    # Build calendar by week and category
    calendar = {
        "weeks": [],
        "categories": categories,
        "totals_by_category": defaultdict(float)
    }
    
    for week_offset in range(weeks_ahead):
        week_start = today + timedelta(weeks=week_offset)
        week_end = week_start + timedelta(days=7)
        
        week_data = {
            "label": get_week_label(week_offset),
            "date_range": f"{week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m')}",
            "payments": defaultdict(list),
            "totals": defaultdict(float),
            "total": 0
        }
        
        for payment in pending_payments:
            if payment.get('fecha_vencimiento'):
                due_date = payment.get('fecha_vencimiento', '')[:10]
                if week_start.isoformat()[:10] <= due_date < week_end.isoformat()[:10]:
                    category = categorize_payment(payment)
                    amount = payment.get('saldo_pendiente', 0)
                    
                    week_data['payments'][category].append({
                        "beneficiario": payment.get('beneficiario', 'N/A')[:30],
                        "monto": amount,
                        "fecha": due_date
                    })
                    week_data['totals'][category] += amount
                    week_data['total'] += amount
                    calendar['totals_by_category'][category] += amount
        
        # Convert defaultdicts to regular dicts
        week_data['payments'] = dict(week_data['payments'])
        week_data['totals'] = dict(week_data['totals'])
        
        calendar['weeks'].append(week_data)
    
    calendar['totals_by_category'] = dict(calendar['totals_by_category'])
    
    return calendar


async def calculate_concentration_kpis(company_id: str) -> dict:
    """Calculate client/vendor concentration KPIs"""
    # Get all collections grouped by client
    collections_by_client = await db.payments.aggregate([
        {'$match': {'company_id': company_id, 'tipo': 'cobro'}},
        {'$group': {
            '_id': '$beneficiario',
            'total': {'$sum': '$monto'},
            'pending': {'$sum': {'$cond': [{'$in': ['$estatus', ['pendiente', 'parcial']]}, '$saldo_pendiente', 0]}}
        }},
        {'$sort': {'total': -1}}
    ]).to_list(100)
    
    # Get all payments grouped by vendor
    payments_by_vendor = await db.payments.aggregate([
        {'$match': {'company_id': company_id, 'tipo': 'pago'}},
        {'$group': {
            '_id': '$beneficiario',
            'total': {'$sum': '$monto'},
            'pending': {'$sum': {'$cond': [{'$in': ['$estatus', ['pendiente', 'parcial']]}, '$saldo_pendiente', 0]}}
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
            "names": [c['_id'][:25] if c['_id'] else 'N/A' for c in top3_clients],
            "amounts": [c['total'] for c in top3_clients],
            "percentage": round(top3_clients_pct, 1),
            "risk_level": get_risk_level(top3_clients_pct, (50, 70)),
            "detail": f"Top 3 clientes representan {top3_clients_pct:.1f}% de ingresos"
        },
        "top_5_vendors": {
            "names": [v['_id'][:25] if v['_id'] else 'N/A' for v in top5_vendors],
            "amounts": [v['total'] for v in top5_vendors],
            "percentage": round(top5_vendors_pct, 1),
            "risk_level": get_risk_level(top5_vendors_pct, (60, 80)),
            "detail": f"Top 5 proveedores representan {top5_vendors_pct:.1f}% de egresos"
        },
        "single_client_dependency": {
            "client_name": collections_by_client[0]['_id'][:30] if collections_by_client else 'N/A',
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
    # Average time it takes to collect payment
    collection_days = []
    for c in all_collections:
        if c.get('fecha_pago') and c.get('created_at'):
            try:
                created = safe_parse_date(c['created_at'])
                paid = safe_parse_date(c['fecha_pago'])
                days = (paid - created).days
                if 0 <= days <= 365:  # Reasonable range
                    collection_days.append(days)
            except:
                pass
    
    dso = sum(collection_days) / len(collection_days) if collection_days else 0
    
    # Calculate DPO (Days Payable Outstanding)
    # Average time it takes to pay suppliers
    payment_days = []
    for p in all_payments:
        if p.get('fecha_pago') and p.get('created_at'):
            try:
                created = safe_parse_date(p['created_at'])
                paid = safe_parse_date(p['fecha_pago'])
                days = (paid - created).days
                if 0 <= days <= 365:
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
    
    # Calculate recent DSO
    recent_dso_days = []
    for c in recent_collections:
        if c.get('fecha_pago') and c.get('created_at'):
            try:
                created = safe_parse_date(c['created_at'])
                paid = safe_parse_date(c['fecha_pago'])
                days = (paid - created).days
                if 0 <= days <= 365:
                    recent_dso_days.append(days)
            except:
                pass
    
    recent_dso = sum(recent_dso_days) / len(recent_dso_days) if recent_dso_days else dso
    
    older_dso_days = []
    for c in older_collections:
        if c.get('fecha_pago') and c.get('created_at'):
            try:
                created = safe_parse_date(c['created_at'])
                paid = safe_parse_date(c['fecha_pago'])
                days = (paid - created).days
                if 0 <= days <= 365:
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
    weeks_ahead: int = Query(8)
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
    weeks_ahead: int = Query(8)
):
    """Get only recommendations"""
    company_id = await get_active_company_id(request, current_user)
    return await generate_recommendations(company_id, weeks_ahead)


@router.get("/calendar")
async def get_calendar(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    weeks_ahead: int = Query(8)
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
