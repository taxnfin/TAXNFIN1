"""Cash flow initialization service"""
from datetime import datetime, timezone, timedelta

from core.database import db
from models.transaction import CashFlowWeek


async def initialize_cashflow_weeks(company_id: str):
    """Initialize 13 weeks of cashflow for a company"""
    existing = await db.cashflow_weeks.find_one({'company_id': company_id})
    if existing:
        return
    
    today = datetime.now(timezone.utc)
    start_of_week = today - timedelta(days=today.weekday())
    
    for i in range(13):
        week_start = start_of_week + timedelta(weeks=i)
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        week = CashFlowWeek(
            company_id=company_id,
            año=week_start.year,
            numero_semana=week_start.isocalendar()[1],
            fecha_inicio=week_start,
            fecha_fin=week_end
        )
        doc = week.model_dump()
        for field in ['fecha_inicio', 'fecha_fin', 'created_at']:
            doc[field] = doc[field].isoformat()
        await db.cashflow_weeks.insert_one(doc)
