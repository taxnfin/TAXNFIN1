"""Audit logging service"""
from typing import Optional, Dict
from datetime import datetime, timezone

from core.database import db
from models.audit import AuditLog


async def audit_log(
    company_id: str, 
    entidad: str, 
    entity_id: str, 
    accion: str, 
    user_id: str, 
    datos_anteriores: Optional[Dict] = None, 
    datos_nuevos: Optional[Dict] = None
):
    """Create an audit log entry"""
    log = AuditLog(
        company_id=company_id,
        entidad=entidad,
        entity_id=entity_id,
        accion=accion,
        user_id=user_id,
        datos_anteriores=datos_anteriores,
        datos_nuevos=datos_nuevos
    )
    doc = log.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.audit_logs.insert_one(doc)
