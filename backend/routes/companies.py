"""Company routes — multi-empresa support"""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from typing import Dict, List, Optional
from datetime import datetime, timezone
import base64

from core.database import db
from core.auth import get_current_user, get_active_company_id
from models.company import Company, CompanyCreate, CompanyUpdate
from models.bank import BankAccount
from services.cashflow import initialize_cashflow_weeks

router = APIRouter(prefix="/companies")


@router.post("", response_model=Company)
async def create_company(
    company_data: CompanyCreate,
    current_user: Dict = Depends(get_current_user)
):
    """Create a new company and add it to the user's company_ids"""
    company = Company(**company_data.model_dump())
    doc = company.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['created_by'] = current_user['id']
    await db.companies.insert_one(doc)

    # ── Add new company to user's company_ids ─────────────────────────────
    user_company_ids = current_user.get('company_ids', [current_user['company_id']])
    if company.id not in user_company_ids:
        user_company_ids.append(company.id)
    await db.users.update_one(
        {'id': current_user['id']},
        {'$set': {'company_ids': user_company_ids}}
    )

    # Initialize 13 weeks of cashflow
    await initialize_cashflow_weeks(company.id)

    # Create default bank account
    default_account = BankAccount(
        company_id=company.id,
        nombre="Cuenta Principal",
        numero_cuenta="0000000000",
        banco="Sin banco",
        moneda="MXN",
        saldo_inicial=0.0,
        activo=True
    )
    account_doc = default_account.model_dump()
    account_doc['created_at'] = account_doc['created_at'].isoformat()
    await db.bank_accounts.insert_one(account_doc)

    return company


@router.get("", response_model=List[Company])
async def list_companies(current_user: Dict = Depends(get_current_user)):
    """List ALL companies the current user has access to"""
    user_id = current_user.get('id')
    primary_company_id = current_user.get('company_id')

    # Get all company_ids the user has access to
    company_ids = list(set(
        current_user.get('company_ids', []) +
        ([primary_company_id] if primary_company_id else [])
    ))

    # ALL users (including admin) only see their own companies
    companies = await db.companies.find(
        {'id': {'$in': company_ids}},
        {'_id': 0}
    ).to_list(1000)
    companies = [c for c in companies if c.get('activo', True) != False]

    # Deduplicate
    seen = set()
    result = []
    for c in companies:
        if c['id'] not in seen:
            seen.add(c['id'])
            if isinstance(c.get('created_at'), str):
                c['created_at'] = datetime.fromisoformat(c['created_at'])
            result.append(c)

    return result


@router.get("/{company_id}", response_model=Company)
async def get_company(company_id: str, current_user: Dict = Depends(get_current_user)):
    """Get a specific company — user must have access"""
    user_company_ids = list(set(
        current_user.get('company_ids', []) +
        [current_user.get('company_id', '')]
    ))

    if current_user.get('role') != 'admin' and company_id not in user_company_ids:
        raise HTTPException(status_code=403, detail="Sin acceso a esta empresa")

    company = await db.companies.find_one({'id': company_id, 'activo': True}, {'_id': 0})
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    if isinstance(company.get('created_at'), str):
        company['created_at'] = datetime.fromisoformat(company['created_at'])
    return Company(**company)


@router.put("/{company_id}")
async def update_company(
    company_id: str,
    data: CompanyUpdate,
    current_user: Dict = Depends(get_current_user)
):
    """Update a company — user must have access"""
    user_company_ids = list(set(
        current_user.get('company_ids', []) +
        [current_user.get('company_id', '')]
    ))

    if current_user.get('role') != 'admin' and company_id not in user_company_ids:
        raise HTTPException(status_code=403, detail="Sin acceso a esta empresa")

    company = await db.companies.find_one({'id': company_id, 'activo': True}, {'_id': 0})
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_data:
        await db.companies.update_one({'id': company_id}, {'$set': update_data})

    updated = await db.companies.find_one({'id': company_id}, {'_id': 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return updated


@router.post("/{company_id}/logo")
async def upload_company_logo(
    company_id: str,
    file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user)
):
    """Upload company logo"""
    user_company_ids = list(set(
        current_user.get('company_ids', []) +
        [current_user.get('company_id', '')]
    ))
    if current_user.get('role') != 'admin' and company_id not in user_company_ids:
        raise HTTPException(status_code=403, detail="Sin acceso a esta empresa")

    company = await db.companies.find_one({'id': company_id, 'activo': True}, {'_id': 0})
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")

    contents = await file.read()
    if len(contents) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="El archivo no debe exceder 2MB")

    base64_data = base64.b64encode(contents).decode('utf-8')
    logo_url = f"data:{file.content_type};base64,{base64_data}"
    await db.companies.update_one({'id': company_id}, {'$set': {'logo_url': logo_url}})
    return {"success": True, "logo_url": logo_url}


@router.delete("/{company_id}/logo")
async def delete_company_logo(
    company_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Delete company logo"""
    user_company_ids = list(set(
        current_user.get('company_ids', []) +
        [current_user.get('company_id', '')]
    ))
    if current_user.get('role') != 'admin' and company_id not in user_company_ids:
        raise HTTPException(status_code=403, detail="Sin acceso a esta empresa")

    await db.companies.update_one({'id': company_id}, {'$set': {'logo_url': None}})
    return {"success": True}


# ── NEW: Add existing company to user's access ─────────────────────────────────
@router.post("/{company_id}/add-access")
async def add_company_access(
    company_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Add a company to the current user's accessible companies (admin only for now)"""
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Solo admins pueden agregar acceso a empresas")

    company = await db.companies.find_one({'id': company_id, 'activo': True}, {'_id': 0, 'id': 1})
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    user_company_ids = current_user.get('company_ids', [current_user['company_id']])
    if company_id not in user_company_ids:
        user_company_ids.append(company_id)
        await db.users.update_one(
            {'id': current_user['id']},
            {'$set': {'company_ids': user_company_ids}}
        )

    return {"success": True, "company_ids": user_company_ids}
