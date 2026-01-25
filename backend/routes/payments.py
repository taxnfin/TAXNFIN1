"""Payment routes"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
import uuid

from core.database import db
from core.auth import get_current_user, get_active_company_id
from models.payment import Payment, PaymentCreate
from services.audit import audit_log

router = APIRouter(prefix="/payments")


@router.post("", response_model=Payment)
async def create_payment(payment_data: PaymentCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    """Create a new payment"""
    company_id = await get_active_company_id(request, current_user)
    payment = Payment(company_id=company_id, **payment_data.model_dump())
    doc = payment.model_dump()
    
    # Automatically capture historical exchange rate for non-MXN currencies
    if doc.get('moneda') and doc['moneda'] != 'MXN' and not doc.get('tipo_cambio_historico'):
        rate = await db.fx_rates.find_one(
            {'company_id': company_id, '$or': [
                {'moneda_cotizada': doc['moneda']},
                {'moneda_origen': doc['moneda']}
            ]},
            {'_id': 0},
            sort=[('fecha_vigencia', -1)]
        )
        if rate:
            doc['tipo_cambio_historico'] = rate.get('tipo_cambio') or rate.get('tasa') or 1
        else:
            default_rates = {'USD': 17.50, 'EUR': 19.00}
            doc['tipo_cambio_historico'] = default_rates.get(doc['moneda'], 1)
    
    # If payment is "Real", automatically mark as completed
    # Only set fecha_pago if not already provided (use fecha_vencimiento as fallback)
    if doc.get('es_real') == True:
        doc['estatus'] = 'completado'
        if not doc.get('fecha_pago'):
            doc['fecha_pago'] = doc.get('fecha_vencimiento') or datetime.now(timezone.utc).isoformat()
    
    for field in ['fecha_vencimiento', 'created_at']:
        if doc.get(field):
            doc[field] = doc[field].isoformat()
    if doc.get('fecha_pago') and not isinstance(doc['fecha_pago'], str):
        doc['fecha_pago'] = doc['fecha_pago'].isoformat()
    
    await db.payments.insert_one(doc)
    
    # If payment is real and linked to a CFDI, update the CFDI's collected/paid amount
    if doc.get('es_real') == True and doc.get('cfdi_id'):
        cfdi = await db.cfdis.find_one({'id': doc['cfdi_id']}, {'_id': 0})
        if cfdi:
            if doc['tipo'] == 'cobro':
                current_cobrado = cfdi.get('monto_cobrado', 0) or 0
                new_cobrado = current_cobrado + doc['monto']
                await db.cfdis.update_one(
                    {'id': doc['cfdi_id']},
                    {'$set': {'monto_cobrado': new_cobrado}}
                )
            else:
                current_pagado = cfdi.get('monto_pagado', 0) or 0
                new_pagado = current_pagado + doc['monto']
                await db.cfdis.update_one(
                    {'id': doc['cfdi_id']},
                    {'$set': {'monto_pagado': new_pagado}}
                )
    
    await audit_log(company_id, 'Payment', payment.id, 'CREATE', current_user['id'])
    return payment


@router.get("")
async def list_payments(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    tipo: Optional[str] = Query(None, description="cobro o pago"),
    estatus: Optional[str] = Query(None),
    es_real: Optional[str] = Query(None, description="real o proyeccion"),
    fecha_desde: Optional[str] = Query(None),
    fecha_hasta: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    skip: int = Query(0, ge=0)
):
    """List payments with optional filters"""
    company_id = await get_active_company_id(request, current_user)
    
    query = {'company_id': company_id}
    if tipo:
        query['tipo'] = tipo
    if estatus:
        query['estatus'] = estatus
    if es_real == 'real':
        query['es_real'] = True
    elif es_real == 'proyeccion':
        query['es_real'] = False
    if fecha_desde:
        query['fecha_vencimiento'] = {'$gte': fecha_desde}
    if fecha_hasta:
        if 'fecha_vencimiento' in query:
            query['fecha_vencimiento']['$lte'] = fecha_hasta
        else:
            query['fecha_vencimiento'] = {'$lte': fecha_hasta}
    
    payments = await db.payments.find(query, {'_id': 0}).sort('fecha_vencimiento', -1).skip(skip).limit(limit).to_list(limit)
    
    for p in payments:
        for field in ['fecha_vencimiento', 'fecha_pago', 'created_at']:
            if p.get(field) and isinstance(p[field], str):
                try:
                    p[field] = datetime.fromisoformat(p[field])
                except:
                    pass
    
    return payments


# NOTE: /summary endpoint is handled by server.py with more complete CFDI-based logic
# The basic summary logic was moved here but server.py version uses CFDI data for accurate calculations


@router.post("/{payment_id}/complete")
async def complete_payment(payment_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Mark a payment as completed"""
    company_id = await get_active_company_id(request, current_user)
    
    payment = await db.payments.find_one({'id': payment_id, 'company_id': company_id}, {'_id': 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    
    await db.payments.update_one(
        {'id': payment_id},
        {'$set': {
            'estatus': 'completado',
            'fecha_pago': datetime.now(timezone.utc).isoformat()
        }}
    )
    
    await audit_log(company_id, 'Payment', payment_id, 'COMPLETE', current_user['id'])
    return {'status': 'success', 'message': 'Pago marcado como completado'}


@router.delete("/{payment_id}")
async def delete_payment(payment_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Delete a payment"""
    company_id = await get_active_company_id(request, current_user)
    
    payment = await db.payments.find_one({'id': payment_id, 'company_id': company_id}, {'_id': 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    
    await db.payments.delete_one({'id': payment_id})
    await audit_log(company_id, 'Payment', payment_id, 'DELETE', current_user['id'])
    return {'status': 'success', 'message': 'Pago eliminado'}


@router.delete("/bulk/all")
async def delete_all_payments(request: Request, current_user: Dict = Depends(get_current_user)):
    """Delete ALL payments for the current company"""
    company_id = await get_active_company_id(request, current_user)
    
    result = await db.payments.delete_many({'company_id': company_id})
    
    await audit_log(company_id, 'Payment', 'BULK_DELETE', 'DELETE', current_user['id'], 
                    {'count': result.deleted_count, 'action': 'delete_all_payments'})
    
    return {
        'status': 'success',
        'deleted_count': result.deleted_count,
        'message': f'Se eliminaron {result.deleted_count} pagos/cobranzas'
    }
