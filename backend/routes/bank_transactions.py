"""Bank Transactions routes - Bank statement management"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id
from models.bank import BankTransaction, BankTransactionCreate
from services.audit import audit_log

router = APIRouter(prefix="/bank-transactions")
logger = logging.getLogger(__name__)


@router.post("", response_model=BankTransaction)
async def create_bank_transaction(
    transaction_data: BankTransactionCreate, 
    request: Request, 
    current_user: Dict = Depends(get_current_user)
):
    """Create a new bank transaction"""
    company_id = await get_active_company_id(request, current_user)
    account = await db.bank_accounts.find_one({'id': transaction_data.bank_account_id, 'company_id': company_id}, {'_id': 0})
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    
    # Use account's currency if not specified in transaction
    txn_data = transaction_data.model_dump()
    if not txn_data.get('moneda'):
        txn_data['moneda'] = account.get('moneda', 'MXN')
    
    bank_transaction = BankTransaction(company_id=company_id, **txn_data)
    doc = bank_transaction.model_dump()
    for field in ['fecha_movimiento', 'fecha_valor', 'created_at']:
        if doc.get(field):
            doc[field] = doc[field].isoformat()
    await db.bank_transactions.insert_one(doc)
    
    await audit_log(bank_transaction.company_id, 'BankTransaction', bank_transaction.id, 'CREATE', current_user['id'])
    return bank_transaction


@router.get("", response_model=List[BankTransaction])
async def list_bank_transactions(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    bank_account_id: Optional[str] = Query(None),
    conciliado: Optional[bool] = Query(None),
    fecha_desde: Optional[str] = Query(None),
    fecha_hasta: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    skip: int = Query(0, ge=0)
):
    """List bank transactions with optional filters"""
    company_id = await get_active_company_id(request, current_user)
    
    query = {'company_id': company_id}
    if bank_account_id:
        query['bank_account_id'] = bank_account_id
    if conciliado is not None:
        query['conciliado'] = conciliado
    if fecha_desde or fecha_hasta:
        query['fecha_movimiento'] = {}
        if fecha_desde:
            query['fecha_movimiento']['$gte'] = fecha_desde
        if fecha_hasta:
            query['fecha_movimiento']['$lte'] = fecha_hasta + 'T23:59:59'
    
    transactions = await db.bank_transactions.find(
        query,
        {'_id': 0}
    ).sort('fecha_movimiento', -1).skip(skip).limit(limit).to_list(limit)
    
    for t in transactions:
        for field in ['fecha_movimiento', 'fecha_valor', 'created_at']:
            if isinstance(t.get(field), str):
                try:
                    t[field] = datetime.fromisoformat(t[field])
                except:
                    pass
    return transactions


@router.get("/{transaction_id}")
async def get_bank_transaction(
    transaction_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Get a single bank transaction"""
    company_id = await get_active_company_id(request, current_user)
    
    txn = await db.bank_transactions.find_one(
        {'id': transaction_id, 'company_id': company_id},
        {'_id': 0}
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    return txn


@router.put("/{transaction_id}")
async def update_bank_transaction(
    transaction_id: str,
    data: dict,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Update a bank transaction"""
    company_id = await get_active_company_id(request, current_user)
    
    txn = await db.bank_transactions.find_one(
        {'id': transaction_id, 'company_id': company_id},
        {'_id': 0}
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    # Don't allow editing reconciled transactions (except notes)
    if txn.get('conciliado') and not (len(data) == 1 and 'notas' in data):
        raise HTTPException(status_code=400, detail="No se puede editar un movimiento conciliado")
    
    # Convert date fields
    for field in ['fecha_movimiento', 'fecha_valor']:
        if field in data and data[field]:
            if isinstance(data[field], str):
                pass  # Keep as string
            elif hasattr(data[field], 'isoformat'):
                data[field] = data[field].isoformat()
    
    await db.bank_transactions.update_one(
        {'id': transaction_id, 'company_id': company_id},
        {'$set': data}
    )
    
    await audit_log(company_id, 'BankTransaction', transaction_id, 'UPDATE', current_user['id'])
    return {'status': 'success', 'message': 'Movimiento actualizado'}


@router.delete("/{transaction_id}")
async def delete_bank_transaction(
    transaction_id: str, 
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Delete a bank transaction"""
    company_id = await get_active_company_id(request, current_user)
    
    txn = await db.bank_transactions.find_one({'id': transaction_id, 'company_id': company_id}, {'_id': 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    # Check if it's reconciled
    if txn.get('conciliado'):
        raise HTTPException(status_code=400, detail="No se puede eliminar un movimiento conciliado. Cancele primero la conciliación.")
    
    # Delete the transaction
    result = await db.bank_transactions.delete_one({'id': transaction_id, 'company_id': company_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    await audit_log(company_id, 'BankTransaction', transaction_id, 'DELETE', current_user['id'])
    return {"status": "success", "message": "Movimiento eliminado"}


@router.get("/{txn_id}/match-cfdi")
async def get_cfdi_matches_for_transaction(
    txn_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Find potential CFDI matches for a bank transaction"""
    company_id = await get_active_company_id(request, current_user)
    
    txn = await db.bank_transactions.find_one({'id': txn_id, 'company_id': company_id}, {'_id': 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    monto = txn.get('monto', 0)
    tipo = txn.get('tipo_movimiento', '')
    moneda = txn.get('moneda', 'MXN')
    descripcion = txn.get('descripcion', '').lower()
    
    # Determine CFDI type based on transaction type
    tipo_cfdi = 'ingreso' if tipo == 'credito' else 'egreso'
    
    # Find matching CFDIs
    query = {
        'company_id': company_id,
        'tipo_cfdi': tipo_cfdi,
        'estado_conciliacion': {'$ne': 'conciliado'},
        'moneda': moneda
    }
    
    cfdis = await db.cfdis.find(query, {'_id': 0, 'xml_original': 0}).to_list(1000)
    
    matches = []
    for cfdi in cfdis:
        cfdi_total = cfdi.get('total', 0)
        cfdi_emisor = cfdi.get('emisor_nombre', '').lower()
        cfdi_receptor = cfdi.get('receptor_nombre', '').lower()
        
        # Calculate match score
        score = 0
        
        # Amount match (exact or close)
        if abs(cfdi_total - monto) < 0.01:
            score += 50
        elif abs(cfdi_total - monto) / max(cfdi_total, monto) < 0.05:
            score += 30
        elif abs(cfdi_total - monto) / max(cfdi_total, monto) < 0.10:
            score += 15
        
        # Name match in description
        if cfdi_emisor and cfdi_emisor in descripcion:
            score += 30
        if cfdi_receptor and cfdi_receptor in descripcion:
            score += 30
        
        # Only include if score > 0
        if score > 0:
            matches.append({
                'cfdi': cfdi,
                'score': score,
                'match_reasons': []
            })
    
    # Sort by score
    matches.sort(key=lambda x: x['score'], reverse=True)
    
    return {'matches': matches[:10], 'total_candidates': len(matches)}


@router.post("/check-duplicates")
async def check_duplicate_transactions(
    data: dict,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Check for potential duplicate transactions"""
    company_id = await get_active_company_id(request, current_user)
    
    transactions = data.get('transactions', [])
    duplicates = []
    
    for txn in transactions:
        # Check if similar transaction exists
        fecha = txn.get('fecha_movimiento', '')
        monto = txn.get('monto', 0)
        referencia = txn.get('referencia', '')
        
        query = {
            'company_id': company_id,
            'monto': monto
        }
        
        if fecha:
            query['fecha_movimiento'] = {'$regex': fecha[:10]}
        if referencia:
            query['referencia'] = referencia
        
        existing = await db.bank_transactions.find_one(query, {'_id': 0})
        if existing:
            duplicates.append({
                'new': txn,
                'existing': existing
            })
    
    return {'duplicates': duplicates, 'count': len(duplicates)}


@router.delete("/bulk/all")
async def delete_all_bank_transactions(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Delete ALL bank transactions for the current company"""
    company_id = await get_active_company_id(request, current_user)
    
    # First delete all reconciliations
    await db.reconciliations.delete_many({'company_id': company_id})
    
    # Delete all payments linked to bank transactions
    await db.payments.delete_many({'company_id': company_id, 'bank_transaction_id': {'$exists': True}})
    
    # Delete all bank transactions
    result = await db.bank_transactions.delete_many({'company_id': company_id})
    
    await audit_log(company_id, 'BankTransaction', 'BULK_DELETE', 'DELETE', current_user['id'],
                    {'count': result.deleted_count})
    
    return {
        'status': 'success',
        'message': f'Se eliminaron {result.deleted_count} movimientos bancarios',
        'deleted_count': result.deleted_count
    }
