"""Payment routes with full CFDI reversal logic"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
import logging
import uuid

from core.database import db
from core.auth import get_current_user, get_active_company_id
from models.payment import Payment, PaymentCreate
from services.audit import audit_log

router = APIRouter(prefix="/payments")
logger = logging.getLogger(__name__)


@router.post("", response_model=Payment)
async def create_payment(payment_data: PaymentCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    """Create a new payment with automatic CFDI amount updates and category inheritance"""
    company_id = await get_active_company_id(request, current_user)
    payment = Payment(company_id=company_id, **payment_data.model_dump())
    doc = payment.model_dump()
    
    # If linked to a CFDI, INHERIT category, subcategory, and UUID from the CFDI
    if doc.get('cfdi_id'):
        cfdi = await db.cfdis.find_one({'id': doc['cfdi_id']}, {'_id': 0})
        if cfdi:
            # Inherit category and subcategory from CFDI if not already set
            if not doc.get('category_id') and cfdi.get('category_id'):
                doc['category_id'] = cfdi['category_id']
            if not doc.get('subcategory_id') and cfdi.get('subcategory_id'):
                doc['subcategory_id'] = cfdi['subcategory_id']
            # Store CFDI UUID for reference
            if cfdi.get('uuid'):
                doc['cfdi_uuid'] = cfdi['uuid']
            # Set emisor/receptor info
            if cfdi.get('emisor_nombre'):
                doc['cfdi_emisor'] = cfdi['emisor_nombre']
            if cfdi.get('receptor_nombre'):
                doc['cfdi_receptor'] = cfdi['receptor_nombre']
            logger.info(f"Payment inheriting from CFDI {doc['cfdi_id']}: cat={doc.get('category_id')}, subcat={doc.get('subcategory_id')}")
    
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
                logger.info(f"Auto-completed payment: Updated CFDI {doc['cfdi_id']} monto_cobrado: {current_cobrado} -> {new_cobrado}")
            else:
                current_pagado = cfdi.get('monto_pagado', 0) or 0
                new_pagado = current_pagado + doc['monto']
                await db.cfdis.update_one(
                    {'id': doc['cfdi_id']},
                    {'$set': {'monto_pagado': new_pagado}}
                )
                logger.info(f"Auto-completed payment: Updated CFDI {doc['cfdi_id']} monto_pagado: {current_pagado} -> {new_pagado}")
    
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
            if isinstance(p.get(field), str):
                p[field] = datetime.fromisoformat(p[field])
    return payments


@router.post("/backfill-from-cfdis")
async def backfill_payments_from_cfdis(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    Backfill payments desde CFDIs que ya tienen monto_cobrado/monto_pagado > 0
    pero no tienen un payment registrado en la colección payments.
    Ejecutar UNA SOLA VEZ. Es idempotente (no crea duplicados).
    """
    company_id = await get_active_company_id(request, current_user)

    cfdis = await db.cfdis.find(
        {
            'company_id': company_id,
            'estado_cancelacion': {'$ne': 'cancelado'},
            '$or': [
                {'monto_cobrado': {'$gt': 0.01}},
                {'monto_pagado': {'$gt': 0.01}}
            ]
        },
        {'_id': 0}
    ).to_list(10000)

    creados = 0
    omitidos = 0
    errores = []

    for cfdi in cfdis:
        try:
            cfdi_id = cfdi.get('id')
            tipo_cfdi = cfdi.get('tipo_cfdi', '')
            tipo_pago = 'cobro' if tipo_cfdi == 'ingreso' else 'pago'
            monto_field = 'monto_cobrado' if tipo_cfdi == 'ingreso' else 'monto_pagado'
            monto = float(cfdi.get(monto_field, 0) or 0)

            if monto < 0.01:
                continue

            existing = await db.payments.find_one(
                {'company_id': company_id, 'cfdi_id': cfdi_id},
                {'_id': 0, 'id': 1}
            )
            if existing:
                omitidos += 1
                continue

            if tipo_cfdi == 'ingreso':
                beneficiario = cfdi.get('receptor_nombre', '') or cfdi.get('emisor_nombre', '')
            else:
                beneficiario = cfdi.get('emisor_nombre', '') or cfdi.get('receptor_nombre', '')

            fecha_pago = cfdi.get('fecha_emision') or cfdi.get('fecha_timbrado') or datetime.now(timezone.utc).isoformat()
            if len(fecha_pago) == 10:
                fecha_pago = f"{fecha_pago}T12:00:00"

            moneda = cfdi.get('moneda', 'MXN') or 'MXN'
            tc = cfdi.get('tipo_cambio', 1) or 1

            payment_doc = {
                'id': str(uuid.uuid4()),
                'company_id': company_id,
                'cfdi_id': cfdi_id,
                'tipo': tipo_pago,
                'concepto': cfdi.get('concepto') or cfdi.get('descripcion') or cfdi.get('uso_cfdi') or beneficiario or cfdi.get('uuid', '')[:8],
                'monto': monto,
                'moneda': moneda,
                'tipo_cambio_historico': tc if moneda != 'MXN' else 1,
                'metodo_pago': cfdi.get('metodo_pago', 'transferencia'),
                'fecha_vencimiento': fecha_pago,
                'fecha_pago': fecha_pago,
                'estatus': 'completado',
                'referencia': cfdi.get('uuid', '')[:36],
                'beneficiario': beneficiario,
                'es_real': True,
                'bank_transaction_id': None,
                'cfdi_uuid': cfdi.get('uuid'),
                'cfdi_emisor': cfdi.get('emisor_nombre'),
                'cfdi_receptor': cfdi.get('receptor_nombre'),
                'category_id': cfdi.get('category_id'),
                'subcategory_id': cfdi.get('subcategory_id'),
                'fuente': 'backfill_from_cfdi',
                'auto_created_from_reconciliation': False,
                'created_at': datetime.now(timezone.utc).isoformat()
            }

            await db.payments.insert_one(payment_doc)
            creados += 1
            logger.info(f"Backfill payment creado: CFDI={cfdi_id} tipo={tipo_pago} monto={monto}")

        except Exception as e:
            errores.append(f"CFDI {cfdi.get('id', '?')}: {str(e)}")
            logger.error(f"Error en backfill CFDI {cfdi.get('id')}: {str(e)}", exc_info=True)

    await audit_log(company_id, 'Payment', 'BACKFILL_FROM_CFDIS', 'CREATE', current_user['id'],
                    {'creados': creados, 'omitidos': omitidos, 'errores': len(errores)})

    return {
        'status': 'success',
        'message': f'Backfill completado: {creados} payments creados, {omitidos} ya existían.',
        'creados': creados,
        'omitidos': omitidos,
        'errores': len(errores),
        'detalle_errores': errores[:10]
    }


@router.post("/fix-backfill-concepts")
async def fix_backfill_concepts(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    Corrige el campo 'concepto' de los payments creados por backfill.
    Reemplaza 'Backfill - XXX' con el concepto real del CFDI.
    Ejecutar UNA SOLA VEZ.
    """
    company_id = await get_active_company_id(request, current_user)

    # Buscar todos los payments de backfill
    backfill_payments = await db.payments.find(
        {'company_id': company_id, 'fuente': 'backfill_from_cfdi'},
        {'_id': 0}
    ).to_list(10000)

    actualizados = 0
    omitidos = 0
    errores = []

    for p in backfill_payments:
        try:
            cfdi_id = p.get('cfdi_id')
            if not cfdi_id:
                omitidos += 1
                continue

            cfdi = await db.cfdis.find_one({'id': cfdi_id}, {'_id': 0})
            if not cfdi:
                omitidos += 1
                continue

            if p.get('tipo') == 'cobro':
                beneficiario = cfdi.get('receptor_nombre', '') or cfdi.get('emisor_nombre', '')
            else:
                beneficiario = cfdi.get('emisor_nombre', '') or cfdi.get('receptor_nombre', '')

            nuevo_concepto = (
                cfdi.get('concepto') or
                cfdi.get('descripcion') or
                cfdi.get('uso_cfdi') or
                beneficiario or
                cfdi.get('uuid', '')[:8]
            )

            await db.payments.update_one(
                {'id': p['id']},
                {'$set': {'concepto': nuevo_concepto}}
            )
            actualizados += 1

        except Exception as e:
            errores.append(f"Payment {p.get('id', '?')}: {str(e)}")

    return {
        'status': 'success',
        'message': f'{actualizados} conceptos actualizados.',
        'actualizados': actualizados,
        'omitidos': omitidos,
        'errores': len(errores),
        'detalle_errores': errores[:10]
    }


@router.put("/{payment_id}")
async def update_payment(payment_id: str, payment_data: PaymentCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    """Update a payment with CFDI amount adjustment"""
    company_id = await get_active_company_id(request, current_user)
    existing = await db.payments.find_one({'id': payment_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    
    old_monto = existing.get('monto', 0)
    old_cfdi_id = existing.get('cfdi_id')
    old_estatus = existing.get('estatus')
    
    update_data = payment_data.model_dump()
    for field in ['fecha_vencimiento', 'fecha_pago']:
        if update_data.get(field):
            update_data[field] = update_data[field].isoformat()
    
    await db.payments.update_one(
        {'id': payment_id, 'company_id': company_id},
        {'$set': update_data}
    )
    
    # If payment was completed and linked to a CFDI, update the CFDI's collected/paid amount
    if old_estatus == 'completado' and old_cfdi_id:
        cfdi = await db.cfdis.find_one({'id': old_cfdi_id}, {'_id': 0})
        if cfdi:
            # Calculate the difference between old and new amount
            new_monto = update_data.get('monto', old_monto)
            diff = new_monto - old_monto
            
            if existing['tipo'] == 'cobro':
                current_cobrado = cfdi.get('monto_cobrado', 0) or 0
                new_cobrado = max(0, current_cobrado + diff)
                await db.cfdis.update_one(
                    {'id': old_cfdi_id},
                    {'$set': {'monto_cobrado': new_cobrado}}
                )
                logger.info(f"Updated CFDI {old_cfdi_id} monto_cobrado after payment edit: {current_cobrado} -> {new_cobrado}")
            else:
                current_pagado = cfdi.get('monto_pagado', 0) or 0
                new_pagado = max(0, current_pagado + diff)
                await db.cfdis.update_one(
                    {'id': old_cfdi_id},
                    {'$set': {'monto_pagado': new_pagado}}
                )
                logger.info(f"Updated CFDI {old_cfdi_id} monto_pagado after payment edit: {current_pagado} -> {new_pagado}")
    
    await audit_log(company_id, 'Payment', payment_id, 'UPDATE', current_user['id'])
    return {'status': 'success', 'message': 'Pago actualizado'}


@router.post("/{payment_id}/complete")
async def complete_payment(payment_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Mark a payment as completed with CFDI amount update"""
    company_id = await get_active_company_id(request, current_user)
    existing = await db.payments.find_one({'id': payment_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    
    # Use fecha_vencimiento as fecha_pago if available, otherwise use current date
    fecha_pago = existing.get('fecha_vencimiento') or datetime.now(timezone.utc).isoformat()
    
    # Update payment status
    await db.payments.update_one(
        {'id': payment_id},
        {'$set': {
            'estatus': 'completado',
            'fecha_pago': fecha_pago
        }}
    )
    
    # If payment is linked to a CFDI, update the paid/collected amount
    if existing.get('cfdi_id'):
        cfdi = await db.cfdis.find_one({'id': existing['cfdi_id']}, {'_id': 0})
        if cfdi:
            if existing['tipo'] == 'cobro':
                # Update monto_cobrado for income CFDI
                current_cobrado = cfdi.get('monto_cobrado', 0) or 0
                new_cobrado = current_cobrado + existing['monto']
                await db.cfdis.update_one(
                    {'id': existing['cfdi_id']},
                    {'$set': {'monto_cobrado': new_cobrado}}
                )
                logger.info(f"Updated CFDI {existing['cfdi_id']} monto_cobrado: {current_cobrado} -> {new_cobrado}")
            else:
                # Update monto_pagado for expense CFDI
                current_pagado = cfdi.get('monto_pagado', 0) or 0
                new_pagado = current_pagado + existing['monto']
                await db.cfdis.update_one(
                    {'id': existing['cfdi_id']},
                    {'$set': {'monto_pagado': new_pagado}}
                )
                logger.info(f"Updated CFDI {existing['cfdi_id']} monto_pagado: {current_pagado} -> {new_pagado}")
    
    await audit_log(company_id, 'Payment', payment_id, 'COMPLETE', current_user['id'])
    return {'status': 'success', 'message': 'Pago completado'}


@router.delete("/{payment_id}")
async def delete_payment(payment_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Delete a payment with CFDI amount reversal"""
    company_id = await get_active_company_id(request, current_user)
    existing = await db.payments.find_one({'id': payment_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    
    # If payment was completed and linked to a CFDI, reverse the collected/paid amount
    if existing.get('estatus') == 'completado' and existing.get('cfdi_id'):
        cfdi = await db.cfdis.find_one({'id': existing['cfdi_id']}, {'_id': 0})
        if cfdi:
            if existing['tipo'] == 'cobro':
                current_cobrado = cfdi.get('monto_cobrado', 0) or 0
                new_cobrado = max(0, current_cobrado - existing['monto'])
                await db.cfdis.update_one(
                    {'id': existing['cfdi_id']},
                    {'$set': {'monto_cobrado': new_cobrado}}
                )
                logger.info(f"Reversed CFDI {existing['cfdi_id']} monto_cobrado after payment delete: {current_cobrado} -> {new_cobrado}")
            else:
                current_pagado = cfdi.get('monto_pagado', 0) or 0
                new_pagado = max(0, current_pagado - existing['monto'])
                await db.cfdis.update_one(
                    {'id': existing['cfdi_id']},
                    {'$set': {'monto_pagado': new_pagado}}
                )
                logger.info(f"Reversed CFDI {existing['cfdi_id']} monto_pagado after payment delete: {current_pagado} -> {new_pagado}")
    
    await db.payments.delete_one({'id': payment_id})
    await audit_log(company_id, 'Payment', payment_id, 'DELETE', current_user['id'])
    return {'status': 'success', 'message': 'Pago eliminado'}


@router.delete("/bulk/all")
async def delete_all_payments(request: Request, current_user: Dict = Depends(get_current_user)):
    """Delete ALL payments/collections for the current company with CFDI reset"""
    company_id = await get_active_company_id(request, current_user)
    
    # Reset all CFDIs monto_cobrado and monto_pagado
    await db.cfdis.update_many(
        {'company_id': company_id},
        {'$set': {'monto_cobrado': 0, 'monto_pagado': 0}}
    )
    
    # Delete all payments
    result = await db.payments.delete_many({'company_id': company_id})
    
    await audit_log(company_id, 'Payment', 'BULK_DELETE', 'DELETE', current_user['id'], 
                    {'count': result.deleted_count, 'action': 'delete_all_payments'})
    
    return {
        'status': 'success',
        'message': f'Se eliminaron {result.deleted_count} pagos/cobranzas',
        'deleted_count': result.deleted_count
    }


@router.post("/backfill-categories")
async def backfill_payment_categories(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    Backfill category/subcategory from linked CFDIs to existing payments.
    This updates payments that have cfdi_id but are missing category_id/subcategory_id.
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Find all payments with cfdi_id but missing category
    payments_to_update = await db.payments.find({
        'company_id': company_id,
        'cfdi_id': {'$ne': None, '$exists': True},
        '$or': [
            {'category_id': None},
            {'category_id': {'$exists': False}}
        ]
    }, {'_id': 0, 'id': 1, 'cfdi_id': 1}).to_list(10000)
    
    updated_count = 0
    errors = []
    
    for payment in payments_to_update:
        cfdi = await db.cfdis.find_one({'id': payment['cfdi_id']}, {'_id': 0, 'category_id': 1, 'subcategory_id': 1, 'uuid': 1, 'emisor_nombre': 1, 'receptor_nombre': 1})
        if cfdi and cfdi.get('category_id'):
            update_data = {
                'category_id': cfdi.get('category_id'),
                'subcategory_id': cfdi.get('subcategory_id'),
                'cfdi_uuid': cfdi.get('uuid'),
                'cfdi_emisor': cfdi.get('emisor_nombre'),
                'cfdi_receptor': cfdi.get('receptor_nombre')
            }
            # Remove None values
            update_data = {k: v for k, v in update_data.items() if v is not None}
            
            if update_data:
                result = await db.payments.update_one(
                    {'id': payment['id']},
                    {'$set': update_data}
                )
                if result.modified_count > 0:
                    updated_count += 1
        else:
            errors.append(f"Payment {payment['id']}: CFDI {payment['cfdi_id']} not found or has no category")
    
    await audit_log(company_id, 'Payment', 'BACKFILL', 'UPDATE', current_user['id'],
                    {'updated_count': updated_count, 'total_checked': len(payments_to_update)})
    
    return {
        'status': 'success',
        'message': f'Se actualizaron {updated_count} de {len(payments_to_update)} pagos',
        'updated_count': updated_count,
        'total_checked': len(payments_to_update),
        'errors': errors[:10] if errors else []  # Return first 10 errors
    }


@router.put("/{payment_id}/categorize")
async def categorize_payment_direct(
    payment_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
    category_id: str = Query(None),
    subcategory_id: str = Query(None)
):
    """
    Categorize a payment directly (for payments without CFDI).
    This is useful for bank fees, manual entries, etc.
    """
    company_id = await get_active_company_id(request, current_user)
    
    payment = await db.payments.find_one({'id': payment_id, 'company_id': company_id}, {'_id': 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    
    update_data = {}
    if category_id:
        update_data['category_id'] = category_id
    if subcategory_id:
        update_data['subcategory_id'] = subcategory_id
    
    if update_data:
        await db.payments.update_one(
            {'id': payment_id, 'company_id': company_id},
            {'$set': update_data}
        )
        await audit_log(company_id, 'Payment', payment_id, 'CATEGORIZE', current_user['id'], update_data)
    
    return {'status': 'success', 'message': 'Pago categorizado correctamente'}



@router.post("/sync-reconciliation-status")
async def sync_reconciliation_status(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    Synchronize payment status with bank transaction reconciliation status.
    If a payment has a bank_transaction_id pointing to a non-reconciled transaction,
    the payment status should be 'pendiente', not 'completado'.
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Get all bank transactions and build a set of truly reconciled IDs
    bank_txns = await db.bank_transactions.find({'company_id': company_id}, {'_id': 0}).to_list(5000)
    reconciled_txn_ids = set(t['id'] for t in bank_txns if t.get('conciliado') == True)
    
    # Find all payments with bank_transaction_id
    payments = await db.payments.find({'company_id': company_id, 'bank_transaction_id': {'$ne': None}}, {'_id': 0}).to_list(5000)
    
    updated_count = 0
    for payment in payments:
        bank_txn_id = payment.get('bank_transaction_id')
        current_status = payment.get('estatus')
        
        # If the bank transaction is NOT reconciled, payment should be 'pendiente'
        if bank_txn_id and bank_txn_id not in reconciled_txn_ids:
            if current_status == 'completado':
                await db.payments.update_one(
                    {'id': payment['id']},
                    {'$set': {'estatus': 'pendiente'}}
                )
                updated_count += 1
                logger.info(f"Payment {payment['id']} status changed from 'completado' to 'pendiente' (bank txn not reconciled)")
        
        # If the bank transaction IS reconciled, payment should be 'completado'
        elif bank_txn_id and bank_txn_id in reconciled_txn_ids:
            if current_status == 'pendiente':
                await db.payments.update_one(
                    {'id': payment['id']},
                    {'$set': {'estatus': 'completado'}}
                )
                updated_count += 1
                logger.info(f"Payment {payment['id']} status changed from 'pendiente' to 'completado' (bank txn reconciled)")
    
    return {
        'status': 'success',
        'message': f'Sincronización completada. {updated_count} pagos actualizados.',
        'updated_count': updated_count
    }


@router.get("/with-reconciliation-status")
async def get_payments_with_reconciliation_status(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    tipo: Optional[str] = Query(None),
    limit: int = Query(100, le=1000)
):
    """
    Get payments with their TRUE reconciliation status from bank transactions.
    This includes a computed 'estado_real' field that reflects whether the
    associated bank transaction is actually reconciled.
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Get all bank transactions for this company
    bank_txns = await db.bank_transactions.find({'company_id': company_id}, {'_id': 0}).to_list(5000)
    bank_txn_map = {t['id']: t for t in bank_txns}
    
    # Build query
    query = {'company_id': company_id}
    if tipo:
        query['tipo'] = tipo
    
    payments = await db.payments.find(query, {'_id': 0}).sort('fecha_vencimiento', -1).limit(limit).to_list(limit)
    
    # Add computed 'estado_real' based on bank transaction status
    for p in payments:
        bank_txn_id = p.get('bank_transaction_id')
        if bank_txn_id:
            bank_txn = bank_txn_map.get(bank_txn_id)
            if bank_txn:
                p['estado_real'] = 'completado' if bank_txn.get('conciliado') == True else 'pendiente'
                p['conciliacion_real'] = bank_txn.get('conciliado', False)
            else:
                # Bank transaction not found, mark as unknown
                p['estado_real'] = 'desconocido'
                p['conciliacion_real'] = False
        else:
            # No bank transaction linked, use payment's own status
            p['estado_real'] = p.get('estatus', 'pendiente')
            p['conciliacion_real'] = None  # Not applicable
        
        # Convert datetime fields
        for field in ['fecha_vencimiento', 'fecha_pago', 'created_at']:
            if isinstance(p.get(field), str):
                p[field] = datetime.fromisoformat(p[field])
    
    return payments


@router.post("/cleanup-duplicates")
async def cleanup_duplicate_payments(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    Remove duplicate payments that reference the same bank_transaction_id.
    Keeps only the first (oldest) payment for each bank transaction.
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Get all payments with bank_transaction_id
    payments = await db.payments.find(
        {'company_id': company_id, 'bank_transaction_id': {'$ne': None}},
        {'_id': 0}
    ).sort('created_at', 1).to_list(10000)  # Sort by created_at to keep oldest
    
    # Group by bank_transaction_id
    from collections import defaultdict
    grouped = defaultdict(list)
    for p in payments:
        bank_txn_id = p.get('bank_transaction_id')
        if bank_txn_id:
            grouped[bank_txn_id].append(p)
    
    # Find and delete duplicates (keep first, delete rest)
    deleted_count = 0
    deleted_ids = []
    
    for bank_txn_id, payment_list in grouped.items():
        if len(payment_list) > 1:
            # Keep the first one (oldest by created_at), delete the rest
            to_delete = payment_list[1:]  # All except first
            for p in to_delete:
                await db.payments.delete_one({'id': p['id']})
                deleted_ids.append(p['id'])
                deleted_count += 1
                logger.info(f"Deleted duplicate payment {p['id']} for bank_txn {bank_txn_id}")
    
    return {
        'status': 'success',
        'message': f'Limpieza completada. {deleted_count} pagos duplicados eliminados.',
        'deleted_count': deleted_count,
        'deleted_ids': deleted_ids[:20]  # Show first 20 for reference
    }



@router.get("/summary")
async def get_payments_summary(request: Request, current_user: Dict = Depends(get_current_user)):
    """Summary of payments for dashboard cards"""
    company_id = await get_active_company_id(request, current_user)
    payments = await db.payments.find({'company_id': company_id}, {'_id': 0}).to_list(10000)
    
    total_pagado = sum(p.get('monto', 0) or 0 for p in payments if p.get('tipo') == 'pago' and p.get('estatus') == 'completado')
    total_cobrado = sum(p.get('monto', 0) or 0 for p in payments if p.get('tipo') == 'cobro' and p.get('estatus') == 'completado')
    total_proy_pagos = sum(p.get('monto', 0) or 0 for p in payments if p.get('tipo') == 'pago' and p.get('es_real') == False)
    total_proy_cobros = sum(p.get('monto', 0) or 0 for p in payments if p.get('tipo') == 'cobro' and p.get('es_real') == False)
    
    return {
        'total_pagado': total_pagado,
        'total_cobrado': total_cobrado,
        'total_proy_pagos': total_proy_pagos,
        'total_proy_cobros': total_proy_cobros,
    }


@router.get("/breakdown")
async def get_payments_breakdown(request: Request, current_user: Dict = Depends(get_current_user)):
    """Breakdown of CFDI pending amounts and payment totals for dashboard cards.
    Uses REAL pending balances (total - monto_cobrado/pagado)."""
    company_id = await get_active_company_id(request, current_user)
    
    # Get FX rates
    rates_docs = await db.fx_rates.find({'company_id': company_id}).to_list(100)
    fx = {'MXN': 1.0, 'USD': 17.5, 'EUR': 19.0}
    for r in rates_docs:
        moneda = r.get('moneda_cotizada') or r.get('moneda_origen')
        tasa = r.get('tipo_cambio') or r.get('tasa')
        if moneda and tasa:
            fx[moneda] = tasa

    def to_mxn(amount, moneda):
        if not moneda or moneda == 'MXN':
            return amount
        tc = fx.get(moneda, 1)
        return amount * tc

    # Get all active CFDIs
    cfdis = await db.cfdis.find(
        {'company_id': company_id, 'estado_cancelacion': {'$ne': 'cancelado'}},
        {'_id': 0, 'tipo_cfdi': 1, 'total': 1, 'moneda': 1, 'tipo_cambio': 1,
         'monto_cobrado': 1, 'monto_pagado': 1}
    ).to_list(10000)

    cfdi_por_cobrar_mxn = 0.0
    cfdi_por_cobrar_count = 0
    cfdi_por_pagar_mxn = 0.0
    cfdi_por_pagar_count = 0

    for c in cfdis:
        total = c.get('total', 0) or 0
        moneda = c.get('moneda', 'MXN') or 'MXN'
        tc = c.get('tipo_cambio', 1) or 1

        if c.get('tipo_cfdi') == 'ingreso':
            ya_cobrado = c.get('monto_cobrado', 0) or 0
            pendiente = max(0, total - ya_cobrado)
            if pendiente > 0.01:
                # Use row-level tipo_cambio for accuracy
                mxn = pendiente * tc if moneda != 'MXN' else pendiente
                cfdi_por_cobrar_mxn += mxn
                cfdi_por_cobrar_count += 1
        else:
            ya_pagado = c.get('monto_pagado', 0) or 0
            pendiente = max(0, total - ya_pagado)
            if pendiente > 0.01:
                mxn = pendiente * tc if moneda != 'MXN' else pendiente
                cfdi_por_pagar_mxn += mxn
                cfdi_por_pagar_count += 1

    # Get real payments from payments collection
    payments = await db.payments.find(
        {'company_id': company_id, 'es_real': True, 'estatus': 'completado'},
        {'_id': 0, 'tipo': 1, 'monto': 1, 'moneda': 1}
    ).to_list(10000)

    total_pagado_mxn = sum(to_mxn(p.get('monto', 0) or 0, p.get('moneda', 'MXN')) for p in payments if p.get('tipo') == 'pago')
    total_cobrado_mxn = sum(to_mxn(p.get('monto', 0) or 0, p.get('moneda', 'MXN')) for p in payments if p.get('tipo') == 'cobro')

    # FIX A: Si no hay payments registrados pero los CFDIs tienen monto_cobrado/pagado
    # (vienen de Alegra/Contalink), leer directamente de los CFDIs para que las tarjetas
    # Pagado/Cobrado no aparezcan en $0.
    if total_pagado_mxn == 0 and total_cobrado_mxn == 0:
        for c in cfdis:
            moneda = c.get('moneda', 'MXN') or 'MXN'
            tc = c.get('tipo_cambio', 1) or 1
            mxn_factor = tc if moneda != 'MXN' else 1
            if c.get('tipo_cfdi') == 'ingreso':
                cobrado = c.get('monto_cobrado', 0) or 0
                if cobrado > 0.01:
                    total_cobrado_mxn += cobrado * mxn_factor
            else:
                pagado = c.get('monto_pagado', 0) or 0
                if pagado > 0.01:
                    total_pagado_mxn += pagado * mxn_factor

    # Projected payments
    proj_payments = await db.payments.find(
        {'company_id': company_id, 'es_real': False},
        {'_id': 0, 'tipo': 1, 'monto': 1, 'moneda': 1}
    ).to_list(10000)

    proy_pagos_mxn = sum(to_mxn(p.get('monto', 0) or 0, p.get('moneda', 'MXN')) for p in proj_payments if p.get('tipo') == 'pago')
    proy_cobros_mxn = sum(to_mxn(p.get('monto', 0) or 0, p.get('moneda', 'MXN')) for p in proj_payments if p.get('tipo') == 'cobro')

    return {
        'cfdi_por_cobrar': {
            'total_equiv_mxn': round(cfdi_por_cobrar_mxn, 2),
            'total_count': cfdi_por_cobrar_count,
        },
        'cfdi_por_pagar': {
            'total_equiv_mxn': round(cfdi_por_pagar_mxn, 2),
            'total_count': cfdi_por_pagar_count,
        },
        'pagado': {
            'total_equiv_mxn': round(total_pagado_mxn, 2),
        },
        'cobrado': {
            'total_equiv_mxn': round(total_cobrado_mxn, 2),
        },
        'proy_pagos': {
            'total_equiv_mxn': round(proy_pagos_mxn, 2),
        },
        'proy_cobros': {
            'total_equiv_mxn': round(proy_cobros_mxn, 2),
        },
    }
