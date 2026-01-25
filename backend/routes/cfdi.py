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


@router.get("/summary")
async def get_cfdi_summary(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    moneda_vista: str = Query('MXN', description="Moneda para mostrar totales"),
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None
):
    """Get summary of CFDIs by type and status with currency conversion"""
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
    
    # Get company's base currency
    company = await db.companies.find_one({'id': company_id}, {'_id': 0, 'moneda_base': 1})
    moneda_base = company.get('moneda_base', 'MXN') if company else 'MXN'
    
    # Get FX rates
    rates_docs = await db.fx_rates.find({'company_id': company_id}).sort('fecha_vigencia', -1).to_list(100)
    rates = {'MXN': 1.0, 'USD': 17.50, 'EUR': 19.00}  # Defaults
    for r in rates_docs:
        moneda = r.get('moneda_cotizada') or r.get('moneda_origen')
        tasa = r.get('tipo_cambio') or r.get('tasa')
        if moneda and tasa:
            rates[moneda] = tasa
    
    # Calculate totals by currency and converted
    totals_by_currency = {'ingresos': {}, 'egresos': {}}
    totals_converted = {'ingresos': 0.0, 'egresos': 0.0}
    pendientes = 0
    conciliados = 0
    
    for c in cfdis:
        total = c.get('total', 0) or 0
        moneda = c.get('moneda', 'MXN') or 'MXN'
        tipo = 'ingresos' if c.get('tipo_cfdi') == 'ingreso' else 'egresos'
        
        # Sum by original currency
        if moneda not in totals_by_currency[tipo]:
            totals_by_currency[tipo][moneda] = 0
        totals_by_currency[tipo][moneda] += total
        
        # Convert to view currency
        if moneda == moneda_vista:
            totals_converted[tipo] += total
        elif moneda in rates and moneda_vista in rates:
            if moneda == 'MXN':
                converted = total / rates.get(moneda_vista, 1)
            elif moneda_vista == 'MXN':
                converted = total * rates.get(moneda, 1)
            else:
                # Cross rate
                to_mxn = total * rates.get(moneda, 1)
                converted = to_mxn / rates.get(moneda_vista, 1)
            totals_converted[tipo] += converted
        else:
            totals_converted[tipo] += total
        
        # Count reconciliation status
        if c.get('estado_conciliacion') == 'conciliado':
            conciliados += 1
        else:
            pendientes += 1
    
    return {
        'moneda_vista': moneda_vista,
        'moneda_base': moneda_base,
        'totales_por_moneda': totals_by_currency,
        'totales_convertidos': {
            'ingresos': round(totals_converted['ingresos'], 2),
            'egresos': round(totals_converted['egresos'], 2)
        },
        'balance_convertido': round(totals_converted['ingresos'] - totals_converted['egresos'], 2),
        'tipos_cambio_usados': rates,
        'total_cfdis': len(cfdis),
        'conciliados': conciliados,
        'pendientes': pendientes,
        'porcentaje_conciliado': round(conciliados / len(cfdis) * 100, 1) if cfdis else 0
    }


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
    request: Request, 
    current_user: Dict = Depends(get_current_user),
    category_id: Optional[str] = Query(None),
    subcategory_id: Optional[str] = Query(None),
    vendor_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None)
):
    """Assign category and subcategory to a CFDI"""
    company_id = await get_active_company_id(request, current_user)
    
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    update_data = {}
    if category_id:
        update_data['category_id'] = category_id
    if subcategory_id:
        update_data['subcategory_id'] = subcategory_id
    if vendor_id:
        update_data['vendor_id'] = vendor_id
    if customer_id:
        update_data['customer_id'] = customer_id
    
    if update_data:
        await db.cfdis.update_one({'id': cfdi_id}, {'$set': update_data})
        await audit_log(company_id, 'CFDI', cfdi_id, 'CATEGORIZE', current_user['id'], update_data)
    
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
