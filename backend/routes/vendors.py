"""Vendor routes"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, List
from datetime import datetime, timezone
import uuid, logging

from core.database import db
from core.auth import get_current_user, get_active_company_id
from models.vendor import Vendor, VendorCreate
from services.audit import audit_log

logger = logging.getLogger(__name__)

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


@router.post("/import-from-cfdis")
async def import_vendors_from_cfdis(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    Importa proveedores desde CFDIs de tipo 'egreso'.
    Fuente: emisor_nombre + emisor_rfc de db.cfdis.
    Upsert por RFC (si existe) o por nombre (sin RFC).
    """
    company_id = await get_active_company_id(request, current_user)
    now = datetime.now(timezone.utc)

    cfdis = await db.cfdis.find(
        {"company_id": company_id, "tipo_cfdi": "egreso"},
        {"emisor_nombre": 1, "emisor_rfc": 1, "_id": 0},
    ).to_list(5000)

    seen: set = set()
    importados = existentes = 0

    for cfdi in cfdis:
        nombre = (cfdi.get("emisor_nombre") or "").strip()
        rfc    = (cfdi.get("emisor_rfc") or "").strip().upper() or None
        if not nombre:
            continue
        key = rfc or nombre
        if key in seen:
            continue
        seen.add(key)

        query = {"company_id": company_id, "rfc": rfc} if rfc else {"company_id": company_id, "nombre": nombre}
        existing = await db.vendors.find_one(query, {"_id": 0})
        if existing:
            existentes += 1
            continue

        doc = {
            "id":         str(uuid.uuid4()),
            "company_id": company_id,
            "nombre":     nombre,
            "rfc":        rfc,
            "email":      None,
            "telefono":   None,
            "direccion":  None,
            "plazo_pago": None,
            "activo":     True,
            "created_at": now.isoformat(),
            "origen":     "cfdi_import",
        }
        await db.vendors.insert_one(doc)
        importados += 1

    logger.info(f"[IMPORT VENDORS] company={company_id} importados={importados} existentes={existentes}")
    return {"importados": importados, "existentes": existentes, "total": importados + existentes}


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
