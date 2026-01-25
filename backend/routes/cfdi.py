"""CFDI routes - Electronic invoice management"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id
from models.cfdi import CFDI
from services.audit import audit_log

router = APIRouter(prefix="/cfdi")
logger = logging.getLogger(__name__)


@router.get("", response_model=List[CFDI])
async def list_cfdis(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    limit: int = Query(100, le=1000),
    skip: int = Query(0, ge=0)
):
    """List all CFDIs for the current company"""
    company_id = await get_active_company_id(request, current_user)
    
    cfdis = await db.cfdis.find(
        {'company_id': company_id},
        {'_id': 0, 'xml_original': 0}
    ).sort('fecha_emision', -1).skip(skip).limit(limit).to_list(limit)
    
    for c in cfdis:
        for field in ['fecha_emision', 'fecha_timbrado', 'created_at']:
            if isinstance(c.get(field), str):
                c[field] = datetime.fromisoformat(c[field])
    return cfdis


@router.get("/{cfdi_id}")
async def get_cfdi(cfdi_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Get a single CFDI by ID"""
    company_id = await get_active_company_id(request, current_user)
    
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    for field in ['fecha_emision', 'fecha_timbrado', 'created_at']:
        if isinstance(cfdi.get(field), str):
            cfdi[field] = datetime.fromisoformat(cfdi[field])
    
    return cfdi


@router.delete("/{cfdi_id}")
async def delete_cfdi(cfdi_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Delete a CFDI"""
    company_id = await get_active_company_id(request, current_user)
    
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    # Delete associated payments and reconciliations
    await db.payments.delete_many({'cfdi_id': cfdi_id, 'company_id': company_id})
    await db.reconciliations.delete_many({'cfdi_id': cfdi_id, 'company_id': company_id})
    
    await db.cfdis.delete_one({'id': cfdi_id, 'company_id': company_id})
    await audit_log(company_id, 'CFDI', cfdi_id, 'DELETE', current_user['id'])
    
    return {'status': 'success', 'message': 'CFDI eliminado correctamente'}


@router.put("/{cfdi_id}/categorize")
async def categorize_cfdi(
    cfdi_id: str, 
    data: dict, 
    request: Request, 
    current_user: Dict = Depends(get_current_user)
):
    """Assign category and subcategory to a CFDI"""
    company_id = await get_active_company_id(request, current_user)
    
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    category_id = data.get('category_id')
    subcategory_id = data.get('subcategory_id')
    
    update_data = {}
    if category_id:
        update_data['category_id'] = category_id
    if subcategory_id:
        update_data['subcategory_id'] = subcategory_id
    
    if update_data:
        await db.cfdis.update_one({'id': cfdi_id}, {'$set': update_data})
        await audit_log(company_id, 'CFDI', cfdi_id, 'CATEGORIZE', current_user['id'], 
                        {'category_id': category_id, 'subcategory_id': subcategory_id})
    
    return {'status': 'success', 'message': 'CFDI categorizado correctamente'}


@router.put("/{cfdi_id}/reconciliation-status")
async def update_cfdi_reconciliation_status(
    cfdi_id: str,
    data: dict,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Update the reconciliation status of a CFDI"""
    company_id = await get_active_company_id(request, current_user)
    
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    estado = data.get('estado_conciliacion', 'pendiente')
    if estado not in ['pendiente', 'conciliado', 'no_conciliable']:
        raise HTTPException(status_code=400, detail="Estado inválido")
    
    await db.cfdis.update_one({'id': cfdi_id}, {'$set': {'estado_conciliacion': estado}})
    await audit_log(company_id, 'CFDI', cfdi_id, 'UPDATE_STATUS', current_user['id'], {'estado': estado})
    
    return {'status': 'success', 'message': f'Estado actualizado a {estado}'}


@router.put("/{cfdi_id}/notes")
async def update_cfdi_notes(
    cfdi_id: str,
    data: dict,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Update notes for a CFDI"""
    company_id = await get_active_company_id(request, current_user)
    
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    notas = data.get('notas', '')
    
    await db.cfdis.update_one({'id': cfdi_id}, {'$set': {'notas': notas}})
    await audit_log(company_id, 'CFDI', cfdi_id, 'UPDATE_NOTES', current_user['id'])
    
    return {'status': 'success', 'message': 'Notas actualizadas'}


@router.get("/summary")
async def get_cfdi_summary(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None
):
    """Get summary of CFDIs by type and status"""
    company_id = await get_active_company_id(request, current_user)
    
    query = {'company_id': company_id}
    if fecha_desde or fecha_hasta:
        query['fecha_emision'] = {}
        if fecha_desde:
            query['fecha_emision']['$gte'] = fecha_desde
        if fecha_hasta:
            query['fecha_emision']['$lte'] = fecha_hasta + 'T23:59:59'
    
    # Get all CFDIs
    cfdis = await db.cfdis.find(query, {'_id': 0, 'xml_original': 0}).to_list(10000)
    
    # Calculate summary
    total_ingresos = 0
    total_egresos = 0
    count_ingresos = 0
    count_egresos = 0
    pendientes = 0
    conciliados = 0
    
    for c in cfdis:
        total = c.get('total', 0)
        if c.get('tipo_cfdi') == 'ingreso':
            total_ingresos += total
            count_ingresos += 1
        else:
            total_egresos += total
            count_egresos += 1
        
        if c.get('estado_conciliacion') == 'conciliado':
            conciliados += 1
        else:
            pendientes += 1
    
    return {
        'total_cfdis': len(cfdis),
        'ingresos': {
            'count': count_ingresos,
            'total': round(total_ingresos, 2)
        },
        'egresos': {
            'count': count_egresos,
            'total': round(total_egresos, 2)
        },
        'conciliados': conciliados,
        'pendientes': pendientes,
        'porcentaje_conciliado': round(conciliados / len(cfdis) * 100, 1) if cfdis else 0
    }
