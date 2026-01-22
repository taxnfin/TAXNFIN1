"""Customer routes"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, List
from datetime import datetime

from core.database import db
from core.auth import get_current_user, get_active_company_id
from models.customer import Customer, CustomerCreate
from services.audit import audit_log

router = APIRouter(prefix="/customers")


@router.post("", response_model=Customer)
async def create_customer(customer_data: CustomerCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    """Create a new customer"""
    company_id = await get_active_company_id(request, current_user)
    customer = Customer(company_id=company_id, **customer_data.model_dump())
    doc = customer.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.customers.insert_one(doc)
    await audit_log(customer.company_id, 'Customer', customer.id, 'CREATE', current_user['id'])
    return customer


@router.get("", response_model=List[Customer])
async def list_customers(request: Request, current_user: Dict = Depends(get_current_user)):
    """List all customers for current company"""
    company_id = await get_active_company_id(request, current_user)
    customers = await db.customers.find({'company_id': company_id, 'activo': True}, {'_id': 0}).to_list(1000)
    for c in customers:
        if isinstance(c.get('created_at'), str):
            c['created_at'] = datetime.fromisoformat(c['created_at'])
    return customers


@router.put("/{customer_id}")
async def update_customer(customer_id: str, customer_data: CustomerCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    """Update a customer"""
    company_id = await get_active_company_id(request, current_user)
    existing = await db.customers.find_one({'id': customer_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    update_data = customer_data.model_dump()
    await db.customers.update_one(
        {'id': customer_id, 'company_id': company_id},
        {'$set': update_data}
    )
    await audit_log(company_id, 'Customer', customer_id, 'UPDATE', current_user['id'], existing, update_data)
    
    updated = await db.customers.find_one({'id': customer_id}, {'_id': 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return updated


@router.delete("/{customer_id}")
async def delete_customer(customer_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Delete (soft) a customer"""
    company_id = await get_active_company_id(request, current_user)
    existing = await db.customers.find_one({'id': customer_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    await db.customers.update_one(
        {'id': customer_id},
        {'$set': {'activo': False}}
    )
    await audit_log(company_id, 'Customer', customer_id, 'DELETE', current_user['id'])
    return {'status': 'success', 'message': 'Cliente eliminado'}
