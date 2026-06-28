"""Bank accounts routes"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, List
from datetime import datetime
import uuid

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
        {'id': account_id, 'company_id': company_id},
        {'$set': {'activo': False}}
    )
    await audit_log(company_id, 'BankAccount', account_id, 'DELETE', current_user['id'])
    return {'status': 'success', 'message': 'Cuenta bancaria eliminada'}


@router.get("/summary")
async def get_bank_accounts_summary(request: Request, current_user: Dict = Depends(get_current_user)):
    """Get summary of all bank accounts with balances by currency.
    
    Acepta query param ?fecha=YYYY-MM-DD para obtener el saldo histórico
    más cercano anterior o igual a esa fecha. Sin fecha usa saldo_inicial actual.
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Fecha de referencia opcional (para que el dashboard filtre por mes)
    fecha_ref = request.query_params.get('fecha') or None
    
    accounts = await db.bank_accounts.find({'company_id': company_id, 'activo': True}, {'_id': 0}).to_list(1000)
    
    by_currency = {}
    by_bank = {}
    total_mxn = 0
    
    for acc in accounts:
        moneda = acc.get('moneda', 'MXN')
        banco = acc.get('banco', 'Sin banco')
        acct_id = acc.get('id', '')
        
        # Si hay fecha_ref, buscar saldo histórico más cercano <= fecha_ref
        # Usamos find+sort+limit para obtener solo el más reciente (evita duplicados)
        if fecha_ref:
            hist_cursor = db.bank_account_history.find(
                {'account_id': acct_id, 'company_id': company_id, 'fecha': {'$lte': fecha_ref}},
                {'_id': 0, 'saldo': 1, 'fecha': 1},
            ).sort('fecha', -1).limit(1)
            hist_list = await hist_cursor.to_list(1)
            hist = hist_list[0] if hist_list else None
            if hist:
                saldo = float(hist.get('saldo', 0) or 0)
                fecha_saldo = hist.get('fecha')
            else:
                saldo = acc.get('saldo_inicial', 0)
                fecha_saldo = acc.get('fecha_saldo')
        else:
            saldo = acc.get('saldo_inicial', 0)
            fecha_saldo = acc.get('fecha_saldo')
        
        if fecha_saldo:
            if isinstance(fecha_saldo, str):
                fecha_saldo_dt = datetime.fromisoformat(fecha_saldo.replace('Z', '+00:00').split('+')[0])
            else:
                fecha_saldo_dt = fecha_saldo
            rate = await get_fx_rate_by_date(company_id, moneda, fecha_saldo_dt)
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
            'id': acct_id,
            'nombre': acc.get('nombre', acc.get('nombre_banco', 'Sin nombre')),
            'numero_cuenta': acc.get('numero_cuenta', ''),
            'moneda': moneda,
            'saldo': saldo,
            'saldo_mxn': saldo_mxn,
            'fecha_saldo': fecha_saldo,
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
        'tipos_cambio': fx_rates,
        'fecha_ref': fecha_ref,
    }


@router.patch("/{account_id}/saldo")
async def update_saldo(
    account_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Actualiza el saldo inicial y fecha de saldo de una cuenta bancaria."""
    company_id = await get_active_company_id(request, current_user)
    body = await request.json()
    
    existing = await db.bank_accounts.find_one(
        {'id': account_id, 'company_id': company_id}, {'_id': 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    
    update = {}
    if 'saldo_inicial' in body:
        update['saldo_inicial'] = float(body['saldo_inicial'])
    if 'fecha_saldo' in body:
        update['fecha_saldo'] = body['fecha_saldo']
    
    if not update:
        raise HTTPException(status_code=400, detail="Nada que actualizar")
    
    await db.bank_accounts.update_one(
        {'id': account_id, 'company_id': company_id},
        {'$set': update}
    )
    
    return {
        'success': True,
        'account_id': account_id,
        **update
    }


@router.post("/{account_id}/history")
async def add_saldo_history(
    account_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """
    Registra un saldo histórico verificado para una cuenta bancaria.
    Si ya existe una entrada para esa fecha, la ACTUALIZA en lugar de duplicar.
    """
    company_id = await get_active_company_id(request, current_user)
    body = await request.json()

    existing = await db.bank_accounts.find_one(
        {'id': account_id, 'company_id': company_id}, {'_id': 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    saldo = body.get('saldo')
    fecha = body.get('fecha')
    if saldo is None or not fecha:
        raise HTTPException(status_code=400, detail="Se requieren 'saldo' y 'fecha'")

    # Upsert: actualizar si ya existe para esa fecha, insertar si no
    existing_hist = await db.bank_account_history.find_one(
        {'account_id': account_id, 'company_id': company_id, 'fecha': fecha},
        {'_id': 0, 'id': 1}
    )

    if existing_hist:
        # Actualizar entrada existente
        await db.bank_account_history.update_one(
            {'account_id': account_id, 'company_id': company_id, 'fecha': fecha},
            {'$set': {
                'saldo': float(saldo),
                'fuente': body.get('fuente', 'manual'),
                'notas': body.get('notas', ''),
                'updated_at': datetime.utcnow().isoformat(),
            }}
        )
        doc_id = existing_hist['id']
    else:
        # Insertar nueva entrada
        doc = {
            'id': str(uuid.uuid4()),
            'account_id': account_id,
            'company_id': company_id,
            'moneda': existing.get('moneda', 'MXN'),
            'saldo': float(saldo),
            'fecha': fecha,
            'fuente': body.get('fuente', 'manual'),
            'notas': body.get('notas', ''),
            'created_at': datetime.utcnow().isoformat(),
            'created_by': current_user.get('id', ''),
        }
        await db.bank_account_history.insert_one(doc)
        doc_id = doc['id']

    # Actualizar saldo_actual en bank_accounts si esta fecha es más reciente
    fecha_actual = existing.get('fecha_saldo', '')
    if not fecha_actual or fecha > fecha_actual:
        await db.bank_accounts.update_one(
            {'id': account_id, 'company_id': company_id},
            {'$set': {'saldo_inicial': float(saldo), 'fecha_saldo': fecha}}
        )

    return {
        'success': True,
        'id': doc_id,
        'account_id': account_id,
        'saldo': float(saldo),
        'fecha': fecha,
        'moneda': existing.get('moneda', 'MXN'),
        'updated': existing_hist is not None,
    }


@router.get("/{account_id}/history")
async def get_saldo_history(
    account_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Lista el historial de saldos verificados de una cuenta bancaria."""
    company_id = await get_active_company_id(request, current_user)

    existing = await db.bank_accounts.find_one(
        {'id': account_id, 'company_id': company_id}, {'_id': 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    history = await db.bank_account_history.find(
        {'account_id': account_id, 'company_id': company_id},
        {'_id': 0}
    ).sort('fecha', 1).to_list(200)

    return {'account_id': account_id, 'history': history}


@router.post("/deduplicate-transactions")
async def deduplicate_bank_transactions(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    dry_run: bool = Query(True, description="Si True, solo reporta sin eliminar"),
):
    """Elimina duplicados en bank_transactions. Solo admin/cfo."""
    from collections import defaultdict

    company_id = await get_active_company_id(request, current_user)
    GENERIC_CATS = {'cobro_alegra', 'banco_alegra', 'pago_alegra', '', None}

    txns = await db.bank_transactions.find(
        {'company_id': company_id},
        {'_id': 0, 'id': 1, 'fecha': 1, 'monto': 1, 'tipo': 1,
         'contacto': 1, 'category_name': 1}
    ).to_list(50000)

    groups = defaultdict(list)
    for t in txns:
        fecha    = str(t.get('fecha', ''))[:10]
        monto    = round(float(t.get('monto', 0) or 0), 2)
        tipo     = t.get('tipo', '') or ''
        contacto = t.get('contacto', '') or ''
        groups[(fecha, monto, tipo, contacto)].append(t)

    ids_to_delete = []
    for key, group in groups.items():
        if len(group) <= 1:
            continue
        # Ordenar: categoría específica primero, genérica al final
        def get_score(t):
            cat = (t.get('category_name') or '').lower().strip()
            return 0 if cat in GENERIC_CATS else 1
        sorted_group = sorted(group, key=get_score, reverse=True)
        keep = sorted_group[0]
        for t in sorted_group[1:]:
            if t.get('id') and t['id'] != keep['id']:
                ids_to_delete.append(t['id'])

    deleted = 0
    if not dry_run and ids_to_delete:
        result = await db.bank_transactions.delete_many(
            {'company_id': company_id, 'id': {'$in': ids_to_delete}}
        )
        deleted = result.deleted_count

    return {
        'dry_run': dry_run,
        'total_transacciones': len(txns),
        'grupos_duplicados': sum(1 for g in groups.values() if len(g) > 1),
        'ids_a_eliminar': len(ids_to_delete),
        'eliminados': deleted,
        'mensaje': 'Ejecuta con ?dry_run=false para eliminar' if dry_run else f'{deleted} duplicados eliminados',
    }
