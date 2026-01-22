"""Vendor routes"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, List
from datetime import datetime

from core.database import db
from core.auth import get_current_user, get_active_company_id
from models.vendor import Vendor, VendorCreate
from services.audit import audit_log

router = APIRouter(prefix="/vendors")


@router.post("", response_model=Vendor)
async def create_vendor(vendor_data: VendorCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    """Create a new vendor"""
    company_id = await get_active_company_id(request, current_user)
    vendor = Vendor(company_id=company_id, **vendor_data.model_dump())
    doc = vendor.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.vendors.insert_one(doc)
    await audit_log(vendor.company_id, 'Vendor', vendor.id, 'CREATE', current_user['id'])
    return vendor


@router.get("", response_model=List[Vendor])
async def list_vendors(request: Request, current_user: Dict = Depends(get_current_user)):
    """List all vendors for current company"""
    company_id = await get_active_company_id(request, current_user)
    vendors = await db.vendors.find({'company_id': company_id, 'activo': True}, {'_id': 0}).to_list(1000)
    for v in vendors:
        if isinstance(v.get('created_at'), str):
            v['created_at'] = datetime.fromisoformat(v['created_at'])
    return vendors


@router.put("/{vendor_id}")
async def update_vendor(vendor_id: str, vendor_data: VendorCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    """Update a vendor"""
    company_id = await get_active_company_id(request, current_user)
    existing = await db.vendors.find_one({'id': vendor_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    
    update_data = vendor_data.model_dump()
    await db.vendors.update_one(
        {'id': vendor_id, 'company_id': company_id},
        {'$set': update_data}
    )
    await audit_log(company_id, 'Vendor', vendor_id, 'UPDATE', current_user['id'], existing, update_data)
    
    updated = await db.vendors.find_one({'id': vendor_id}, {'_id': 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return updated


@router.delete("/{vendor_id}")
async def delete_vendor(vendor_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Delete (soft) a vendor"""
    company_id = await get_active_company_id(request, current_user)
    existing = await db.vendors.find_one({'id': vendor_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    
    await db.vendors.update_one(
        {'id': vendor_id},
        {'$set': {'activo': False}}
    )
    await audit_log(company_id, 'Vendor', vendor_id, 'DELETE', current_user['id'])
    return {'status': 'success', 'message': 'Proveedor eliminado'}
