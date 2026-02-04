"""Reconciliation routes with full data integrity logic"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Dict, List, Optional
from datetime import datetime, timezone
import uuid
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id
from models.reconciliation import BankReconciliation, BankReconciliationCreate
from services.audit import audit_log

router = APIRouter(prefix="/reconciliations")
logger = logging.getLogger(__name__)


@router.post("", response_model=BankReconciliation)
async def create_reconciliation(reconciliation_data: BankReconciliationCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    """Create a reconciliation with automatic payment creation and CFDI amount updates"""
    company_id = await get_active_company_id(request, current_user)
    
    bank_txn = await db.bank_transactions.find_one({'id': reconciliation_data.bank_transaction_id, 'company_id': company_id}, {'_id': 0})
    if not bank_txn:
        raise HTTPException(status_code=404, detail="Movimiento bancario no encontrado")
    
    # Check if this exact reconciliation already exists
    existing_recon = await db.reconciliations.find_one({
        'company_id': company_id,
        'bank_transaction_id': reconciliation_data.bank_transaction_id,
        'cfdi_id': reconciliation_data.cfdi_id
    }, {'_id': 0})
    if existing_recon:
        raise HTTPException(status_code=400, detail="Este CFDI ya está conciliado con este movimiento bancario")
    
    # If reconciling with a CFDI, automatically create payment if not exists
    if reconciliation_data.cfdi_id:
        cfdi = await db.cfdis.find_one({'id': reconciliation_data.cfdi_id, 'company_id': company_id}, {'_id': 0})
        if not cfdi:
            raise HTTPException(status_code=404, detail="CFDI no encontrado")
        
        # For partial payments: Check if CFDI still has saldo_pendiente
        # If CFDI is already fully paid (no saldo_pendiente), don't allow more reconciliations
        cfdi_total = cfdi.get('total', 0)
        if cfdi.get('tipo_cfdi') == 'ingreso':
            monto_cubierto = cfdi.get('monto_cobrado', 0) or 0
        else:
            monto_cubierto = cfdi.get('monto_pagado', 0) or 0
        saldo_pendiente = cfdi_total - monto_cubierto
        
        if saldo_pendiente < 0.01:
            raise HTTPException(status_code=400, detail="Este CFDI ya está completamente pagado. No hay saldo pendiente.")
        
        # Check if this exact bank transaction is already linked to this CFDI (duplicate prevention)
        # But allow same CFDI with DIFFERENT transactions for partial payments
        
        # Check if payment exists - prevent duplicates for same txn+cfdi combination
        payment_exists = await db.payments.find_one({
            'company_id': company_id,
            'bank_transaction_id': reconciliation_data.bank_transaction_id,
            'cfdi_id': reconciliation_data.cfdi_id
        }, {'_id': 0, 'id': 1})
        
        if not payment_exists:
            # Auto-create payment from reconciliation
            tipo_cfdi = cfdi.get('tipo_cfdi', '')
            tipo_pago = 'cobro' if tipo_cfdi == 'ingreso' else 'pago'
            moneda = bank_txn.get('moneda') or cfdi.get('moneda', 'MXN')
            
            # Determine beneficiario based on CFDI type:
            # - INGRESO (sales): beneficiario = receptor (customer who pays you)
            # - EGRESO (expenses): beneficiario = emisor (vendor you pay)
            # - NOMINA (payroll): beneficiario = receptor (employee you pay)
            if tipo_cfdi == 'ingreso':
                # Your company is the emisor, the customer is the receptor
                beneficiario_nombre = cfdi.get('receptor_nombre', '') or cfdi.get('emisor_nombre', '')
            elif tipo_cfdi == 'nomina':
                # Your company is the emisor, the employee is the receptor
                beneficiario_nombre = cfdi.get('receptor_nombre', '') or cfdi.get('emisor_nombre', '')
            else:
                # Egreso: the vendor is the emisor, your company is the receptor
                beneficiario_nombre = cfdi.get('emisor_nombre', '') or cfdi.get('receptor_nombre', '')
            
            # Use monto_aplicado for partial payments, otherwise use bank transaction amount
            monto_payment = reconciliation_data.monto_aplicado if reconciliation_data.monto_aplicado is not None else bank_txn.get('monto', 0)
            
            # Use category from reconciliation request if provided, otherwise inherit from CFDI
            category_id = reconciliation_data.categoria_id or cfdi.get('category_id')
            subcategory_text = reconciliation_data.subcategoria or cfdi.get('subcategory_id') or ''
            
            # If subcategory is provided as text and category exists, check if we need to create it
            subcategory_id = ''
            if subcategory_text and category_id:
                # Check if subcategory already exists (by name or id)
                existing_subcat = await db.subcategories.find_one({
                    'company_id': company_id,
                    'category_id': category_id,
                    '$or': [
                        {'id': subcategory_text},
                        {'nombre': {'$regex': f'^{subcategory_text}$', '$options': 'i'}}
                    ],
                    'activo': True
                }, {'_id': 0})
                
                if existing_subcat:
                    subcategory_id = existing_subcat.get('id')
                else:
                    # Create new subcategory
                    new_subcat_id = str(uuid.uuid4())
                    new_subcat = {
                        'id': new_subcat_id,
                        'company_id': company_id,
                        'category_id': category_id,
                        'nombre': subcategory_text,
                        'activo': True,
                        'created_at': datetime.now(timezone.utc).isoformat()
                    }
                    await db.subcategories.insert_one(new_subcat)
                    subcategory_id = new_subcat_id
                    logger.info(f"Created new subcategory: {subcategory_text} (ID: {new_subcat_id}) for category {category_id}")
            
            payment_doc = {
                'id': str(uuid.uuid4()),
                'company_id': company_id,
                'bank_account_id': bank_txn.get('bank_account_id'),
                'cfdi_id': reconciliation_data.cfdi_id,
                'tipo': tipo_pago,
                'concepto': f"Conciliación - {beneficiario_nombre}",
                'monto': monto_payment,  # Use partial or full amount
                'moneda': moneda,
                'metodo_pago': 'transferencia',
                'fecha_vencimiento': bank_txn.get('fecha_movimiento'),
                'fecha_pago': bank_txn.get('fecha_movimiento'),
                'estatus': 'completado',
                'referencia': bank_txn.get('referencia', ''),
                'beneficiario': beneficiario_nombre,
                'es_real': True,
                'bank_transaction_id': bank_txn.get('id'),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'auto_created_from_reconciliation': True,
                # Use category from reconciliation request (user-selected) or fallback to CFDI
                'category_id': category_id,
                'subcategory_id': subcategory,
                'cfdi_uuid': cfdi.get('uuid'),
                'cfdi_emisor': cfdi.get('emisor_nombre'),
                'cfdi_receptor': cfdi.get('receptor_nombre')
            }
            
            # Get historical FX rate for non-MXN currencies
            if moneda != 'MXN':
                rate = await db.fx_rates.find_one(
                    {'company_id': company_id, '$or': [
                        {'moneda_cotizada': moneda},
                        {'moneda_origen': moneda}
                    ]},
                    {'_id': 0},
                    sort=[('fecha_vigencia', -1)]
                )
                if rate:
                    payment_doc['tipo_cambio_historico'] = rate.get('tipo_cambio') or rate.get('tasa') or 1
            
            await db.payments.insert_one(payment_doc)
            
            # Update CFDI amounts
            if tipo_pago == 'cobro':
                current_cobrado = cfdi.get('monto_cobrado', 0) or 0
                new_cobrado = current_cobrado + payment_doc['monto']
                await db.cfdis.update_one(
                    {'id': reconciliation_data.cfdi_id},
                    {'$set': {'monto_cobrado': new_cobrado}}
                )
                # Check if CFDI is fully paid
                cfdi_total = cfdi.get('total', 0)
                is_fully_paid = new_cobrado >= cfdi_total - 0.01
            else:
                current_pagado = cfdi.get('monto_pagado', 0) or 0
                new_pagado = current_pagado + payment_doc['monto']
                await db.cfdis.update_one(
                    {'id': reconciliation_data.cfdi_id},
                    {'$set': {'monto_pagado': new_pagado}}
                )
                # Check if CFDI is fully paid
                cfdi_total = cfdi.get('total', 0)
                is_fully_paid = new_pagado >= cfdi_total - 0.01
        else:
            # Payment already exists - check if fully paid for status update
            cfdi_total = cfdi.get('total', 0)
            monto_cubierto = cfdi.get('monto_cobrado' if cfdi.get('tipo_cfdi') == 'ingreso' else 'monto_pagado', 0) or 0
            is_fully_paid = monto_cubierto >= cfdi_total - 0.01
        
        # Update CFDI estado_conciliacion: 'conciliado' if fully paid, 'parcial' if partial
        nuevo_estado = 'conciliado' if is_fully_paid else 'parcial'
        await db.cfdis.update_one(
            {'id': reconciliation_data.cfdi_id},
            {'$set': {'estado_conciliacion': nuevo_estado}}
        )
    
    reconciliation = BankReconciliation(
        company_id=company_id,
        user_id=current_user['id'],
        **reconciliation_data.model_dump()
    )
    
    doc = reconciliation.model_dump()
    for field in ['fecha_conciliacion', 'created_at']:
        doc[field] = doc[field].isoformat()
    await db.reconciliations.insert_one(doc)
    
    await db.bank_transactions.update_one({'id': reconciliation.bank_transaction_id}, {'$set': {'conciliado': True}})
    
    if reconciliation.transaction_id:
        await db.transactions.update_one({'id': reconciliation.transaction_id}, {'$set': {'es_real': True}})
    
    await audit_log(reconciliation.company_id, 'BankReconciliation', reconciliation.id, 'CREATE', current_user['id'])
    return reconciliation


@router.get("", response_model=List[BankReconciliation])
async def list_reconciliations(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    limit: int = Query(100, le=1000),
    skip: int = Query(0, ge=0)
):
    """List all reconciliations"""
    company_id = await get_active_company_id(request, current_user)
    reconciliations = await db.reconciliations.find(
        {'company_id': company_id},
        {'_id': 0}
    ).sort('fecha_conciliacion', -1).skip(skip).limit(limit).to_list(limit)
    
    for r in reconciliations:
        for field in ['fecha_conciliacion', 'created_at']:
            if isinstance(r.get(field), str):
                r[field] = datetime.fromisoformat(r[field])
    return reconciliations


@router.delete("/{reconciliation_id}")
async def delete_reconciliation(
    reconciliation_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Delete/cancel a reconciliation with full cleanup"""
    company_id = await get_active_company_id(request, current_user)
    
    recon = await db.reconciliations.find_one({'id': reconciliation_id, 'company_id': company_id}, {'_id': 0})
    if not recon:
        raise HTTPException(status_code=404, detail="Conciliación no encontrada")
    
    bank_txn_id = recon.get('bank_transaction_id')
    cfdi_id = recon.get('cfdi_id')
    monto_aplicado = recon.get('monto_aplicado')
    
    # If monto_aplicado is None (legacy reconciliations), try to get it from the payment or bank transaction
    if monto_aplicado is None and cfdi_id:
        # Try to find the associated payment to get the amount
        associated_payment = await db.payments.find_one({
            'company_id': company_id,
            'cfdi_id': cfdi_id,
            'bank_transaction_id': bank_txn_id
        }, {'_id': 0, 'monto': 1})
        if associated_payment:
            monto_aplicado = associated_payment.get('monto', 0)
        elif bank_txn_id:
            # Fall back to bank transaction amount
            bank_txn = await db.bank_transactions.find_one({'id': bank_txn_id}, {'_id': 0, 'monto': 1})
            if bank_txn:
                monto_aplicado = bank_txn.get('monto', 0)
    
    # Ensure monto_aplicado is a number
    monto_aplicado = float(monto_aplicado or 0)
    
    logger.info(f"Canceling reconciliation {reconciliation_id}: cfdi_id={cfdi_id}, monto_aplicado={monto_aplicado}")
    
    # Check if there are other reconciliations for this CFDI
    other_recons = 0
    if cfdi_id:
        other_recons = await db.reconciliations.count_documents({
            'company_id': company_id,
            'cfdi_id': cfdi_id,
            'id': {'$ne': reconciliation_id}
        })
    
    # Delete the reconciliation
    await db.reconciliations.delete_one({'id': reconciliation_id})
    
    # Mark bank transaction as not reconciled (only if no other reconciliations exist for it)
    if bank_txn_id:
        other_txn_recons = await db.reconciliations.count_documents({
            'company_id': company_id,
            'bank_transaction_id': bank_txn_id
        })
        if other_txn_recons == 0:
            await db.bank_transactions.update_one(
                {'id': bank_txn_id},
                {'$set': {'conciliado': False, 'payment_id': None, 'fecha_conciliacion': None}}
            )
    
    # Update CFDI - restore the paid/collected amount
    if cfdi_id:
        cfdi = await db.cfdis.find_one({'id': cfdi_id}, {'_id': 0})
        if cfdi:
            tipo_cfdi = cfdi.get('tipo_cfdi', '')
            cfdi_total = float(cfdi.get('total', 0) or 0)
            
            # Determine which field to update based on CFDI type
            if tipo_cfdi in ['ingreso', 'I']:
                # For income CFDIs, we reduce monto_cobrado
                current_cobrado = float(cfdi.get('monto_cobrado', 0) or 0)
                new_cobrado = max(0, current_cobrado - monto_aplicado)
                
                # Determine new status based on remaining amount
                if other_recons == 0 or new_cobrado < 0.01:
                    new_estado = 'pendiente'
                elif new_cobrado < cfdi_total - 0.01:
                    new_estado = 'parcial'
                else:
                    new_estado = 'pendiente'
                
                logger.info(f"CFDI {cfdi_id}: tipo=ingreso, cobrado {current_cobrado} -> {new_cobrado}, estado -> {new_estado}")
                
                await db.cfdis.update_one(
                    {'id': cfdi_id},
                    {'$set': {
                        'monto_cobrado': new_cobrado,
                        'estado_conciliacion': new_estado
                    }}
                )
            else:
                # For expense CFDIs, we reduce monto_pagado
                current_pagado = float(cfdi.get('monto_pagado', 0) or 0)
                new_pagado = max(0, current_pagado - monto_aplicado)
                
                # Determine new status based on remaining amount
                if other_recons == 0 or new_pagado < 0.01:
                    new_estado = 'pendiente'
                elif new_pagado < cfdi_total - 0.01:
                    new_estado = 'parcial'
                else:
                    new_estado = 'pendiente'
                
                logger.info(f"CFDI {cfdi_id}: tipo=egreso, pagado {current_pagado} -> {new_pagado}, estado -> {new_estado}")
                
                await db.cfdis.update_one(
                    {'id': cfdi_id},
                    {'$set': {
                        'monto_pagado': new_pagado,
                        'estado_conciliacion': new_estado
                    }}
                )
    
    # Delete auto-created payment if exists - search by both bank_txn_id AND cfdi_id
    payment_query = {'company_id': company_id, 'auto_created_from_reconciliation': True}
    if bank_txn_id and cfdi_id:
        payment_query['$or'] = [
            {'bank_transaction_id': bank_txn_id, 'cfdi_id': cfdi_id},
            {'bank_transaction_id': bank_txn_id},
            {'cfdi_id': cfdi_id}
        ]
    elif bank_txn_id:
        payment_query['bank_transaction_id'] = bank_txn_id
    elif cfdi_id:
        payment_query['cfdi_id'] = cfdi_id
    
    auto_payment = await db.payments.find_one(payment_query, {'_id': 0, 'id': 1})
    
    if auto_payment:
        await db.payments.delete_one({'id': auto_payment['id']})
    
    await audit_log(company_id, 'BankReconciliation', reconciliation_id, 'DELETE', current_user['id'])
    
    return {"status": "success", "message": "Conciliación cancelada correctamente"}


@router.get("/by-cfdi/{cfdi_id}")
async def get_reconciliations_by_cfdi(
    cfdi_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Get all reconciliations for a specific CFDI"""
    company_id = await get_active_company_id(request, current_user)
    
    reconciliations = await db.reconciliations.find(
        {'company_id': company_id, 'cfdi_id': cfdi_id},
        {'_id': 0}
    ).to_list(100)
    
    # Enrich with bank transaction info
    for r in reconciliations:
        if r.get('bank_transaction_id'):
            txn = await db.bank_transactions.find_one({'id': r['bank_transaction_id']}, {'_id': 0, 'descripcion': 1, 'monto': 1, 'moneda': 1, 'fecha_movimiento': 1})
            if txn:
                r['bank_transaction'] = txn
    
    return reconciliations


@router.get("/summary")
async def get_reconciliation_summary(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    fecha_desde: str = None,
    fecha_hasta: str = None
):
    """Get reconciliation summary with totals by type"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get all bank transactions
    txn_query = {'company_id': company_id}
    if fecha_desde or fecha_hasta:
        txn_query['fecha_movimiento'] = {}
        if fecha_desde:
            txn_query['fecha_movimiento']['$gte'] = fecha_desde
        if fecha_hasta:
            txn_query['fecha_movimiento']['$lte'] = fecha_hasta + 'T23:59:59'
    
    all_transactions = await db.bank_transactions.find(txn_query, {'_id': 0}).to_list(10000)
    
    # Get all reconciliations
    reconciliations = await db.reconciliations.find({'company_id': company_id}, {'_id': 0}).to_list(10000)
    recon_by_txn = {}
    for r in reconciliations:
        txn_id = r.get('bank_transaction_id')
        if txn_id not in recon_by_txn:
            recon_by_txn[txn_id] = []
        recon_by_txn[txn_id].append(r)
    
    # Calculate totals
    total_movimientos = len(all_transactions)
    total_monto = sum(t.get('monto', 0) for t in all_transactions)
    
    conciliados_con_uuid = []
    monto_con_uuid = 0
    conciliados_sin_uuid = []
    monto_sin_uuid = 0
    no_relacionados = []
    monto_no_relacionado = 0
    pendientes = []
    monto_pendiente = 0
    
    for txn in all_transactions:
        txn_id = txn.get('id')
        monto = txn.get('monto', 0)
        
        if txn.get('conciliado'):
            recons = recon_by_txn.get(txn_id, [])
            if recons:
                tipo = recons[0].get('tipo_conciliacion', 'con_uuid')
                has_cfdi = any(r.get('cfdi_id') for r in recons)
                
                if has_cfdi or tipo == 'con_uuid':
                    conciliados_con_uuid.append(txn)
                    monto_con_uuid += monto
                elif tipo == 'sin_uuid':
                    conciliados_sin_uuid.append(txn)
                    monto_sin_uuid += monto
                elif tipo == 'no_relacionado':
                    no_relacionados.append(txn)
                    monto_no_relacionado += monto
                else:
                    conciliados_con_uuid.append(txn)
                    monto_con_uuid += monto
            else:
                conciliados_con_uuid.append(txn)
                monto_con_uuid += monto
        else:
            pendientes.append(txn)
            monto_pendiente += monto
    
    # Get bank accounts for context
    bank_accounts = await db.bank_accounts.find({'company_id': company_id}, {'_id': 0}).to_list(100)
    
    return {
        'summary': {
            'total_movimientos': total_movimientos,
            'total_monto': round(total_monto, 2),
            'conciliados_con_uuid': len(conciliados_con_uuid),
            'monto_con_uuid': round(monto_con_uuid, 2),
            'conciliados_sin_uuid': len(conciliados_sin_uuid),
            'monto_sin_uuid': round(monto_sin_uuid, 2),
            'no_relacionados': len(no_relacionados),
            'monto_no_relacionado': round(monto_no_relacionado, 2),
            'pendientes': len(pendientes),
            'monto_pendiente': round(monto_pendiente, 2),
            'porcentaje_conciliado': round((total_movimientos - len(pendientes)) / total_movimientos * 100, 1) if total_movimientos > 0 else 0
        },
        'by_account': [
            {
                'account_id': acc['id'],
                'banco': acc.get('banco', ''),
                'nombre': acc.get('nombre', ''),
                'moneda': acc.get('moneda', 'MXN'),
                'total_movimientos': len([t for t in all_transactions if t.get('bank_account_id') == acc['id']]),
                'conciliados': len([t for t in all_transactions if t.get('bank_account_id') == acc['id'] and t.get('conciliado')]),
                'pendientes': len([t for t in all_transactions if t.get('bank_account_id') == acc['id'] and not t.get('conciliado')])
            }
            for acc in bank_accounts
        ]
    }


@router.post("/mark-without-uuid")
async def mark_reconciliation_without_uuid(
    data: dict,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Mark a bank transaction as reconciled WITHOUT a UUID (no CFDI relationship)"""
    company_id = await get_active_company_id(request, current_user)
    
    bank_transaction_id = data.get('bank_transaction_id')
    tipo_conciliacion = data.get('tipo_conciliacion', 'sin_uuid')
    notas = data.get('notas', '')
    categoria = data.get('categoria', '')
    concepto = data.get('concepto', '')
    category_id = data.get('category_id')  # Support category selection
    
    if not bank_transaction_id:
        raise HTTPException(status_code=400, detail="Se requiere bank_transaction_id")
    
    if tipo_conciliacion not in ['sin_uuid', 'no_relacionado']:
        raise HTTPException(status_code=400, detail="tipo_conciliacion debe ser 'sin_uuid' o 'no_relacionado'")
    
    txn = await db.bank_transactions.find_one({'id': bank_transaction_id, 'company_id': company_id}, {'_id': 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Movimiento bancario no encontrado")
    
    tipo_pago = 'cobro' if txn.get('tipo_movimiento') == 'credito' else 'pago'
    moneda = txn.get('moneda', 'MXN')
    
    # Generate description
    if concepto:
        descripcion = concepto
    elif categoria == 'comision_bancaria':
        descripcion = f"Comisión bancaria - {txn.get('descripcion', '')[:50]}"
    elif categoria == 'gasto_sin_factura':
        descripcion = f"Gasto sin factura - {txn.get('descripcion', '')[:50]}"
    else:
        descripcion = txn.get('descripcion') or f"Movimiento bancario {txn.get('referencia', '')}"
    
    payment_doc = {
        'id': str(uuid.uuid4()),
        'company_id': company_id,
        'bank_account_id': txn.get('bank_account_id'),
        'cfdi_id': None,
        'tipo': tipo_pago,
        'concepto': descripcion[:200],
        'monto': txn.get('monto', 0),
        'moneda': moneda,
        'metodo_pago': 'transferencia',
        'fecha_vencimiento': txn.get('fecha_movimiento'),
        'fecha_pago': txn.get('fecha_movimiento'),
        'estatus': 'completado',
        'referencia': txn.get('referencia', ''),
        'beneficiario': txn.get('merchant_name') or '',
        'notas': notas,
        'es_real': True,
        'bank_transaction_id': bank_transaction_id,
        'sin_uuid': True,
        'categoria_gasto': categoria,
        'category_id': category_id,
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Get historical FX rate
    if moneda != 'MXN':
        rate = await db.fx_rates.find_one(
            {'company_id': company_id, '$or': [
                {'moneda_cotizada': moneda},
                {'moneda_origen': moneda}
            ]},
            {'_id': 0},
            sort=[('fecha_vigencia', -1)]
        )
        if rate:
            payment_doc['tipo_cambio_historico'] = rate.get('tipo_cambio') or rate.get('tasa') or 1
    
    await db.payments.insert_one(payment_doc)
    
    # Create reconciliation record without CFDI
    reconciliation = BankReconciliation(
        company_id=company_id,
        user_id=current_user['id'],
        bank_transaction_id=bank_transaction_id,
        cfdi_id=None,
        transaction_id=None,
        metodo_conciliacion='manual',
        tipo_conciliacion=tipo_conciliacion,
        porcentaje_match=100.0,
        notas=notas
    )
    
    doc = reconciliation.model_dump()
    for field in ['fecha_conciliacion', 'created_at']:
        doc[field] = doc[field].isoformat()
    await db.reconciliations.insert_one(doc)
    
    # Mark transaction as reconciled
    await db.bank_transactions.update_one(
        {'id': bank_transaction_id},
        {'$set': {
            'conciliado': True, 
            'tipo_conciliacion': tipo_conciliacion,
            'payment_id': payment_doc['id']
        }}
    )
    
    await audit_log(company_id, 'BankReconciliation', reconciliation.id, 'CREATE', current_user['id'], 
                    {'tipo': tipo_conciliacion, 'sin_uuid': True, 'payment_created': True})
    
    return {
        'status': 'success',
        'message': f'Movimiento marcado como conciliado ({tipo_conciliacion})',
        'reconciliation_id': reconciliation.id,
        'payment_id': payment_doc['id'],
        'payment_tipo': tipo_pago,
        'payment_monto': payment_doc['monto']
    }


@router.delete("/bulk/all")
async def delete_all_reconciliations(request: Request, current_user: Dict = Depends(get_current_user)):
    """Delete ALL reconciliations for the current company and reset bank transaction status"""
    company_id = await get_active_company_id(request, current_user)
    
    # Delete all reconciliation records
    result = await db.reconciliations.delete_many({'company_id': company_id})
    
    # Reset all bank transactions to not conciliado
    await db.bank_transactions.update_many(
        {'company_id': company_id},
        {'$set': {'conciliado': False, 'tipo_conciliacion': None}}
    )
    
    await audit_log(company_id, 'BankReconciliation', 'BULK_DELETE', 'DELETE', current_user['id'], 
                    {'count': result.deleted_count, 'action': 'delete_all_reconciliations'})
    
    return {
        'status': 'success',
        'message': f'Se eliminaron {result.deleted_count} conciliaciones y se reseteron todos los movimientos',
        'deleted_count': result.deleted_count
    }
