"""Notification and KPI alert rules routes"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import uuid

from core.database import db
from core.auth import get_current_user
from models.notification import KpiAlertRule, KpiAlertRuleCreate, Notification
from services.kpi_alerts import evaluate_kpi_alerts

router = APIRouter()


# ===== NOTIFICATION ENDPOINTS =====

@router.get("/notifications")
async def get_notifications(current_user: Dict = Depends(get_current_user)):
    """Get all notifications for user's company, most recent first"""
    notifications = await db.notifications.find(
        {'company_id': current_user['company_id']},
        {'_id': 0}
    ).sort('created_at', -1).to_list(100)
    
    for n in notifications:
        if isinstance(n.get('created_at'), datetime):
            n['created_at'] = n['created_at'].isoformat()
    
    return notifications


@router.get("/notifications/unread-count")
async def get_unread_count(current_user: Dict = Depends(get_current_user)):
    """Get count of unread notifications"""
    count = await db.notifications.count_documents({
        'company_id': current_user['company_id'],
        'read': False
    })
    return {'count': count}


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: Dict = Depends(get_current_user)):
    """Mark a single notification as read"""
    result = await db.notifications.update_one(
        {'id': notification_id, 'company_id': current_user['company_id']},
        {'$set': {'read': True}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    return {'status': 'ok'}


@router.put("/notifications/read-all")
async def mark_all_read(current_user: Dict = Depends(get_current_user)):
    """Mark all notifications as read"""
    result = await db.notifications.update_many(
        {'company_id': current_user['company_id'], 'read': False},
        {'$set': {'read': True}}
    )
    return {'status': 'ok', 'updated': result.modified_count}


@router.delete("/notifications/{notification_id}")
async def delete_notification(notification_id: str, current_user: Dict = Depends(get_current_user)):
    """Delete a notification"""
    result = await db.notifications.delete_one({
        'id': notification_id,
        'company_id': current_user['company_id']
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    return {'status': 'ok'}


# ===== KPI ALERT RULES =====

@router.get("/kpi-alert-rules")
async def get_alert_rules(current_user: Dict = Depends(get_current_user)):
    """Get all KPI alert rules for company"""
    rules = await db.kpi_alert_rules.find(
        {'company_id': current_user['company_id']},
        {'_id': 0}
    ).sort('created_at', -1).to_list(100)
    
    for r in rules:
        if isinstance(r.get('created_at'), datetime):
            r['created_at'] = r['created_at'].isoformat()
    
    return rules


@router.post("/kpi-alert-rules")
async def create_alert_rule(rule_data: KpiAlertRuleCreate, current_user: Dict = Depends(get_current_user)):
    """Create a new KPI alert rule"""
    rule = KpiAlertRule(
        company_id=current_user['company_id'],
        metric_key=rule_data.metric_key,
        metric_section=rule_data.metric_section,
        metric_label=rule_data.metric_label,
        condition=rule_data.condition,
        threshold=rule_data.threshold,
        level=rule_data.level,
        created_by=current_user['id'],
    )
    doc = rule.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.kpi_alert_rules.insert_one(doc)
    del doc['_id']
    return doc


@router.put("/kpi-alert-rules/{rule_id}")
async def update_alert_rule(rule_id: str, rule_data: KpiAlertRuleCreate, current_user: Dict = Depends(get_current_user)):
    """Update a KPI alert rule"""
    result = await db.kpi_alert_rules.update_one(
        {'id': rule_id, 'company_id': current_user['company_id']},
        {'$set': {
            'metric_key': rule_data.metric_key,
            'metric_section': rule_data.metric_section,
            'metric_label': rule_data.metric_label,
            'condition': rule_data.condition,
            'threshold': rule_data.threshold,
            'level': rule_data.level,
        }}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return {'status': 'ok'}


@router.put("/kpi-alert-rules/{rule_id}/toggle")
async def toggle_alert_rule(rule_id: str, current_user: Dict = Depends(get_current_user)):
    """Toggle a KPI alert rule active/inactive"""
    rule = await db.kpi_alert_rules.find_one(
        {'id': rule_id, 'company_id': current_user['company_id']},
        {'_id': 0}
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    
    new_status = not rule.get('is_active', True)
    await db.kpi_alert_rules.update_one(
        {'id': rule_id},
        {'$set': {'is_active': new_status}}
    )
    return {'status': 'ok', 'is_active': new_status}


@router.delete("/kpi-alert-rules/{rule_id}")
async def delete_alert_rule(rule_id: str, current_user: Dict = Depends(get_current_user)):
    """Delete a KPI alert rule"""
    result = await db.kpi_alert_rules.delete_one({
        'id': rule_id,
        'company_id': current_user['company_id']
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return {'status': 'ok'}


# ===== TRIGGER EVALUATION =====

@router.post("/kpi-alert-rules/evaluate/{periodo}")
async def trigger_evaluation(periodo: str, current_user: Dict = Depends(get_current_user)):
    """Manually trigger KPI evaluation for a specific period.
    This is also called automatically when financial statements are uploaded."""
    from routes.financial_statements import calculate_financial_metrics
    
    company_id = current_user['company_id']
    
    # Get the financial statement for this period
    fs = await db.financial_statements.find_one(
        {'company_id': company_id, 'periodo': periodo},
        {'_id': 0}
    )
    if not fs:
        raise HTTPException(status_code=404, detail="No hay estados financieros para este período")
    
    # Compute metrics
    income_data = fs.get('datos', {}) if fs.get('tipo') == 'estado_resultados' else {}
    balance_data = {}
    
    # We need both income statement and balance sheet
    inc = await db.financial_statements.find_one({'company_id': company_id, 'tipo': 'estado_resultados', 'periodo': periodo}, {'_id': 0})
    bal = await db.financial_statements.find_one({'company_id': company_id, 'tipo': 'balance_general', 'periodo': periodo}, {'_id': 0})
    
    income_data = inc.get('datos', {}) if inc else {}
    balance_data = bal.get('datos', {}) if bal else {}
    
    metrics_data = {'metrics': calculate_financial_metrics(income_data, balance_data)}
    
    # Evaluate rules
    triggered = await evaluate_kpi_alerts(db, company_id, metrics_data, periodo)
    
    # Save triggered notifications
    saved = 0
    for notif in triggered:
        notif['id'] = str(uuid.uuid4())
        notif['created_at'] = notif['created_at'].isoformat()
        await db.notifications.insert_one(notif)
        saved += 1
    
    return {
        'status': 'ok',
        'rules_evaluated': await db.kpi_alert_rules.count_documents({'company_id': company_id, 'is_active': True}),
        'notifications_created': saved
    }
