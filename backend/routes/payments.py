"""Payment routes with full CFDI reversal logic"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
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
    source: Optional[str] = Query(None, description="fuente: alegra, contalink, banco, etc."),
    fuente: Optional[str] = Query(None, description="alias de source"),
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
    src = source or fuente
    if src:
        query['$or'] = [{'source': src}, {'fuente': src}]
    
    payments = await db.payments.find(query, {'_id': 0}).sort('fecha_vencimiento', -1).skip(skip).limit(limit).to_list(limit)
    
    for p in payments:
        for field in ['fecha_vencimiento', 'fecha_pago', 'created_at']:
            if isinstance(p.get(field), str) and p[field]:
                p[field] = datetime.fromisoformat(p[field].replace('Z', '+00:00'))
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
                'concepto': (
                    f"{cfdi.get('folio_alegra') or cfdi.get('referencia') or ''} - {beneficiario}".strip(' -')
                ),
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
    """Corrige el concepto de payments creados por backfill. Ejecutar UNA SOLA VEZ."""
    company_id = await get_active_company_id(request, current_user)

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

            folio = cfdi.get('folio_alegra') or cfdi.get('referencia') or ''
            nuevo_concepto = f"{folio} - {beneficiario}".strip(' -')

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


@router.post("/borrar-contalink")
async def borrar_payments_contalink(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    Borra SOLO los payments importados desde Contalink (source='contalink').
    Deja intactos los de banco, PDF y manuales.
    Después re-sincroniza desde Contalink con las fechas correctas.
    """
    company_id = await get_active_company_id(request, current_user)
    result = await db.payments.delete_many(
        {"company_id": company_id, "source": "contalink"}
    )
    return {
        "success": True,
        "deleted": result.deleted_count,
        "message": f"{result.deleted_count} payments de Contalink eliminados. Ya puedes re-sincronizar."
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


@router.get("/by-date-range/preview")
async def preview_delete_by_date_range(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    fecha_inicio: str = Query(..., description="Fecha inicio YYYY-MM-DD"),
    fecha_fin: str = Query(..., description="Fecha fin YYYY-MM-DD"),
):
    """Preview: count and total amount of payments in a date range (before deleting)."""
    company_id = await get_active_company_id(request, current_user)

    if fecha_inicio > fecha_fin:
        raise HTTPException(status_code=400, detail="fecha_inicio debe ser <= fecha_fin")

    query = {
        'company_id': company_id,
        'fecha_vencimiento': {'$gte': fecha_inicio, '$lte': fecha_fin + 'T23:59:59'},
    }
    payments = await db.payments.find(query, {'_id': 0, 'monto': 1, 'moneda': 1, 'tipo_cambio_historico': 1}).to_list(10000)

    # Sum amounts converting to MXN where possible
    monto_total = 0.0
    for p in payments:
        monto = p.get('monto') or 0
        moneda = p.get('moneda', 'MXN')
        tc = p.get('tipo_cambio_historico') or 1
        monto_total += monto if moneda == 'MXN' else monto * tc

    return {
        'count': len(payments),
        'monto_total': round(monto_total, 2),
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
    }


@router.delete("/by-date-range")
async def delete_payments_by_date_range(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    fecha_inicio: str = Query(..., description="Fecha inicio YYYY-MM-DD"),
    fecha_fin: str = Query(..., description="Fecha fin YYYY-MM-DD"),
):
    """Delete all payments for the company within a date range.
    Resets monto_cobrado / monto_pagado on linked CFDIs."""
    company_id = await get_active_company_id(request, current_user)

    if fecha_inicio > fecha_fin:
        raise HTTPException(status_code=400, detail="fecha_inicio debe ser <= fecha_fin")

    query = {
        'company_id': company_id,
        'fecha_vencimiento': {'$gte': fecha_inicio, '$lte': fecha_fin + 'T23:59:59'},
    }

    # Collect CFDI IDs linked to these payments before deleting
    affected = await db.payments.find(query, {'_id': 0, 'cfdi_id': 1}).to_list(10000)
    cfdi_ids = list({p['cfdi_id'] for p in affected if p.get('cfdi_id')})

    result = await db.payments.delete_many(query)

    # Reset monto_cobrado / monto_pagado on affected CFDIs
    if cfdi_ids:
        await db.cfdis.update_many(
            {'company_id': company_id, 'uuid': {'$in': cfdi_ids}},
            {'$set': {'monto_cobrado': 0, 'monto_pagado': 0}},
        )

    await audit_log(
        company_id, 'Payment', 'BULK_DELETE_BY_DATE', 'DELETE', current_user['id'],
        {'count': result.deleted_count, 'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin},
    )

    return {
        'eliminados': result.deleted_count,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
    }


# /{payment_id} must come AFTER all specific paths to avoid capturing them as IDs
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


@router.post("/reset-empresa")
async def reset_empresa(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    Reset COMPLETO de la empresa activa:
    - Borra todos los payments
    - Borra todos los CFDIs
    - Borra categorías custom (conserva defaults del sistema)
    - Borra estados financieros
    - Borra movimientos de cashflow sync
    SOLO afecta a la empresa activa (X-Company-ID header).
    """
    company_id = await get_active_company_id(request, current_user)

    # 1. Payments
    r_payments = await db.payments.delete_many({"company_id": company_id})

    # 2. CFDIs
    r_cfdis = await db.cfdis.delete_many({"company_id": company_id})

    # 3. Categorías custom (no las del sistema/defaults)
    r_cats = await db.cashflow_categories.delete_many({"company_id": company_id})

    # 4. Estados financieros
    r_fin = await db.financial_statements.delete_many({"company_id": company_id})

    # 5. Movimientos de cashflow sync
    r_cf = await db.cashflow_movements.delete_many({"company_id": company_id})

    await audit_log(company_id, 'Company', 'RESET_EMPRESA', 'DELETE', current_user['id'], {
        'payments': r_payments.deleted_count,
        'cfdis': r_cfdis.deleted_count,
        'categorias': r_cats.deleted_count,
        'financial_statements': r_fin.deleted_count,
        'cashflow_movements': r_cf.deleted_count,
    })

    return {
        "success": True,
        "company_id": company_id,
        "eliminados": {
            "payments": r_payments.deleted_count,
            "cfdis": r_cfdis.deleted_count,
            "categorias_custom": r_cats.deleted_count,
            "estados_financieros": r_fin.deleted_count,
            "cashflow_movements": r_cf.deleted_count,
        },
        "message": "Reset completo. Ya puedes re-sincronizar desde Contalink."
    }


@router.post("/backfill-categories")
async def backfill_payment_categories(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    Backfill category/subcategory from linked CFDIs to existing payments.
    This updates payments that have cfdi_id but are missing category_id/subcategory_id.
    """
    company_id = await get_active_company_id(request, current_user)

    # Check first if any payments are linked to CFDIs at all
    total_with_cfdi = await db.payments.count_documents({
        'company_id': company_id,
        'cfdi_id': {'$ne': None, '$exists': True},
    })
    if total_with_cfdi == 0:
        return {
            'status': 'no_cfdi_payments',
            'message': 'No hay pagos vinculados a CFDI para categorizar. Usa Auto-categorizar con IA para los demás pagos.',
            'updated_count': 0,
            'total_checked': 0,
            'errors': []
        }

    # Find payments with cfdi_id that are missing or empty category
    payments_to_update = await db.payments.find({
        'company_id': company_id,
        'cfdi_id': {'$ne': None, '$exists': True},
        '$or': [
            {'category_id': None},
            {'category_id': {'$exists': False}},
            {'category_id': ''},
        ]
    }, {'_id': 0, 'id': 1, 'cfdi_id': 1}).to_list(10000)

    updated_count = 0
    errors = []
    
    for payment in payments_to_update:
        cfdi = await db.cfdis.find_one({'id': payment['cfdi_id']}, {'_id': 0, 'category_id': 1, 'category_name': 1, 'subcategory_id': 1, 'uuid': 1, 'emisor_nombre': 1, 'receptor_nombre': 1})
        if cfdi and cfdi.get('category_id'):
            update_data = {
                'category_id': cfdi.get('category_id'),
                'category_name': cfdi.get('category_name'),
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
    limit: int = Query(1000, le=10000),
    fecha_desde: Optional[str] = Query(None),
    fecha_hasta: Optional[str] = Query(None),
):
    """
    Get payments with their TRUE reconciliation status from bank transactions.
    This includes a computed 'estado_real' field that reflects whether the
    associated bank transaction is actually reconciled.
    """
    company_id = await get_active_company_id(request, current_user)

    # ── Detectar si la empresa usa Alegra como fuente principal ──
    alegra_count = await db.bank_transactions.count_documents(
        {'company_id': {'$regex': f'^{company_id[:8]}'}, 'source': 'alegra'}, limit=1
    )
    usa_alegra = alegra_count > 0

    payments: list = []

    COBRO_TIPOS = {'deposito', 'ingreso', 'credito', 'in'}
    PAGO_TIPOS  = {'retiro', 'egreso', 'debito', 'out'}

    if usa_alegra:
        # ── Fuente principal: db.bank_transactions source='alegra' ──
        bt_query: dict = {'company_id': {'$regex': f'^{company_id[:8]}'}, 'source': 'alegra', 'es_real': True}
        if tipo == 'cobro':
            bt_query['tipo'] = {'$in': list(COBRO_TIPOS)}
        elif tipo == 'pago':
            bt_query['tipo'] = {'$in': list(PAGO_TIPOS)}

        logger.info(f"[Payments BT] bt_query={bt_query} fecha_desde={fecha_desde} fecha_hasta={fecha_hasta}")
        bank_txns_alegra = await db.bank_transactions.find(
            bt_query, {'_id': 0}
        ).sort('fecha', -1).to_list(20000)

        # Filtrar por fecha en Python — compatible con campo string o datetime
        if fecha_desde:
            bank_txns_alegra = [t for t in bank_txns_alegra
                                if str(t.get('fecha', ''))[:10] >= fecha_desde]
        if fecha_hasta:
            bank_txns_alegra = [t for t in bank_txns_alegra
                                if str(t.get('fecha', ''))[:10] <= fecha_hasta]

        # Deduplicar por alegra_id — conservar el más reciente (mayor updated_at)
        seen_alegra_ids: dict = {}
        for t in bank_txns_alegra:
            aid = t.get('alegra_id')
            if not aid:
                continue
            prev = seen_alegra_ids.get(aid)
            if prev is None or str(t.get('updated_at', '')) > str(prev.get('updated_at', '')):
                seen_alegra_ids[aid] = t
        # Docs sin alegra_id se incluyen siempre
        no_aid = [t for t in bank_txns_alegra if not t.get('alegra_id')]
        bank_txns_alegra = list(seen_alegra_ids.values()) + no_aid

        logger.info(f"[Payments BT] bank_txns después de dedup: {len(bank_txns_alegra)}")

        for t in bank_txns_alegra:
            tipo_bt = t.get('tipo', '').lower()
            tipo_pay = 'cobro' if tipo_bt in COBRO_TIPOS else 'pago'
            fecha = t.get('fecha') or t.get('fecha_movimiento', '')
            payments.append({
                'id':                      t.get('id') or f"bt-{t.get('alegra_id', '')}",
                'company_id':              company_id,
                'tipo':                    tipo_pay,
                'concepto':                t.get('descripcion') or t.get('numero_movimiento') or t.get('contacto') or '',
                'monto':                   t.get('monto', 0),
                'monto_original':          t.get('monto_original', t.get('monto', 0)),
                'moneda':                  t.get('moneda', 'MXN'),
                'tipo_cambio':             t.get('tipo_cambio', 1),
                'fecha_pago':              fecha,
                'fecha_vencimiento':       fecha,
                'beneficiario':            t.get('contacto', ''),
                'cuenta_bancaria':         t.get('cuenta_bancaria', ''),
                'alegra_bank_account':     t.get('cuenta_bancaria', ''),
                'facturas_ligadas':        t.get('facturas_ligadas', []),
                'categorias':              t.get('categorias', []),
                'estatus':                 'completado',
                'es_real':                 True,
                'source':                  'alegra',
                'fuente':                  'bank_transaction',
                'alegra_id':               t.get('alegra_id', ''),
                'estado_real':             'completado',
                'conciliacion_real':       True,
                '_from_bank_transactions': True,
            })

    else:
        # ── Fuente fallback: db.payments (Contalink / manual) ──
        query: dict = {'company_id': company_id}
        if tipo:
            query['tipo'] = tipo
        if fecha_desde:
            query['fecha_pago'] = {'$gte': fecha_desde}
        if fecha_hasta:
            if 'fecha_pago' in query:
                query['fecha_pago']['$lte'] = fecha_hasta
            else:
                query['fecha_pago'] = {'$lte': fecha_hasta}

        bank_txns_all = await db.bank_transactions.find(
            {'company_id': company_id}, {'_id': 0}
        ).to_list(5000)
        bank_txn_map = {t['id']: t for t in bank_txns_all}

        raw = await db.payments.find(query, {'_id': 0}).sort('fecha_pago', -1).limit(limit).to_list(limit)

        for p in raw:
            bank_txn_id = p.get('bank_transaction_id')
            if bank_txn_id:
                bt = bank_txn_map.get(bank_txn_id)
                if bt:
                    p['estado_real'] = 'completado' if bt.get('conciliado') else 'pendiente'
                    p['conciliacion_real'] = bt.get('conciliado', False)
                else:
                    p['estado_real'] = 'desconocido'
                    p['conciliacion_real'] = False
            else:
                p['estado_real'] = p.get('estatus', 'pendiente')
                p['conciliacion_real'] = None

            for field in ['fecha_vencimiento', 'fecha_pago', 'created_at']:
                if isinstance(p.get(field), str) and p[field]:
                    p[field] = datetime.fromisoformat(p[field].replace('Z', '+00:00'))

            payments.append(p)

    payments.sort(
        key=lambda p: str(p.get('fecha_pago') or p.get('fecha_vencimiento') or ''),
        reverse=True
    )
    return JSONResponse(content=jsonable_encoder(payments[:limit]))


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

    total_pagado     = sum(p.get('monto', 0) or 0 for p in payments if p.get('tipo') == 'pago'  and p.get('estatus') == 'completado')
    total_cobrado    = sum(p.get('monto', 0) or 0 for p in payments if p.get('tipo') == 'cobro' and p.get('estatus') == 'completado')
    total_proy_pagos = sum(p.get('monto', 0) or 0 for p in payments if p.get('tipo') == 'pago'  and p.get('es_real') == False)
    total_proy_cobros= sum(p.get('monto', 0) or 0 for p in payments if p.get('tipo') == 'cobro' and p.get('es_real') == False)

    # CxC pendientes de Alegra (invoices no cobradas) — en MXN
    cxc_alegra_docs = [
        p for p in payments
        if p.get('tipo') == 'cobro' and p.get('estatus') == 'pendiente'
        and p.get('es_real') == True and p.get('source') == 'alegra'
    ]
    monto_cxc_alegra = sum(
        float(p.get('monto', 0) or 0) * float(p.get('tipo_cambio_historico') or 1)
        for p in cxc_alegra_docs
    )

    # CxP pendientes de Alegra (bills no pagadas) — en MXN
    cxp_alegra_docs = [
        p for p in payments
        if p.get('tipo') == 'pago' and p.get('estatus') == 'pendiente'
        and p.get('es_real') == True and p.get('source') == 'alegra'
    ]
    monto_cxp_alegra = sum(
        float(p.get('monto', 0) or 0) * float(p.get('tipo_cambio_historico') or 1)
        for p in cxp_alegra_docs
    )

    return {
        'total_pagado':      total_pagado,
        'total_cobrado':     total_cobrado,
        'total_proy_pagos':  total_proy_pagos,
        'total_proy_cobros': total_proy_cobros,
        'por_cobrar':        round(monto_cxc_alegra, 2),
        'por_cobrar_count':  len(cxc_alegra_docs),
        'por_pagar':         round(monto_cxp_alegra, 2),
        'por_pagar_count':   len(cxp_alegra_docs),
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
         'currency': 1, 'monto_cobrado': 1, 'monto_pagado': 1}
    ).to_list(10000)

    cfdi_por_cobrar_mxn = 0.0
    cfdi_por_cobrar_count = 0
    cfdi_por_pagar_mxn = 0.0
    cfdi_por_pagar_count = 0

    for c in cfdis:
        total = c.get('total', 0) or 0
        moneda = c.get('moneda', 'MXN') or 'MXN'
        tc = c.get('tipo_cambio') or None
        if not tc or tc == 1:
            currency = c.get('currency', {})
            if isinstance(currency, dict):
                tc = float(currency.get('exchangeRate') or 1)
            else:
                tc = 1.0
        tc = float(tc) if tc else 1.0

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
        {'_id': 0, 'tipo': 1, 'monto': 1, 'moneda': 1, 'cfdi_id': 1}
    ).to_list(10000)

    pagado_count  = sum(1 for p in payments if p.get('tipo') == 'pago')
    cobrado_count = sum(1 for p in payments if p.get('tipo') == 'cobro')
    pagado_con_cfdi  = sum(1 for p in payments if p.get('tipo') == 'pago'  and p.get('cfdi_id'))
    cobrado_con_cfdi = sum(1 for p in payments if p.get('tipo') == 'cobro' and p.get('cfdi_id'))

    total_pagado_mxn  = sum(to_mxn(p.get('monto', 0) or 0, p.get('moneda', 'MXN')) for p in payments if p.get('tipo') == 'pago')
    total_cobrado_mxn = sum(to_mxn(p.get('monto', 0) or 0, p.get('moneda', 'MXN')) for p in payments if p.get('tipo') == 'cobro')

    # Sumar movimientos reales de db.bank_transactions source='alegra'
    bank_txns_alegra = await db.bank_transactions.find(
        {'company_id': company_id, 'source': 'alegra', 'es_real': True},
        {'_id': 0, 'tipo': 1, 'monto': 1}
    ).to_list(10000)
    for t in bank_txns_alegra:
        tipo_bt = t.get('tipo', '')
        monto_t = float(t.get('monto', 0) or 0)
        if tipo_bt in ('deposito', 'ingreso', 'credito'):
            total_cobrado_mxn += monto_t
            cobrado_count += 1
        else:
            total_pagado_mxn += monto_t
            pagado_count += 1

    # Fallback: si aún no hay nada, leer monto_cobrado/pagado de los CFDIs
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

    # Projected payments (payments manuales con es_real=False)
    proj_payments = await db.payments.find(
        {'company_id': company_id, 'es_real': False},
        {'_id': 0, 'tipo': 1, 'monto': 1, 'moneda': 1}
    ).to_list(10000)

    proy_pagos_mxn = sum(to_mxn(p.get('monto', 0) or 0, p.get('moneda', 'MXN')) for p in proj_payments if p.get('tipo') == 'pago')
    proy_cobros_mxn = sum(to_mxn(p.get('monto', 0) or 0, p.get('moneda', 'MXN')) for p in proj_payments if p.get('tipo') == 'cobro')

    # ── Sumar CxC/CxP de Contalink como proyecciones futuras ──────────
    # Las CxC son cobros pendientes (proyeccion_cobros)
    # Las CxP son pagos pendientes (proyeccion_pagos)
    cxc_cached = await db.contalink_cache.find_one({"key": f"cxc_{company_id}_latest"})
    cxp_cached = await db.contalink_cache.find_one({"key": f"cxp_{company_id}_latest"})
    cxc_total = cxc_cached["data"].get("total_pendiente", 0) if cxc_cached else 0
    cxp_total = cxp_cached["data"].get("total_pendiente", 0) if cxp_cached else 0
    proy_cobros_mxn += cxc_total   # CxC = dinero que nos van a pagar
    proy_pagos_mxn  += cxp_total   # CxP = dinero que tenemos que pagar

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
            'total_count':     pagado_count,
            'con_cfdi':        pagado_con_cfdi,
        },
        'cobrado': {
            'total_equiv_mxn': round(total_cobrado_mxn, 2),
            'total_count':     cobrado_count,
            'con_cfdi':        cobrado_con_cfdi,
        },
        'proy_pagos': {
            'total_equiv_mxn': round(proy_pagos_mxn, 2),
        },
        'proy_cobros': {
            'total_equiv_mxn': round(proy_cobros_mxn, 2),
        },
        # Aliases para compatibilidad con PaymentsModule frontend
        'proyeccion_pagos': {
            'total_equiv_mxn': round(proy_pagos_mxn, 2),
            'total_count': len([p for p in proj_payments if p.get('tipo') == 'pago']),
        },
        'proyeccion_cobros': {
            'total_equiv_mxn': round(proy_cobros_mxn, 2),
            'total_count': len([p for p in proj_payments if p.get('tipo') == 'cobro']),
        },
    }


@router.post("/sync-contalink")
async def sync_payments_from_contalink(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    date_from: str = Query(None, description="Fecha inicio YYYY-MM-DD (default: 1 año atrás)"),
    date_to: str = Query(None, description="Fecha fin YYYY-MM-DD (default: hoy)"),
):
    """Sincroniza cobranza y pagos desde Contalink para un rango de fechas configurable."""
    company_id = await get_active_company_id(request, current_user)

    # Buscar credenciales con formato de contalink.py (type="contalink")
    creds_doc = await db.integrations.find_one(
        {"company_id": company_id, "type": "contalink", "active": True},
        {"_id": 0}
    )
    if not creds_doc:
        raise HTTPException(status_code=400, detail="No tienes Contalink conectado. Ve a Integraciones y guarda tu API Key.")

    api_key = creds_doc.get("api_key", "")
    rfc = creds_doc.get("rfc", "")

    if not api_key:
        raise HTTPException(status_code=400, detail="API Key de Contalink no configurada.")
    if not rfc or rfc == "PENDIENTE":
        raise HTTPException(status_code=400, detail="RFC no configurado. Ve a Integraciones → Contalink y guarda el RFC.")

    from routes.contalink import ContalinkClient
    import calendar as cal

    client = ContalinkClient(api_key)
    created = 0
    skipped = 0
    errors = []

    now = datetime.now(timezone.utc)

    # Parse or default the date range
    dt_to = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=timezone.utc) if date_to else now
    dt_from = (
        datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if date_from
        else dt_to.replace(year=dt_to.year - 1)
    )

    # Build list of (year, month) pairs covering the full range
    months_to_sync = []
    cur = dt_from.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_month = dt_to.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    while cur <= end_month:
        months_to_sync.append((cur.year, cur.month))
        # Advance to next month safely
        cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)

    for year, month in months_to_sync:
        last_day = cal.monthrange(year, month)[1]
        start = f"{year}-{month:02d}-01"
        end = f"{year}-{month:02d}-{last_day:02d}"

        # Facturas emitidas (cobranza CxC)
        try:
            issued = await client.get_invoices(
                rfc=rfc,
                transaction_type="E",
                document_type="Ingreso",
                start_date=start,
                end_date=end,
            )
            # Contalink response: {"list": {"total": N, "invoices": [...]}}
            if isinstance(issued, list):
                inv_list = issued
            elif "list" in issued:
                inv_list = issued["list"].get("invoices", [])
            else:
                inv_list = issued.get("data", issued.get("invoices", []))
            logger.info(f"Contalink issued {start}: {len(inv_list)} facturas")
            if inv_list:
                sample = inv_list[0]
                logger.info(f"Contalink sample invoice keys: {list(sample.keys())}")
                logger.info(f"Contalink sample date fields: date={sample.get('date')} fecha={sample.get('fecha')} fecha_expedicion={sample.get('fecha_expedicion')} fecha_emision={sample.get('fecha_emision')}")

            for inv in inv_list:
                monto = float(inv.get("total", 0) or 0)
                estatus = (inv.get("estatus") or inv.get("status") or "vigente").lower()
                if monto <= 0 or estatus == "cancelado":
                    continue
                ref = f"contalink-issued-{inv.get('uuid', inv.get('id', str(inv.get('folio',''))))}-{start}"
                if await db.payments.find_one({"company_id": company_id, "referencia_contalink": ref}):
                    skipped += 1
                    continue
                try:
                    fecha_str = (inv.get("fecha_expedicion") or inv.get("fecha") or
                                 inv.get("date") or inv.get("fecha_emision") or end)
                    fecha = datetime.strptime(str(fecha_str)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except:
                    fecha = datetime.now(timezone.utc)
                uuid_val = (inv.get("uuid") or inv.get("UUID") or inv.get("folio_fiscal") or "")
                receptor = inv.get("nombre_receptor") or inv.get("receptor_nombre", "")
                await db.payments.insert_one({
                    "id":                   str(uuid.uuid4()),
                    "company_id":           company_id,
                    "tipo":                 "cobro",
                    "monto":                monto,
                    "moneda":               inv.get("moneda", "MXN"),
                    "tipo_cambio_historico": float(inv.get("tipo_cambio", 1) or 1),
                    "fecha":                fecha.isoformat(),
                    "fecha_pago":           fecha.isoformat(),
                    "fecha_vencimiento":    fecha.isoformat(),
                    "concepto":             f"Cobranza {inv.get('folio','')} - {receptor}".strip(" -"),
                    "beneficiario":         receptor,
                    "estatus":              "completado",
                    "source":               "contalink",
                    "es_real":              True,
                    "referencia_contalink": ref,
                    "cfdi_uuid":            uuid_val,
                    "created_at":           datetime.now(timezone.utc).isoformat(),
                    "created_by":           current_user["id"],
                })
                created += 1

                # También guardar en cfdis para proyecciones futuras
                if uuid_val and not await db.cfdis.find_one({"company_id": company_id, "uuid": uuid_val}):
                    # Calcular fecha de vencimiento (30 días después de expedición)
                    fecha_venc = fecha + timedelta(days=30)
                    await db.cfdis.insert_one({
                        "id":                  str(uuid.uuid4()),
                        "company_id":          company_id,
                        "uuid":                uuid_val,
                        "tipo_cfdi":           "ingreso",
                        "fecha_emision":       fecha.isoformat(),
                        "fecha_expedicion":    fecha.isoformat(),
                        "fecha_vencimiento":   fecha_venc.isoformat(),
                        "total":               monto,
                        "moneda":              inv.get("moneda", "MXN"),
                        "tipo_cambio":         float(inv.get("tipo_cambio", 1) or 1),
                        "monto_cobrado":       monto,  # ya cobrado = no proyectar
                        "monto_pagado":        0,
                        "nombre_receptor":     receptor,
                        "nombre_emisor":       inv.get("nombre_emisor") or inv.get("emisor_nombre", ""),
                        "rfc_receptor":        inv.get("rfc_receptor", ""),
                        "rfc_emisor":          inv.get("rfc_emisor", rfc),
                        "folio":               str(inv.get("folio", "")),
                        "estado_cancelacion":  "vigente",
                        "source":              "contalink",
                        "created_at":          datetime.now(timezone.utc).isoformat(),
                    })
        except Exception as e:
            errors.append(f"Emitidas {start}: {str(e)}")
            logger.error(f"sync-contalink issued error: {e}")

        # Facturas recibidas (pagos CxP)
        try:
            received = await client.get_invoices(
                rfc=rfc,
                transaction_type="R",
                document_type="Ingreso",
                start_date=start,
                end_date=end,
            )
            if isinstance(received, list):
                rec_list = received
            elif "list" in received:
                rec_list = received["list"].get("invoices", [])
            else:
                rec_list = received.get("data", received.get("invoices", []))
            logger.info(f"Contalink received {start}: {len(rec_list)} facturas")

            for inv in rec_list:
                monto = float(inv.get("total", 0) or 0)
                estatus = (inv.get("estatus") or inv.get("status") or "vigente").lower()
                if monto <= 0 or estatus == "cancelado":
                    continue
                ref = f"contalink-received-{inv.get('uuid', inv.get('id', str(inv.get('folio',''))))}-{start}"
                if await db.payments.find_one({"company_id": company_id, "referencia_contalink": ref}):
                    skipped += 1
                    continue
                try:
                    fecha_str = (inv.get("fecha_expedicion") or inv.get("fecha") or
                                 inv.get("date") or inv.get("fecha_emision") or end)
                    fecha = datetime.strptime(str(fecha_str)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except:
                    fecha = datetime.now(timezone.utc)
                uuid_val = (inv.get("uuid") or inv.get("UUID") or inv.get("folio_fiscal") or "")
                emisor = inv.get("nombre_emisor") or inv.get("emisor_nombre", "")
                await db.payments.insert_one({
                    "id":                   str(uuid.uuid4()),
                    "company_id":           company_id,
                    "tipo":                 "pago",
                    "monto":                monto,
                    "moneda":               inv.get("moneda", "MXN"),
                    "tipo_cambio_historico": float(inv.get("tipo_cambio", 1) or 1),
                    "fecha":                fecha.isoformat(),
                    "fecha_pago":           fecha.isoformat(),
                    "fecha_vencimiento":    fecha.isoformat(),
                    "concepto":             f"Pago {inv.get('folio','')} - {emisor}".strip(" -"),
                    "beneficiario":         emisor,
                    "estatus":              "completado",
                    "source":               "contalink",
                    "es_real":              True,
                    "referencia_contalink": ref,
                    "cfdi_uuid":            uuid_val,
                    "created_at":           datetime.now(timezone.utc).isoformat(),
                    "created_by":           current_user["id"],
                })
                created += 1

                # También guardar en cfdis para proyecciones futuras
                if uuid_val and not await db.cfdis.find_one({"company_id": company_id, "uuid": uuid_val}):
                    fecha_venc = fecha + timedelta(days=30)
                    await db.cfdis.insert_one({
                        "id":                  str(uuid.uuid4()),
                        "company_id":          company_id,
                        "uuid":                uuid_val,
                        "tipo_cfdi":           "egreso",
                        "fecha_emision":       fecha.isoformat(),
                        "fecha_expedicion":    fecha.isoformat(),
                        "fecha_vencimiento":   fecha_venc.isoformat(),
                        "total":               monto,
                        "moneda":              inv.get("moneda", "MXN"),
                        "tipo_cambio":         float(inv.get("tipo_cambio", 1) or 1),
                        "monto_cobrado":       0,
                        "monto_pagado":        monto,  # ya pagado = no proyectar
                        "nombre_emisor":       emisor,
                        "nombre_receptor":     inv.get("nombre_receptor") or inv.get("receptor_nombre", ""),
                        "rfc_emisor":          inv.get("rfc_emisor", ""),
                        "rfc_receptor":        inv.get("rfc_receptor", rfc),
                        "folio":               str(inv.get("folio", "")),
                        "estado_cancelacion":  "vigente",
                        "source":              "contalink",
                        "created_at":          datetime.now(timezone.utc).isoformat(),
                    })
        except Exception as e:
            errors.append(f"Recibidas {start}: {str(e)}")
            logger.error(f"sync-contalink received error: {e}")

    # Persist sync range to integrations record for reference
    await db.integrations.update_one(
        {"company_id": company_id, "type": "contalink", "active": True},
        {"$set": {
            "last_sync_from": dt_from.strftime("%Y-%m-%d"),
            "last_sync_to":   dt_to.strftime("%Y-%m-%d"),
            "last_sync_at":   now.isoformat(),
            "last_sync_created": created,
        }}
    )

    return {
        "success": True,
        "created": created,
        "skipped": skipped,
        "errors":  errors,
        "sync_from": dt_from.strftime("%Y-%m-%d"),
        "sync_to":   dt_to.strftime("%Y-%m-%d"),
        "months_synced": len(months_to_sync),
        "message": f"Contalink sync ({dt_from.strftime('%Y-%m-%d')} → {dt_to.strftime('%Y-%m-%d')}): {created} importados, {skipped} ya existían.",
    }

@router.post("/fix-contalink-status")
async def fix_contalink_status(request: Request, current_user: Dict = Depends(get_current_user)):
    """Actualiza pagos importados de Contalink de pendiente a completado"""
    company_id = await get_active_company_id(request, current_user)
    result = await db.payments.update_many(
        {"company_id": company_id, "source": "contalink"},
        {"$set": {"estatus": "completado", "es_real": True}}
    )
    return {"success": True, "updated": result.modified_count, "message": f"{result.modified_count} pagos actualizados a completado"}


@router.post("/fix-contalink-fecha-pago")
async def fix_contalink_fecha_pago(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    Migración: agrega fecha_pago y fecha_vencimiento a payments de Contalink
    que solo tienen 'fecha'. Necesario para que aparezcan en el modelo de cashflow.
    """
    company_id = await get_active_company_id(request, current_user)
    payments = await db.payments.find(
        {
            "company_id": company_id,
            "source": "contalink",
            "$or": [
                {"fecha_pago": {"$exists": False}},
                {"fecha_pago": None},
            ]
        },
        {"_id": 0, "id": 1, "fecha": 1}
    ).to_list(5000)

    updated = 0
    for p in payments:
        fecha = p.get("fecha")
        if not fecha:
            continue
        await db.payments.update_one(
            {"id": p["id"], "company_id": company_id},
            {"$set": {
                "fecha_pago":        fecha,
                "fecha_vencimiento": fecha,
                "estatus":           "completado",
                "es_real":           True,
            }}
        )
        updated += 1

    return {
        "success": True,
        "updated": updated,
        "message": f"{updated} payments de Contalink actualizados con fecha_pago y fecha_vencimiento."
    }




@router.post("/fix-contalink-dates")
async def fix_contalink_dates(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    Migración puntual: corrige la fecha de los payments de Contalink que quedaron
    con la fecha de import (hoy) en lugar de la fecha del CFDI.
    Usa cfdi_uuid para buscar la fecha real en la colección de CFDIs.
    Ejecutar UNA VEZ después de sincronizar.
    """
    company_id = await get_active_company_id(request, current_user)

    # Traer payments de Contalink con cfdi_uuid
    payments = await db.payments.find(
        {"company_id": company_id, "source": "contalink", "cfdi_uuid": {"$exists": True, "$ne": ""}},
        {"_id": 0, "id": 1, "cfdi_uuid": 1, "fecha": 1}
    ).to_list(5000)

    updated = 0
    not_found = 0
    for p in payments:
        cfdi_uuid = p.get("cfdi_uuid")
        if not cfdi_uuid:
            continue
        cfdi = await db.cfdis.find_one(
            {"company_id": company_id, "$or": [
                {"uuid": cfdi_uuid}, {"folio_fiscal": cfdi_uuid}
            ]},
            {"_id": 0, "fecha_expedicion": 1, "fecha": 1}
        )
        if not cfdi:
            not_found += 1
            continue
        fecha_real = cfdi.get("fecha_expedicion") or cfdi.get("fecha")
        if not fecha_real:
            not_found += 1
            continue
        if not isinstance(fecha_real, str):
            fecha_real = fecha_real.isoformat()
        await db.payments.update_one(
            {"id": p["id"], "company_id": company_id},
            {"$set": {"fecha": fecha_real, "fecha_pago": fecha_real}}
        )
        updated += 1

    return {
        "success": True,
        "updated": updated,
        "not_found": not_found,
        "message": f"{updated} pagos con fecha corregida desde CFDI. {not_found} sin CFDI encontrado."
    }




@router.post("/fix-company-id")
async def fix_company_id(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    Fix puntual: reasigna los 412 pagos que quedaron bajo la empresa 'test'
    (company_id: 381aada7-9180-41fe-b1f8-9b15b4630414) a la empresa activa actual.
    Ejecutar UNA SOLA VEZ.
    """
    OLD_COMPANY_ID = "381aada7-9180-41fe-b1f8-9b15b4630414"
    company_id = await get_active_company_id(request, current_user)

    result = await db.payments.update_many(
        {"company_id": OLD_COMPANY_ID},
        {"$set": {"company_id": company_id}}
    )

    logger.info(f"fix-company-id: {result.modified_count} pagos reasignados de {OLD_COMPANY_ID} -> {company_id}")
    await audit_log(company_id, "Payment", "FIX_COMPANY_ID", "UPDATE", current_user["id"],
                    {"old_company_id": OLD_COMPANY_ID, "new_company_id": company_id, "modified": result.modified_count})

    return {
        "success": True,
        "modificados": result.modified_count,
        "old_company_id": OLD_COMPANY_ID,
        "new_company_id": company_id,
        "message": f"{result.modified_count} pagos reasignados correctamente a la empresa activa."
    }
