"""KPI alert evaluation service.
Evaluates KPI alert rules against current financial metrics
and creates notifications when thresholds are breached."""
import logging
from typing import Dict, List, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def evaluate_kpi_alerts(db, company_id: str, metrics_data: Dict[str, Any], periodo: str) -> List[Dict]:
    """Evaluate all active KPI alert rules for a company against the given metrics.
    Returns list of triggered notifications."""
    
    rules = await db.kpi_alert_rules.find(
        {'company_id': company_id, 'is_active': True},
        {'_id': 0}
    ).to_list(100)
    
    if not rules:
        return []
    
    triggered = []
    metrics = metrics_data.get('metrics', {})
    
    for rule in rules:
        section = rule.get('metric_section', '')
        key = rule.get('metric_key', '')
        
        metric = metrics.get(section, {}).get(key, {})
        value = metric.get('value')
        
        if value is None:
            continue
        
        condition = rule.get('condition', 'below')
        threshold = rule.get('threshold', 0)
        breached = False
        
        if condition == 'below' and value < threshold:
            breached = True
        elif condition == 'above' and value > threshold:
            breached = True
        
        if not breached:
            continue
        
        # Check if we already sent a notification for this rule + period
        existing = await db.notifications.find_one({
            'company_id': company_id,
            'rule_id': rule['id'],
            'category': 'kpi',
            'title': {'$regex': periodo}
        }, {'_id': 0})
        
        if existing:
            continue
        
        label = rule.get('metric_label', key)
        cond_text = 'por debajo de' if condition == 'below' else 'por encima de'
        level = rule.get('level', 'warning')
        
        fmt_value = f"{value:.1f}%" if section in ('margins', 'returns', 'solvency') else f"{value:.2f}"
        fmt_threshold = f"{threshold:.1f}%" if section in ('margins', 'returns', 'solvency') else f"{threshold:.2f}"
        
        notification = {
            'id': None,  # Will be set by the route
            'company_id': company_id,
            'title': f"Alerta KPI [{periodo}]: {label}",
            'message': f"{label} está en {fmt_value}, {cond_text} el umbral configurado de {fmt_threshold}.",
            'level': level,
            'category': 'kpi',
            'metric_key': key,
            'metric_value': value,
            'rule_id': rule['id'],
            'read': False,
            'created_at': datetime.now(timezone.utc),
        }
        
        triggered.append(notification)
    
    return triggered
