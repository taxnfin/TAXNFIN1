"""Reconciliation routes"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Dict, List, Optional
from datetime import datetime, timezone

from core.database import db
from core.auth import get_current_user, get_active_company_id
from models.bank import BankReconciliation, BankReconciliationCreate
from services.audit import audit_log

router = APIRouter(prefix="/reconciliations")


@router.post("", response_model=BankReconciliation)
async def create_reconciliation(reconciliation_data: BankReconciliationCreate, current_user: Dict = Depends(get_current_user)):
    """Create a new reconciliation"""
    bank_txn = await db.bank_transactions.find_one({'id': reconciliation_data.bank_transaction_id, 'company_id': current_user['company_id']}, {'_id': 0})
    if not bank_txn:
        raise HTTPException(status_code=404, detail="Movimiento bancario no encontrado")
    
    # P1 FIX: Validate that a payment record exists when linking to a CFDI
    if reconciliation_data.cfdi_id:
        payment_exists = await db.payments.find_one({
            'company_id': current_user['company_id'],
            'cfdi_id': reconciliation_data.cfdi_id
        }, {'_id': 0, 'id': 1})
        
        if not payment_exists:
            raise HTTPException(
                status_code=400, 
                detail="No se puede conciliar con este CFDI porque no existe un registro de pago/cobro asociado. "
                       "Primero registra el pago/cobro en el módulo 'Cobranza y Pagos' y luego intenta conciliar."
            )
    
    reconciliation = BankReconciliation(
        company_id=current_user['company_id'],
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
    current_user: Dict = Depends(get_current_user),
    limit: int = Query(100, le=1000),
    skip: int = Query(0, ge=0)
):
    """List all reconciliations"""
    reconciliations = await db.reconciliations.find(
        {'company_id': current_user['company_id']},
        {'_id': 0}
    ).sort('fecha_conciliacion', -1).skip(skip).limit(limit).to_list(limit)
    
    for r in reconciliations:
        for field in ['fecha_conciliacion', 'created_at']:
            if isinstance(r.get(field), str):
                r[field] = datetime.fromisoformat(r[field])
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
    
    txn_query = {'company_id': company_id}
    if fecha_desde or fecha_hasta:
        txn_query['fecha_movimiento'] = {}
        if fecha_desde:
            txn_query['fecha_movimiento']['$gte'] = fecha_desde
        if fecha_hasta:
            txn_query['fecha_movimiento']['$lte'] = fecha_hasta + 'T23:59:59'
    
    all_transactions = await db.bank_transactions.find(txn_query, {'_id': 0}).to_list(10000)
    reconciliations = await db.reconciliations.find({'company_id': company_id}, {'_id': 0}).to_list(10000)
    
    recon_by_txn = {}
    for r in reconciliations:
        txn_id = r.get('bank_transaction_id')
        if txn_id not in recon_by_txn:
            recon_by_txn[txn_id] = []
        recon_by_txn[txn_id].append(r)
    
    pendientes = []
    conciliados_con_uuid = []
    no_relacionados = []
    conciliados_sin_uuid = []
    
    total_depositos = 0
    total_retiros = 0
    total_movimientos = len(all_transactions)
    
    for txn in all_transactions:
        monto = txn.get('monto', 0)
        if txn.get('tipo_movimiento') == 'credito':
            total_depositos += monto
        else:
            total_retiros += monto
        
        if txn.get('conciliado'):
            txn_id = txn.get('id')
            recons = recon_by_txn.get(txn_id, [])
            if recons:
                tipo = recons[0].get('tipo_conciliacion', 'con_uuid')
                if tipo == 'no_relacionado':
                    no_relacionados.append(txn)
                elif tipo == 'sin_uuid':
                    conciliados_sin_uuid.append(txn)
                else:
                    conciliados_con_uuid.append(txn)
            else:
                conciliados_con_uuid.append(txn)
        else:
            pendientes.append(txn)
    
    # Get bank accounts
    accounts = await db.bank_accounts.find({'company_id': company_id, 'activo': True}, {'_id': 0}).to_list(100)
    
    return {
        'totales': {
            'total_movimientos': total_movimientos,
            'total_depositos': total_depositos,
            'total_retiros': total_retiros,
            'conciliados_con_uuid': len(conciliados_con_uuid),
            'no_relacionados': len(no_relacionados),
            'conciliados_sin_uuid': len(conciliados_sin_uuid),
            'pendientes': len(pendientes),
            'porcentaje_conciliado': round((total_movimientos - len(pendientes)) / total_movimientos * 100, 1) if total_movimientos > 0 else 0
        },
        'por_cuenta': [
            {
                'cuenta_id': acc['id'],
                'banco': acc.get('banco', ''),
                'nombre': acc.get('nombre', ''),
                'moneda': acc.get('moneda', 'MXN'),
                'conciliados': len([t for t in all_transactions if t.get('bank_account_id') == acc['id'] and t.get('conciliado')]),
                'pendientes': len([t for t in all_transactions if t.get('bank_account_id') == acc['id'] and not t.get('conciliado')])
            }
            for acc in accounts
        ]
    }


@router.post("/mark-without-uuid")
async def mark_without_uuid(
    data: dict,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Mark a bank transaction as reconciled without a CFDI UUID"""
    company_id = await get_active_company_id(request, current_user)
    
    bank_transaction_id = data.get('bank_transaction_id')
    tipo_conciliacion = data.get('tipo_conciliacion', 'sin_uuid')
    notas = data.get('notas', '')
    
    if not bank_transaction_id:
        raise HTTPException(status_code=400, detail="Se requiere bank_transaction_id")
    
    if tipo_conciliacion not in ['sin_uuid', 'no_relacionado']:
        raise HTTPException(status_code=400, detail="tipo_conciliacion debe ser 'sin_uuid' o 'no_relacionado'")
    
    txn = await db.bank_transactions.find_one({'id': bank_transaction_id, 'company_id': company_id}, {'_id': 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Movimiento bancario no encontrado")
    
    reconciliation = BankReconciliation(
        company_id=company_id,
        bank_transaction_id=bank_transaction_id,
        transaction_id=None,
        cfdi_id=None,
        metodo_conciliacion='manual',
        tipo_conciliacion=tipo_conciliacion,
        porcentaje_match=100.0,
        user_id=current_user['id'],
        notas=notas
    )
    
    doc = reconciliation.model_dump()
    for field in ['fecha_conciliacion', 'created_at']:
        doc[field] = doc[field].isoformat()
    await db.reconciliations.insert_one(doc)
    
    await db.bank_transactions.update_one(
        {'id': bank_transaction_id},
        {'$set': {'conciliado': True, 'tipo_conciliacion': tipo_conciliacion}}
    )
    
    await audit_log(company_id, 'BankReconciliation', reconciliation.id, 'CREATE', current_user['id'], 
                    {'tipo': tipo_conciliacion, 'sin_uuid': True})
    
    return {
        'status': 'success',
        'message': f'Movimiento marcado como conciliado ({tipo_conciliacion})',
        'reconciliation_id': reconciliation.id
    }


@router.delete("/bulk/all")
async def delete_all_reconciliations(request: Request, current_user: Dict = Depends(get_current_user)):
    """Delete ALL reconciliations for the current company and reset bank transaction status"""
    company_id = await get_active_company_id(request, current_user)
    
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
        'deleted_count': result.deleted_count,
        'message': f'Se eliminaron {result.deleted_count} conciliaciones y se reseteron todos los movimientos',
    }
