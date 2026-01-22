"""Bank accounts routes"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, List
from datetime import datetime

from core.database import db
from core.auth import get_current_user, get_active_company_id
from models.bank import BankAccount, BankAccountCreate
from services.audit import audit_log
from services.fx import get_fx_rate_by_date

router = APIRouter(prefix="/bank-accounts")


@router.post("", response_model=BankAccount)
async def create_bank_account(account_data: BankAccountCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    """Create a new bank account"""
    company_id = await get_active_company_id(request, current_user)
    account = BankAccount(company_id=company_id, **account_data.model_dump())
    doc = account.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.bank_accounts.insert_one(doc)
    await audit_log(account.company_id, 'BankAccount', account.id, 'CREATE', current_user['id'])
    return account


@router.get("", response_model=List[BankAccount])
async def list_bank_accounts(request: Request, current_user: Dict = Depends(get_current_user)):
    """List all bank accounts for current company"""
    company_id = await get_active_company_id(request, current_user)
    accounts = await db.bank_accounts.find({'company_id': company_id, 'activo': True}, {'_id': 0}).to_list(1000)
    for a in accounts:
        if isinstance(a.get('created_at'), str):
            a['created_at'] = datetime.fromisoformat(a['created_at'])
    return accounts


@router.put("/{account_id}")
async def update_bank_account(account_id: str, account_data: BankAccountCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    """Update a bank account"""
    company_id = await get_active_company_id(request, current_user)
    existing = await db.bank_accounts.find_one({'id': account_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    
    update_data = account_data.model_dump()
    await db.bank_accounts.update_one(
        {'id': account_id, 'company_id': company_id},
        {'$set': update_data}
    )
    await audit_log(company_id, 'BankAccount', account_id, 'UPDATE', current_user['id'], existing, update_data)
    
    updated = await db.bank_accounts.find_one({'id': account_id}, {'_id': 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return updated


@router.delete("/{account_id}")
async def delete_bank_account(account_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Delete (soft) a bank account"""
    company_id = await get_active_company_id(request, current_user)
    existing = await db.bank_accounts.find_one({'id': account_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    
    await db.bank_accounts.update_one(
        {'id': account_id},
        {'$set': {'activo': False}}
    )
    await audit_log(company_id, 'BankAccount', account_id, 'DELETE', current_user['id'])
    return {'status': 'success', 'message': 'Cuenta bancaria eliminada'}


@router.get("/summary")
async def get_bank_accounts_summary(request: Request, current_user: Dict = Depends(get_current_user)):
    """Get summary of all bank accounts with balances by currency"""
    company_id = await get_active_company_id(request, current_user)
    
    accounts = await db.bank_accounts.find({'company_id': company_id, 'activo': True}, {'_id': 0}).to_list(1000)
    
    by_currency = {}
    by_bank = {}
    total_mxn = 0
    
    for acc in accounts:
        moneda = acc.get('moneda', 'MXN')
        banco = acc.get('banco', 'Sin banco')
        saldo = acc.get('saldo_inicial', 0)
        fecha_saldo = acc.get('fecha_saldo')
        
        if fecha_saldo:
            if isinstance(fecha_saldo, str):
                fecha_saldo = datetime.fromisoformat(fecha_saldo.replace('Z', '+00:00'))
            rate = await get_fx_rate_by_date(company_id, moneda, fecha_saldo)
        else:
            rate = await get_fx_rate_by_date(company_id, moneda, None)
        
        if moneda not in by_currency:
            by_currency[moneda] = {'saldo': 0, 'cuentas': 0, 'saldo_mxn': 0}
        by_currency[moneda]['saldo'] += saldo
        by_currency[moneda]['cuentas'] += 1
        
        saldo_mxn = saldo * rate if moneda != 'MXN' else saldo
        by_currency[moneda]['saldo_mxn'] += saldo_mxn
        
        if banco not in by_bank:
            by_bank[banco] = {'saldo_mxn': 0, 'cuentas': [], 'monedas': set()}
        
        by_bank[banco]['saldo_mxn'] += saldo_mxn
        by_bank[banco]['cuentas'].append({
            'id': acc.get('id', ''),
            'nombre': acc.get('nombre', acc.get('nombre_banco', 'Sin nombre')),
            'numero_cuenta': acc.get('numero_cuenta', ''),
            'moneda': moneda,
            'saldo': saldo,
            'saldo_mxn': saldo_mxn,
            'fecha_saldo': acc.get('fecha_saldo'),
            'tipo_cambio_usado': rate
        })
        by_bank[banco]['monedas'].add(moneda)
        
        total_mxn += saldo_mxn
    
    for banco in by_bank:
        by_bank[banco]['monedas'] = list(by_bank[banco]['monedas'])
    
    fx_rates = {'MXN': 1.0}
    rates_docs = await db.fx_rates.find({'company_id': company_id}).sort('fecha_vigencia', -1).to_list(100)
    for r in rates_docs:
        moneda = r.get('moneda_cotizada') or r.get('moneda_origen')
        tasa = r.get('tipo_cambio') or r.get('tasa')
        if moneda and tasa and moneda not in fx_rates:
            fx_rates[moneda] = tasa
    
    return {
        'total_cuentas': len(accounts),
        'total_mxn': total_mxn,
        'por_moneda': by_currency,
        'por_banco': by_bank,
        'tipos_cambio': fx_rates
    }
