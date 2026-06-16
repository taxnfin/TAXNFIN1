"""
Alegra Integration Module
Syncs customers, vendors, invoices, bills, and payments with Alegra accounting software
for cash flow management purposes.
"""
import os
import base64
import uuid
import httpx
from datetime import datetime, timezone, date
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, Query, BackgroundTasks
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from core.database import db
from core.auth import get_current_user, get_active_company_id

import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alegra", tags=["Alegra Integration"])

# Alegra API Configuration
ALEGRA_BASE_URL = "https://api.alegra.com/api/v1"


class AlegraCredentials(BaseModel):
    email: str
    token: str


class SyncStatus(BaseModel):
    entity: str
    synced: int
    created: int
    updated: int
    errors: int


def get_alegra_headers(email: str, token: str) -> Dict[str, str]:
    """Generate Alegra API headers with Basic Auth"""
    credentials = f"{email}:{token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


async def alegra_request(method: str, endpoint: str, email: str, token: str, params: dict = None, json_data: dict = None) -> dict:
    """Make a request to Alegra API with retries"""
    headers = get_alegra_headers(email, token)
    url = f"{ALEGRA_BASE_URL}/{endpoint}"
    max_retries = 3
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for attempt in range(max_retries):
            try:
                if method == "GET":
                    response = await client.get(url, headers=headers, params=params)
                elif method == "POST":
                    response = await client.post(url, headers=headers, json=json_data)
                elif method == "PUT":
                    response = await client.put(url, headers=headers, json=json_data)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                error_text = e.response.text
                status_code = e.response.status_code
                
                # If it's a 429 (rate limit), wait and retry
                if status_code == 429 and attempt < max_retries - 1:
                    import asyncio
                    wait_time = 5 * (attempt + 1)
                    logger.warning(f"Alegra API rate limit (429), waiting {wait_time}s ({attempt + 1}/{max_retries})...")
                    await asyncio.sleep(wait_time)
                    continue
                # If it's a 500 error from Alegra, retry
                if status_code == 500 and attempt < max_retries - 1:
                    logger.warning(f"Alegra API error 500, retrying ({attempt + 1}/{max_retries})...")
                    import asyncio
                    await asyncio.sleep(2 * (attempt + 1))  # Exponential backoff
                    continue
                
                # Parse error message for better display
                try:
                    error_json = e.response.json()
                    error_msg = error_json.get('message', error_text)
                except:
                    error_msg = error_text
                
                logger.error(f"Alegra API error: {status_code} - {error_msg}")
                
                # Return None instead of raising for 500 errors (temporary server issues)
                if status_code == 500:
                    return None
                    
                raise HTTPException(status_code=status_code, detail=f"Error de Alegra: {error_msg}")
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    logger.warning(f"Alegra API timeout, retrying ({attempt + 1}/{max_retries})...")
                    continue
                logger.error(f"Alegra API timeout after {max_retries} attempts")
                return None
            except Exception as e:
                logger.error(f"Alegra request failed: {str(e)}")
                if attempt < max_retries - 1:
                    continue
                return None
    
    return None


async def save_alegra_exchange_rate(company_id: str, moneda: str, tipo_cambio: float, fecha: str):
    """Save exchange rate from Alegra to fx_rates collection"""
    try:
        # Parse date
        if fecha:
            fecha_vigencia = datetime.fromisoformat(fecha.replace('Z', '+00:00')) if 'T' in fecha else datetime.strptime(fecha, '%Y-%m-%d')
        else:
            fecha_vigencia = datetime.now(timezone.utc)
        
        # Check if we already have this rate for this date
        existing = await db.fx_rates.find_one({
            'company_id': company_id,
            'moneda_cotizada': moneda,
            'fecha_vigencia': {'$gte': fecha_vigencia.replace(hour=0, minute=0, second=0), '$lt': fecha_vigencia.replace(hour=23, minute=59, second=59)}
        })
        
        if existing:
            # Update if rate changed
            if existing.get('tipo_cambio') != tipo_cambio:
                await db.fx_rates.update_one(
                    {'_id': existing['_id']},
                    {'$set': {'tipo_cambio': tipo_cambio, 'fuente': 'alegra', 'updated_at': datetime.now(timezone.utc).isoformat()}}
                )
        else:
            # Insert new rate
            rate_doc = {
                'id': str(uuid.uuid4()),
                'company_id': company_id,
                'moneda_base': 'MXN',
                'moneda_cotizada': moneda,
                'tipo_cambio': tipo_cambio,
                'fecha_vigencia': fecha_vigencia.isoformat(),
                'fuente': 'alegra',
                'source': 'alegra',
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            await db.fx_rates.insert_one(rate_doc)
            logger.info(f"Saved exchange rate from Alegra: {moneda} = {tipo_cambio} MXN for {fecha}")
    except Exception as e:
        logger.error(f"Error saving exchange rate: {str(e)}")


@router.post("/test-connection")
async def test_alegra_connection(
    credentials: AlegraCredentials,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Test connection to Alegra API"""
    try:
        # Try to get user info or contacts to verify connection
        result = await alegra_request("GET", "contacts", credentials.email, credentials.token, params={"limit": 1})
        return {
            "success": True,
            "message": "Conexión exitosa con Alegra",
            "sample_data": result[:1] if isinstance(result, list) else result
        }
    except HTTPException as e:
        return {
            "success": False,
            "message": f"Error de conexión: {e.detail}"
        }


@router.post("/save-credentials")
async def save_alegra_credentials(
    credentials: AlegraCredentials,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Save Alegra credentials for the company"""
    company_id = await get_active_company_id(request, current_user)
    
    # Test connection first
    try:
        await alegra_request("GET", "contacts", credentials.email, credentials.token, params={"limit": 1})
    except:
        raise HTTPException(status_code=400, detail="Credenciales de Alegra inválidas")
    
    # Save credentials (encrypted in production)
    await db.companies.update_one(
        {'id': company_id},
        {'$set': {
            'alegra_email': credentials.email,
            'alegra_token': credentials.token,
            'alegra_connected': True,
            'alegra_connected_at': datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"success": True, "message": "Credenciales de Alegra guardadas exitosamente"}


@router.get("/status")
async def get_alegra_status(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Get Alegra connection status for the company"""
    company_id = await get_active_company_id(request, current_user)
    company = await db.companies.find_one({'id': company_id}, {'_id': 0})
    
    return {
        "connected": company.get('alegra_connected', False),
        "email": company.get('alegra_email'),
        "connected_at": company.get('alegra_connected_at'),
        "last_sync": company.get('alegra_last_sync')
    }


@router.post("/sync/contacts")
async def sync_alegra_contacts(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    contact_type: str = Query("all", description="Type: all, client, provider")
):
    """
    Sync contacts (customers and vendors) from Alegra
    """
    company_id = await get_active_company_id(request, current_user)
    company = await db.companies.find_one({'id': company_id}, {'_id': 0})
    
    if not company.get('alegra_connected'):
        raise HTTPException(status_code=400, detail="Alegra no está conectado")
    
    email = company.get('alegra_email')
    token = company.get('alegra_token')
    
    # Fetch all contacts from Alegra with pagination
    all_contacts = []
    start = 0
    limit = 30  # Alegra API max limit is 30
    
    while True:
        params = {"start": start, "limit": limit, "order_direction": "ASC", "order_field": "id"}
        if contact_type != "all":
            params["type"] = contact_type
        
        contacts = await alegra_request("GET", "contacts", email, token, params=params)
        
        if not contacts or len(contacts) == 0:
            break
        
        all_contacts.extend(contacts)
        
        if len(contacts) < limit:
            break
        
        start += limit
    
    # Process and save contacts
    created = 0
    updated = 0
    errors = 0
    
    for contact in all_contacts:
        try:
            alegra_id = str(contact.get('id'))
            contact_types = contact.get('type', [])
            
            # Determine if client, vendor, or both
            is_client = 'client' in contact_types
            is_vendor = 'provider' in contact_types
            
            # Build name
            name_obj = contact.get('name', {})
            if isinstance(name_obj, dict):
                full_name = name_obj.get('fullName') or f"{name_obj.get('firstName', '')} {name_obj.get('lastName', '')}".strip()
            else:
                full_name = str(name_obj)
            
            # Extract address
            address_obj = contact.get('address', {})
            address_str = ""
            if isinstance(address_obj, dict):
                address_parts = [
                    address_obj.get('address', ''),
                    address_obj.get('city', ''),
                    address_obj.get('department', ''),
                    address_obj.get('country', '')
                ]
                address_str = ", ".join(filter(None, address_parts))
            
            contact_doc = {
                'alegra_id': alegra_id,
                'company_id': company_id,
                'nombre': full_name,
                'email': contact.get('email', ''),
                'telefono': contact.get('phonePrimary', ''),
                'telefono_secundario': contact.get('phoneSecondary', ''),
                'celular': contact.get('mobile', ''),
                'rfc': contact.get('identification', ''),
                'direccion': address_str,
                'is_client': is_client,
                'is_vendor': is_vendor,
                'activo': True,
                'source': 'alegra',
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Sync to customers collection if client
            if is_client:
                existing = await db.customers.find_one({'company_id': company_id, 'alegra_id': alegra_id})
                if existing:
                    await db.customers.update_one({'_id': existing['_id']}, {'$set': contact_doc})
                    updated += 1
                else:
                    contact_doc['id'] = str(uuid.uuid4())
                    contact_doc['created_at'] = datetime.now(timezone.utc).isoformat()
                    await db.customers.insert_one(contact_doc)
                    created += 1
            
            # Sync to vendors collection if vendor
            if is_vendor:
                existing = await db.vendors.find_one({'company_id': company_id, 'alegra_id': alegra_id})
                if existing:
                    await db.vendors.update_one({'_id': existing['_id']}, {'$set': contact_doc})
                    if not is_client:  # Don't double count
                        updated += 1
                else:
                    vendor_doc = contact_doc.copy()
                    vendor_doc['id'] = str(uuid.uuid4())
                    vendor_doc['created_at'] = datetime.now(timezone.utc).isoformat()
                    await db.vendors.insert_one(vendor_doc)
                    if not is_client:
                        created += 1
                        
        except Exception as e:
            logger.error(f"Error syncing contact {contact.get('id')}: {str(e)}")
            errors += 1
    
    return {
        "success": True,
        "message": f"Contactos sincronizados desde Alegra",
        "stats": {
            "total": len(all_contacts),
            "created": created,
            "updated": updated,
            "errors": errors
        }
    }


@router.post("/sync/invoices")
async def sync_alegra_invoices(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    status: str = Query("all", description="Status: all, open, closed, void"),
    date_from: str = Query(None, description="Date from (YYYY-MM-DD) - filters by payment date or due date"),
    date_to: str = Query(None, description="Date to (YYYY-MM-DD) - filters by payment date or due date")
):
    """
    Sync invoices (sales/receivables) from Alegra
    These are Cuentas por Cobrar (CxC)
    
    Date filter logic:
    - For PAID invoices: filters by payment date
    - For PENDING invoices: filters by due date
    """
    company_id = await get_active_company_id(request, current_user)
    company = await db.companies.find_one({'id': company_id}, {'_id': 0})
    
    if not company.get('alegra_connected'):
        raise HTTPException(status_code=400, detail="Alegra no está conectado")
    
    email = company.get('alegra_email')
    token = company.get('alegra_token')
    
    # Fetch all invoices from Alegra (we'll filter locally for more control)
    all_invoices = []
    start = 0
    limit = 30  # Alegra API max limit is 30
    
    while True:
        params = {"start": start, "limit": limit, "order_direction": "DESC", "order_field": "id"}
        if status != "all":
            params["status"] = status
        
        invoices = await alegra_request("GET", "invoices", email, token, params=params)
        
        if not invoices or len(invoices) == 0:
            break
        
        all_invoices.extend(invoices)
        
        if len(invoices) < limit:
            break
        
        start += limit
    
    # Process and save invoices as CFDIs (facturas de venta = ingreso)
    created = 0
    updated = 0
    skipped = 0
    duplicates = 0
    errors = 0
    
    for invoice in all_invoices:
        try:
            alegra_id = str(invoice.get('id'))
            
            # Get client info
            client = invoice.get('client', {})
            client_name = ""
            client_rfc = ""
            if isinstance(client, dict):
                name_obj = client.get('name', {})
                if isinstance(name_obj, dict):
                    client_name = name_obj.get('fullName') or f"{name_obj.get('firstName', '')} {name_obj.get('lastName', '')}".strip()
                else:
                    client_name = str(name_obj) if name_obj else ''
                client_rfc = client.get('identification', '')
            
            # Calculate balance
            total = float(invoice.get('total', 0) or 0)
            total_paid = float(invoice.get('totalPaid', 0) or 0)
            balance = float(invoice.get('balance', total - total_paid) or 0)
            
            # Determine status
            inv_status = invoice.get('status', 'open')
            if balance <= 0:
                estado_conciliacion = 'conciliado'
            elif total_paid > 0:
                estado_conciliacion = 'parcial'
            else:
                estado_conciliacion = 'pendiente'
            
            # Parse dates
            fecha = invoice.get('date', '')
            fecha_vencimiento = invoice.get('dueDate', fecha)
            
            # Get payment date from payments array if available
            fecha_pago = None
            payments_list = invoice.get('payments', [])
            if payments_list and isinstance(payments_list, list):
                # Get the most recent payment date
                for pmt in payments_list:
                    if isinstance(pmt, dict) and pmt.get('date'):
                        pmt_date = pmt.get('date')
                        if not fecha_pago or pmt_date > fecha_pago:
                            fecha_pago = pmt_date
            
            # Apply date filter logic: filter by INVOICE EMISSION DATE (fecha)
            # so the user gets exactly what they asked for ("invoices issued in
            # January 2026" must NOT include November-issued invoices that
            # happen to mature in January).
            if date_from or date_to:
                fecha_check = (fecha or '')[:10]
                should_include = True
                if date_from and fecha_check and fecha_check < date_from:
                    should_include = False
                if date_to and fecha_check and fecha_check > date_to:
                    should_include = False
                if not fecha_check:
                    should_include = False
                
                if not should_include:
                    skipped += 1
                    continue
            
            # Extract currency and exchange rate
            currency_data = invoice.get('currency', {})
            moneda = currency_data.get('code', 'MXN') if isinstance(currency_data, dict) else 'MXN'
            tipo_cambio = float(currency_data.get('exchangeRate', 1) or 1) if isinstance(currency_data, dict) else 1
            
            # Save exchange rate to fx_rates if not MXN and rate is not 1
            if moneda != 'MXN' and tipo_cambio and tipo_cambio != 1:
                await save_alegra_exchange_rate(company_id, moneda, tipo_cambio, fecha)
            
            # Get invoice folio - prefix + number (e.g., CUSTINVC859)
            number_template = invoice.get('numberTemplate', {})
            prefix = number_template.get('prefix', '') if isinstance(number_template, dict) else ''
            number = str(invoice.get('number', alegra_id))
            folio_alegra = f"{prefix}{number}"  # Full folio like CUSTINVC859
            
            # Get the REAL UUID from SAT stamp if available
            stamp = invoice.get('stamp', {})
            sat_uuid = stamp.get('uuid') if isinstance(stamp, dict) else None
            
            # Use the real SAT UUID if available, otherwise use a pseudo-UUID
            if sat_uuid:
                uuid_value = sat_uuid
                logger.info(f"Invoice {alegra_id} has real SAT UUID: {sat_uuid}")
            else:
                uuid_value = f"ALEGRA-INV-{alegra_id}"
                logger.info(f"Invoice {alegra_id} has no SAT stamp, using pseudo-UUID")
            
            # Also get the stamp date as the timbrado date
            fecha_timbrado = stamp.get('stampDate') or stamp.get('datetime') or fecha if isinstance(stamp, dict) else fecha
            
            # Calculate totals.
            # IMPORTANT: We store `total` in the ORIGINAL CURRENCY (USD/EUR/MXN)
            # to match the convention used by the SAT/CFDI module and prevent
            # the /cfdi/summary endpoint from double-converting (which used to
            # produce 17x-inflated totals when foreign currencies were stored
            # already-converted to MXN).
            total_moneda_original = total  # always in original currency
            
            if moneda != 'MXN' and tipo_cambio > 0:
                total_mxn = total * tipo_cambio  # Reference value in MXN
                total_paid_mxn = total_paid * tipo_cambio
            else:
                total_mxn = total
                total_paid_mxn = total_paid
            
            # Calculate taxes from the original-currency subtotal so the values
            # are consistent with `total` (also in original currency).
            subtotal = total / 1.16 if total > 0 else 0  # Assuming 16% IVA
            impuestos = total - subtotal
            
            # Determine payment method based on payment status
            # PPD = Pago en Parcialidades o Diferido (pendiente)
            # PUE = Pago en Una sola Exhibición (pagado completamente)
            if estado_conciliacion == 'conciliado':
                metodo_pago = 'PUE'
            else:
                metodo_pago = 'PPD'
            
            cfdi_doc = {
                'alegra_id': alegra_id,
                'company_id': company_id,
                'uuid': uuid_value,  # Real SAT UUID or pseudo-UUID
                'tipo_cfdi': 'ingreso',  # Sales invoice = ingreso
                'emisor_rfc': company.get('rfc', 'XAXX010101000'),
                'emisor_nombre': company.get('razon_social', company.get('nombre', '')),
                'receptor_rfc': client_rfc or 'XAXX010101000',
                'receptor_nombre': client_name,
                'fecha_emision': fecha + 'T00:00:00' if fecha and 'T' not in fecha else fecha,
                'fecha_timbrado': fecha_timbrado if fecha_timbrado else (fecha + 'T00:00:00' if fecha and 'T' not in fecha else fecha),
                'fecha_vencimiento': fecha_vencimiento,
                'moneda': moneda,
                'tipo_cambio': tipo_cambio if moneda != 'MXN' else 1,
                'subtotal': round(subtotal, 2),
                'descuento': 0,
                'impuestos': round(impuestos, 2),
                'total': round(total, 2),  # Total in ORIGINAL currency (USD/EUR/MXN)
                'total_mxn': round(total_mxn, 2),  # Reference: pre-converted to MXN
                'total_moneda_original': round(total_moneda_original, 2),
                'iva_trasladado': round(impuestos, 2),
                'isr_retenido': 0,
                'iva_retenido': 0,
                'metodo_pago': metodo_pago,
                'estatus': 'vigente',
                'estado_conciliacion': estado_conciliacion,
                'monto_cobrado': round(total_paid, 2),  # In original currency
                'monto_cobrado_mxn': round(total_paid_mxn, 2),  # Reference in MXN
                'monto_pagado': 0,
                'referencia': folio_alegra,  # Full folio CUSTINVC859
                'folio_alegra': folio_alegra,
                'source': 'alegra',
                'alegra_status': inv_status,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Check if exists by alegra_id OR by UUID (real or pseudo) to prevent duplicates
            existing = await db.cfdis.find_one({
                'company_id': company_id,
                '$or': [
                    {'alegra_id': alegra_id},
                    {'uuid': uuid_value}
                ]
            })
            
            if existing:
                # Update existing CFDI
                await db.cfdis.update_one({'_id': existing['_id']}, {'$set': cfdi_doc})
                updated += 1
            else:
                cfdi_doc['id'] = str(uuid.uuid4())
                cfdi_doc['created_at'] = datetime.now(timezone.utc).isoformat()
                await db.cfdis.insert_one(cfdi_doc)
                created += 1
                
        except Exception as e:
            logger.error(f"Error syncing invoice {invoice.get('id')}: {str(e)}")
            errors += 1
    
    return {
        "success": True,
        "message": f"Facturas de venta (CxC) sincronizadas al módulo CFDI/SAT",
        "stats": {
            "total": len(all_invoices),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "duplicates": duplicates,
            "errors": errors
        }
    }


@router.post("/sync/bills")
async def sync_alegra_bills(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    status: str = Query("all", description="Status: all, open, closed, void"),
    date_from: str = Query(None, description="Date from (YYYY-MM-DD) - filters by payment date or due date"),
    date_to: str = Query(None, description="Date to (YYYY-MM-DD) - filters by payment date or due date")
):
    """
    Sync bills (purchases/payables) from Alegra
    These are Cuentas por Pagar (CxP)
    
    Date filter logic:
    - For PAID bills: filters by payment date
    - For PENDING bills: filters by due date
    """
    company_id = await get_active_company_id(request, current_user)
    company = await db.companies.find_one({'id': company_id}, {'_id': 0})
    
    if not company.get('alegra_connected'):
        raise HTTPException(status_code=400, detail="Alegra no está conectado")
    
    email = company.get('alegra_email')
    token = company.get('alegra_token')
    
    # Fetch all bills from Alegra (we'll filter locally for more control)
    all_bills = []
    start = 0
    limit = 30  # Alegra API max limit is 30
    
    while True:
        params = {"start": start, "limit": limit, "order_direction": "DESC", "order_field": "id"}
        if status != "all":
            params["status"] = status
        
        # bills endpoint
        bills = await alegra_request("GET", "bills", email, token, params=params)
        
        if not bills or len(bills) == 0:
            break
        
        all_bills.extend(bills)
        
        if len(bills) < limit:
            break
        
        start += limit
    
    # Process and save bills as CFDIs (facturas de proveedor = egreso)
    created = 0
    updated = 0
    skipped = 0
    duplicates = 0
    errors = 0
    
    for bill in all_bills:
        try:
            alegra_id = str(bill.get('id'))
            
            # Get vendor info
            vendor = bill.get('provider', {})
            vendor_name = ""
            vendor_rfc = ""
            if isinstance(vendor, dict):
                name_obj = vendor.get('name', {})
                if isinstance(name_obj, dict):
                    vendor_name = name_obj.get('fullName') or f"{name_obj.get('firstName', '')} {name_obj.get('lastName', '')}".strip()
                else:
                    vendor_name = str(name_obj) if name_obj else ''
                vendor_rfc = vendor.get('identification', '')
            
            # Calculate balance
            total = float(bill.get('total', 0) or 0)
            total_paid = float(bill.get('totalPaid', 0) or 0)
            balance = float(bill.get('balance', total - total_paid) or 0)
            
            # Determine status
            bill_status = bill.get('status', 'open')
            if balance <= 0:
                estado_conciliacion = 'conciliado'
            elif total_paid > 0:
                estado_conciliacion = 'parcial'
            else:
                estado_conciliacion = 'pendiente'
            
            # Parse dates
            fecha = bill.get('date', '')
            fecha_vencimiento = bill.get('dueDate', fecha)
            
            # Get payment date from payments array if available
            fecha_pago = None
            payments_list = bill.get('payments', [])
            if payments_list and isinstance(payments_list, list):
                # Get the most recent payment date
                for pmt in payments_list:
                    if isinstance(pmt, dict) and pmt.get('date'):
                        pmt_date = pmt.get('date')
                        if not fecha_pago or pmt_date > fecha_pago:
                            fecha_pago = pmt_date
            
            # Apply date filter logic: filter by BILL EMISSION DATE (fecha)
            # so the user gets exactly what they asked for.
            if date_from or date_to:
                fecha_check = (fecha or '')[:10]
                should_include = True
                if date_from and fecha_check and fecha_check < date_from:
                    should_include = False
                if date_to and fecha_check and fecha_check > date_to:
                    should_include = False
                if not fecha_check:
                    should_include = False
                
                if not should_include:
                    skipped += 1
                    continue
            
            # Extract currency and exchange rate
            currency_data = bill.get('currency', {})
            moneda = currency_data.get('code', 'MXN') if isinstance(currency_data, dict) else 'MXN'
            tipo_cambio = float(currency_data.get('exchangeRate', 1) or 1) if isinstance(currency_data, dict) else 1
            
            # Save exchange rate to fx_rates if not MXN and rate is not 1
            if moneda != 'MXN' and tipo_cambio and tipo_cambio != 1:
                await save_alegra_exchange_rate(company_id, moneda, tipo_cambio, fecha)
            
            # Get bill folio - prefix + number (e.g., BILL123)
            number_template = bill.get('numberTemplate', {})
            prefix = number_template.get('prefix', '') if isinstance(number_template, dict) else ''
            number = str(bill.get('number', alegra_id))
            folio_alegra = f"{prefix}{number}"  # Full folio
            
            # Get the REAL UUID from SAT stamp if available
            stamp = bill.get('stamp', {})
            sat_uuid = stamp.get('uuid') if isinstance(stamp, dict) else None
            
            # Use the real SAT UUID if available, otherwise use a pseudo-UUID
            if sat_uuid:
                uuid_value = sat_uuid
                logger.info(f"Bill {alegra_id} has real SAT UUID: {sat_uuid}")
            else:
                uuid_value = f"ALEGRA-BILL-{alegra_id}"
                logger.info(f"Bill {alegra_id} has no SAT stamp, using pseudo-UUID")
            
            # Also get the stamp date as the timbrado date
            fecha_timbrado = stamp.get('stampDate') or stamp.get('datetime') or fecha if isinstance(stamp, dict) else fecha
            
            # Calculate totals.
            # IMPORTANT: We store `total` in the ORIGINAL CURRENCY to match the
            # SAT/CFDI module convention and prevent the /cfdi/summary endpoint
            # from double-converting (which produced 17x-inflated totals).
            total_moneda_original = total
            
            if moneda != 'MXN' and tipo_cambio > 0:
                total_mxn = total * tipo_cambio
                total_paid_mxn = total_paid * tipo_cambio
            else:
                total_mxn = total
                total_paid_mxn = total_paid
            
            # Calculate taxes from the original-currency total so values stay consistent
            subtotal = total / 1.16 if total > 0 else 0
            impuestos = total - subtotal
            
            # Determine payment method
            if estado_conciliacion == 'conciliado':
                metodo_pago = 'PUE'
            else:
                metodo_pago = 'PPD'
            
            cfdi_doc = {
                'alegra_id': alegra_id,
                'company_id': company_id,
                'uuid': uuid_value,  # Real SAT UUID or pseudo-UUID
                'tipo_cfdi': 'egreso',  # Purchase bill = egreso
                'emisor_rfc': vendor_rfc or 'XAXX010101000',
                'emisor_nombre': vendor_name,
                'receptor_rfc': company.get('rfc', 'XAXX010101000'),
                'receptor_nombre': company.get('razon_social', company.get('nombre', '')),
                'fecha_emision': fecha + 'T00:00:00' if fecha and 'T' not in fecha else fecha,
                'fecha_timbrado': fecha_timbrado if fecha_timbrado else (fecha + 'T00:00:00' if fecha and 'T' not in fecha else fecha),
                'fecha_vencimiento': fecha_vencimiento,
                'moneda': moneda,
                'tipo_cambio': tipo_cambio if moneda != 'MXN' else 1,
                'subtotal': round(subtotal, 2),
                'descuento': 0,
                'impuestos': round(impuestos, 2),
                'total': round(total, 2),  # Total in ORIGINAL currency
                'total_mxn': round(total_mxn, 2),  # Reference: pre-converted to MXN
                'total_moneda_original': round(total_moneda_original, 2),
                'iva_trasladado': round(impuestos, 2),
                'isr_retenido': 0,
                'iva_retenido': 0,
                'metodo_pago': metodo_pago,
                'estatus': 'vigente',
                'estado_conciliacion': estado_conciliacion,
                'monto_cobrado': 0,
                'monto_pagado': round(total_paid, 2),  # In original currency
                'monto_pagado_mxn': round(total_paid_mxn, 2),  # Reference in MXN
                'referencia': folio_alegra,
                'folio_alegra': folio_alegra,
                'source': 'alegra',
                'alegra_status': bill_status,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Check if exists by alegra_id OR by UUID (real or pseudo) to prevent duplicates
            existing = await db.cfdis.find_one({
                'company_id': company_id,
                '$or': [
                    {'alegra_id': alegra_id},
                    {'uuid': uuid_value}
                ]
            })
            
            if existing:
                # Update existing CFDI
                await db.cfdis.update_one({'_id': existing['_id']}, {'$set': cfdi_doc})
                updated += 1
            else:
                cfdi_doc['id'] = str(uuid.uuid4())
                cfdi_doc['created_at'] = datetime.now(timezone.utc).isoformat()
                await db.cfdis.insert_one(cfdi_doc)
                created += 1
                
        except Exception as e:
            logger.error(f"Error syncing bill {bill.get('id')}: {str(e)}")
            errors += 1
    
    return {
        "success": True,
        "message": f"Facturas de proveedor (CxP) sincronizadas al módulo CFDI/SAT",
        "stats": {
            "total": len(all_bills),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "duplicates": duplicates,
            "errors": errors
        }
    }


@router.post("/sync/payments")
async def sync_alegra_payments(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    date_from: str = Query(None, description="Date from (YYYY-MM-DD)"),
    date_to: str = Query(None, description="Date to (YYYY-MM-DD)")
):
    """
    Sync payments from Alegra using GET /payments endpoint.
    Each record has type ('in'=cobro, 'out'=pago), amount, date, bankAccount, client.
    """
    company_id = await get_active_company_id(request, current_user)
    company = await db.companies.find_one({'id': company_id}, {'_id': 0})

    if not company.get('alegra_connected'):
        raise HTTPException(status_code=400, detail="Alegra no está conectado")

    # Mutual exclusion: companies with active Contalink must not sync Alegra payments
    contalink_active = await db.integrations.find_one({
        'company_id': company_id,
        'type': 'contalink',
        'active': True,
    }, {'_id': 1})
    if contalink_active:
        raise HTTPException(
            status_code=400,
            detail="Esta empresa usa Contalink. Alegra sync no aplica."
        )

    email = company.get('alegra_email')
    token = company.get('alegra_token')

    # Paginate through GET /payments
    all_payments = []
    start = 0
    limit = 30  # Alegra API max page size

    while True:
        params = {
            "start":  start,
            "limit":  limit,
            "order":  "date",
            "fields": "id,date,amount,type,status,bankAccount,client,observations,anotation,categories",
        }
        if date_from:
            params["date-start"] = date_from
        if date_to:
            params["date-end"] = date_to

        batch = await alegra_request("GET", "payments", email, token, params=params)
        if not batch or not isinstance(batch, list):
            break

        all_payments.extend(batch)

        if len(batch) < limit:
            break
        start += limit

    logger.info(f"Alegra /payments fetched {len(all_payments)} records for company {company_id}")

    created = 0
    updated = 0
    skipped = 0
    errors  = 0

    for payment in all_payments:
        try:
            alegra_id  = str(payment.get('id'))
            pago_type  = (payment.get('type') or '').lower()
            pago_status = (payment.get('status') or '').lower()

            # Excluir pagos anulados
            if pago_status == 'void':
                skipped += 1
                continue

            # Mapear type: "in" → cobro, "out" → pago
            tipo = 'cobro' if pago_type == 'in' else 'pago'

            amount   = float(payment.get('amount', 0) or 0)
            fecha_mov = payment.get('date') or datetime.now(timezone.utc).strftime('%Y-%m-%d')

            # Concepto: nombre del cliente o primera categoría
            client_obj = payment.get('client') or {}
            client_name = (client_obj.get('name') or '') if isinstance(client_obj, dict) else ''
            categories  = payment.get('categories') or []
            cat_name    = (categories[0].get('name', '') if categories and isinstance(categories[0], dict) else '')
            concepto    = (client_name or cat_name or
                           payment.get('observations') or payment.get('anotation') or
                           f"Pago Alegra {alegra_id}")

            # Cuenta bancaria
            bank_obj  = payment.get('bankAccount') or {}
            bank_name = (bank_obj.get('name') or '') if isinstance(bank_obj, dict) else ''

            payment_doc = {
                'alegra_id':          alegra_id,
                'alegra_type':        'payment',
                'company_id':         company_id,
                'tipo':               tipo,
                'concepto':           concepto,
                'monto':              abs(amount),
                'moneda':             'MXN',
                'metodo_pago':        'transferencia',
                'fecha_vencimiento':  fecha_mov,
                'fecha_pago':         fecha_mov,
                'estatus':            'completado',
                'referencia':         str(alegra_id),
                'beneficiario':       client_name,
                'es_real':            True,
                'source':             'alegra',
                'alegra_bank_account': bank_name,
                'updated_at':         datetime.now(timezone.utc).isoformat(),
            }

            existing = await db.payments.find_one(
                {'company_id': company_id, 'alegra_id': alegra_id, 'alegra_type': 'payment'},
                {'_id': 1}
            )
            if existing:
                await db.payments.update_one({'_id': existing['_id']}, {'$set': payment_doc})
                updated += 1
            else:
                payment_doc['id']         = str(uuid.uuid4())
                payment_doc['created_at'] = datetime.now(timezone.utc).isoformat()
                await db.payments.insert_one(payment_doc)
                created += 1

        except Exception as e:
            logger.error(f"Error syncing Alegra payment {payment.get('id')}: {e}")
            errors += 1

    return {
        "success": True,
        "message": f"Pagos sincronizados desde Alegra (/payments)",
        "stats": {
            "total":   len(all_payments),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors":  errors,
        },
    }


async def _run_alegra_sync(company_id: str, company: dict, date_from: str = None, date_to: str = None):
    """Background task: sincroniza invoices, bills y payments desde Alegra."""
    logger.info(f"[Alegra] Iniciando sync background para company {company_id}")
    email = company.get('alegra_email')
    token = company.get('alegra_token')
    results = {}

    # Sync invoices (CxC)
    try:
        all_invoices, start = [], 0
        while True:
            params = {'start': start, 'limit': 30, 'status': 'open',
                      'order_field': 'date', 'order_direction': 'DESC'}
            if date_from: params['date[from]'] = date_from
            if date_to:   params['date[to]']   = date_to
            batch = await alegra_request('GET', 'invoices', email, token, params=params)
            if not batch or not isinstance(batch, list): break
            all_invoices.extend(batch)
            if len(batch) < 30: break
            start += 30
        created = updated = 0
        for inv in all_invoices:
            alegra_id = str(inv.get('id'))
            doc = {**inv, 'company_id': company_id, 'alegra_id': alegra_id,
                   'source': 'alegra', 'tipo_cfdi': 'ingreso',
                   'synced_at': datetime.now(timezone.utc).isoformat()}
            res = await db.cfdis.update_one(
                {'company_id': company_id, 'alegra_id': alegra_id},
                {'$set': doc}, upsert=True)
            if res.upserted_id: created += 1
            else: updated += 1
        results['invoices'] = {'total': len(all_invoices), 'created': created, 'updated': updated}
    except Exception as e:
        results['invoices'] = {'error': str(e)}
        logger.error(f"[Alegra] Error sync invoices: {e}")

    # Sync bills (CxP)
    try:
        all_bills, start = [], 0
        while True:
            params = {'start': start, 'limit': 30, 'status': 'open',
                      'order_field': 'date', 'order_direction': 'DESC'}
            if date_from: params['date[from]'] = date_from
            if date_to:   params['date[to]']   = date_to
            batch = await alegra_request('GET', 'bills', email, token, params=params)
            if not batch or not isinstance(batch, list): break
            all_bills.extend(batch)
            if len(batch) < 30: break
            start += 30
        created = updated = 0
        for bill in all_bills:
            alegra_id = str(bill.get('id'))
            doc = {**bill, 'company_id': company_id, 'alegra_id': alegra_id,
                   'source': 'alegra', 'tipo_cfdi': 'egreso',
                   'synced_at': datetime.now(timezone.utc).isoformat()}
            res = await db.cfdis.update_one(
                {'company_id': company_id, 'alegra_id': alegra_id},
                {'$set': doc}, upsert=True)
            if res.upserted_id: created += 1
            else: updated += 1
        results['bills'] = {'total': len(all_bills), 'created': created, 'updated': updated}
    except Exception as e:
        results['bills'] = {'error': str(e)}
        logger.error(f"[Alegra] Error sync bills: {e}")

    # Sync payments → db.payments con formato compatible con Cobranza y Pagos
    try:
        all_payments, start = [], 0
        while True:
            params = {'start': start, 'limit': 30, 'order_field': 'date', 'order_direction': 'DESC'}
            if date_from: params['date[from]'] = date_from
            if date_to:   params['date[to]']   = date_to
            batch = await alegra_request('GET', 'payments', email, token, params=params)
            if not batch or not isinstance(batch, list): break
            all_payments.extend(batch)
            if len(batch) < 30: break
            start += 30
        created = updated = 0
        for pay in all_payments:
            alegra_id = str(pay.get('id'))
            # Determinar tipo: cobro (entrante) o pago (saliente)
            pay_type = pay.get('type', '')
            tipo = 'cobro' if pay_type in ('in', 'income', 'cobro') else 'pago'
            client_obj = pay.get('client') or pay.get('vendor') or {}
            beneficiario = client_obj.get('name', '') if isinstance(client_obj, dict) else ''
            banco_obj = pay.get('bankAccount') or {}
            cuenta_banco = banco_obj.get('name', '') if isinstance(banco_obj, dict) else ''
            fecha = pay.get('date') or datetime.now(timezone.utc).strftime('%Y-%m-%d')
            if len(fecha) == 10:
                fecha_iso = f"{fecha}T12:00:00"
            else:
                fecha_iso = fecha
            moneda = (pay.get('currency') or {}).get('code', 'MXN') if isinstance(pay.get('currency'), dict) else 'MXN'
            tc = float((pay.get('currency') or {}).get('exchangeRate', 1) or 1) if isinstance(pay.get('currency'), dict) else 1.0

            payment_doc = {
                'company_id':         company_id,
                'source':             'alegra',
                'alegra_payment_id':  alegra_id,
                'tipo':               tipo,
                'monto':              float(pay.get('amount', 0) or 0),
                'moneda':             moneda,
                'tipo_cambio_historico': tc if moneda != 'MXN' else 1,
                'fecha_vencimiento':  fecha_iso,
                'fecha_pago':         fecha_iso,
                'estatus':            'completado',
                'es_real':            True,
                'es_proyeccion':      False,
                'concepto':           pay.get('observations') or pay.get('anotation') or f'Pago Alegra #{alegra_id}',
                'beneficiario':       beneficiario,
                'cuenta_banco':       cuenta_banco,
                'referencia':         str(pay.get('numberTemplate', {}).get('fullNumber', '') or '') if isinstance(pay.get('numberTemplate'), dict) else '',
                'metodo_pago':        'transferencia',
                'bank_transaction_id': None,
                'fuente':             'alegra_sync',
                'updated_at':         datetime.now(timezone.utc).isoformat(),
            }
            res = await db.payments.update_one(
                {'company_id': company_id, 'alegra_payment_id': alegra_id},
                {'$set': payment_doc,
                 '$setOnInsert': {'id': str(uuid.uuid4()),
                                  'created_at': datetime.now(timezone.utc).isoformat()}},
                upsert=True
            )
            if res.upserted_id: created += 1
            else: updated += 1
        results['payments'] = {'total': len(all_payments), 'created': created, 'updated': updated}
    except Exception as e:
        results['payments'] = {'error': str(e)}
        logger.error(f"[Alegra] Error sync payments: {e}")

    # Actualizar totales CxC / CxP en la empresa para dashboards
    try:
        cxc_total = await db.cfdis.count_documents({
            'company_id': company_id, 'source': 'alegra', 'tipo_cfdi': 'ingreso',
            'estado_conciliacion': {'$in': ['pendiente', 'parcial', None]}
        })
        cxp_total = await db.cfdis.count_documents({
            'company_id': company_id, 'source': 'alegra', 'tipo_cfdi': 'egreso',
            'estado_conciliacion': {'$in': ['pendiente', 'parcial', None]}
        })
    except Exception:
        cxc_total = cxp_total = 0

    # Marcar último sync + totales
    await db.companies.update_one(
        {'id': company_id},
        {'$set': {'alegra_last_sync': datetime.now(timezone.utc).isoformat(),
                  'alegra_last_sync_results': results,
                  'alegra_cxc_count': cxc_total,
                  'alegra_cxp_count': cxp_total}}
    )
    logger.info(f"[Alegra] Sync background completado para {company_id}: {results} | CxC={cxc_total} CxP={cxp_total}")


@router.post("/sync/all")
async def sync_all_background(
    request: Request,
    background_tasks: BackgroundTasks,
    data: dict = {},
    current_user: Dict = Depends(get_current_user)
):
    """Lanza sincronización completa de Alegra en background. Retorna inmediatamente."""
    company_id = await get_active_company_id(request, current_user)
    company = await db.companies.find_one({'id': company_id})
    if not company or not company.get('alegra_connected'):
        raise HTTPException(status_code=400, detail="Alegra no está conectado")

    date_from = data.get('date_from')
    date_to   = data.get('date_to')

    background_tasks.add_task(_run_alegra_sync, company_id, company, date_from, date_to)
    return {"status": "started", "message": "Sincronización Alegra iniciada. Los datos estarán disponibles en 2-3 minutos."}


@router.get("/sync/status")
async def get_alegra_sync_status(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Devuelve el estado del último sync de Alegra."""
    company_id = await get_active_company_id(request, current_user)
    company = await db.companies.find_one({'id': company_id}, {'_id': 0,
        'alegra_last_sync': 1, 'alegra_last_sync_results': 1, 'alegra_connected': 1})
    if not company:
        return {'status': 'unknown'}
    return {
        'connected': company.get('alegra_connected', False),
        'last_sync': company.get('alegra_last_sync'),
        'results':   company.get('alegra_last_sync_results', {}),
    }


@router.delete("/disconnect")
async def disconnect_alegra(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Disconnect Alegra integration"""
    company_id = await get_active_company_id(request, current_user)
    
    await db.companies.update_one(
        {'id': company_id},
        {'$set': {
            'alegra_connected': False,
            'alegra_email': None,
            'alegra_token': None
        }}
    )
    
    return {"success": True, "message": "Alegra desconectado exitosamente"}


@router.delete("/clear-data")
async def clear_alegra_data(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    clear_customers: bool = Query(True, description="Clear customers from Alegra"),
    clear_vendors: bool = Query(True, description="Clear vendors from Alegra"),
    clear_payments: bool = Query(True, description="Clear payments from Alegra"),
    clear_cfdis: bool = Query(True, description="Clear CFDIs from Alegra")
):
    """
    Clear all data synced from Alegra for the active company
    This allows re-syncing from scratch
    """
    company_id = await get_active_company_id(request, current_user)
    
    results = {
        "customers_deleted": 0,
        "vendors_deleted": 0,
        "payments_deleted": 0,
        "cfdis_deleted": 0
    }
    
    # Delete customers sourced from Alegra
    if clear_customers:
        delete_result = await db.customers.delete_many({
            'company_id': company_id,
            'source': 'alegra'
        })
        results['customers_deleted'] = delete_result.deleted_count
    
    # Delete vendors sourced from Alegra
    if clear_vendors:
        delete_result = await db.vendors.delete_many({
            'company_id': company_id,
            'source': 'alegra'
        })
        results['vendors_deleted'] = delete_result.deleted_count
    
    # Delete payments sourced from Alegra
    if clear_payments:
        delete_result = await db.payments.delete_many({
            'company_id': company_id,
            'source': 'alegra'
        })
        results['payments_deleted'] = delete_result.deleted_count
    
    # Delete CFDIs sourced from Alegra
    if clear_cfdis:
        delete_result = await db.cfdis.delete_many({
            'company_id': company_id,
            'source': 'alegra'
        })
        results['cfdis_deleted'] = delete_result.deleted_count
    
    # Reset last sync time
    await db.companies.update_one(
        {'id': company_id},
        {'$set': {'alegra_last_sync': None}}
    )
    
    total_deleted = results['customers_deleted'] + results['vendors_deleted'] + results['payments_deleted'] + results['cfdis_deleted']
    
    return {
        "success": True,
        "message": f"Se eliminaron {total_deleted} registros de Alegra",
        "results": results
    }


@router.post("/fix-mxn-totals")
async def fix_alegra_mxn_totals(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    dry_run: bool = Query(False, description="If true, only report what would change without writing")
):
    """
    Repair past Alegra-synced CFDIs whose `total` was wrongly stored in MXN
    while their `moneda` was a foreign currency (USD/EUR/...).
    
    The /cfdi/summary endpoint multiplied those totals by the FX rate again,
    producing inflated values (e.g. 17x for USD). This migration restores the
    invariant: `total` is ALWAYS in the row's original currency, with a
    reference field `total_mxn` for downstream code that needs MXN.
    
    Detection rule: A row is considered already-converted-to-MXN when
        - source == 'alegra'
        - moneda != 'MXN'
        - tipo_cambio > 1.01
        - total_moneda_original is missing OR (total ~= total_moneda_original * tipo_cambio
          but NOT ~= total_moneda_original)
    
    Safe to re-run; idempotent.
    """
    company_id = await get_active_company_id(request, current_user)
    
    cursor = db.cfdis.find(
        {'company_id': company_id, 'source': 'alegra'},
        {'_id': 0}
    )
    
    examined = 0
    fixed = 0
    skipped_already_ok = 0
    skipped_mxn = 0
    samples_before = []
    samples_after = []
    
    async for c in cursor:
        examined += 1
        moneda = c.get('moneda', 'MXN') or 'MXN'
        if moneda == 'MXN':
            skipped_mxn += 1
            continue
        
        total = float(c.get('total', 0) or 0)
        tc = float(c.get('tipo_cambio', 1) or 1)
        if tc <= 1.01:
            skipped_already_ok += 1
            continue
        
        original = c.get('total_moneda_original')
        # Heuristic: if total_moneda_original exists and total >= original * (tc - 0.5),
        # the `total` field is in MXN (wrong). If total is approx equal to original,
        # it is already in original currency (correct).
        if original is not None:
            try:
                original = float(original)
            except Exception:
                original = None
        
        is_inflated = False
        if original and original > 0:
            # Already-correct case: total ~= original (within 1%)
            if abs(total - original) / max(original, 1) < 0.01:
                skipped_already_ok += 1
                continue
            # Inflated case: total ~= original * tc (within 5%)
            expected_mxn = original * tc
            if abs(total - expected_mxn) / max(expected_mxn, 1) < 0.05:
                is_inflated = True
        else:
            # No reference value — assume inflated (legacy code always stored MXN)
            is_inflated = True
            original = round(total / tc, 2) if tc > 0 else total
        
        if not is_inflated:
            skipped_already_ok += 1
            continue
        
        new_total = round(original, 2)
        new_total_mxn = round(original * tc, 2)
        
        # Same heuristic for monto_cobrado / monto_pagado
        cobrado = float(c.get('monto_cobrado', 0) or 0)
        pagado = float(c.get('monto_pagado', 0) or 0)
        new_cobrado = round(cobrado / tc, 2) if cobrado > 0 and tc > 0 else cobrado
        new_pagado = round(pagado / tc, 2) if pagado > 0 and tc > 0 else pagado
        
        # Recompute taxes from the new (original-currency) total
        new_subtotal = round(new_total / 1.16, 2) if new_total > 0 else 0
        new_impuestos = round(new_total - new_subtotal, 2)
        
        if len(samples_before) < 3:
            samples_before.append({
                'uuid': c.get('uuid'),
                'moneda': moneda,
                'tipo_cambio': tc,
                'total_was': total,
                'total_will_be': new_total,
                'total_mxn': new_total_mxn,
            })
        
        if not dry_run:
            await db.cfdis.update_one(
                {'id': c['id']},
                {'$set': {
                    'total': new_total,
                    'total_mxn': new_total_mxn,
                    'total_moneda_original': new_total,
                    'subtotal': new_subtotal,
                    'impuestos': new_impuestos,
                    'iva_trasladado': new_impuestos,
                    'monto_cobrado': new_cobrado,
                    'monto_cobrado_mxn': round(new_cobrado * tc, 2),
                    'monto_pagado': new_pagado,
                    'monto_pagado_mxn': round(new_pagado * tc, 2),
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                }}
            )
        fixed += 1
        if len(samples_after) < 3:
            samples_after.append({
                'uuid': c.get('uuid'),
                'moneda': moneda,
                'total': new_total,
                'total_mxn': new_total_mxn,
            })
    
    return {
        'success': True,
        'dry_run': dry_run,
        'examined': examined,
        'fixed': fixed,
        'skipped_already_ok': skipped_already_ok,
        'skipped_mxn_native': skipped_mxn,
        'samples_before': samples_before,
        'samples_after': samples_after if not dry_run else [],
        'message': (f"Se corregirían {fixed} CFDIs" if dry_run
                    else f"Se corrigieron {fixed} CFDIs (de {examined} examinados)")
    }


# ══════════════════════════════════════════════════════════════════════
# T1-A — CxC y CxP CON AGING (calculado desde CFDIs sincronizados)
# ══════════════════════════════════════════════════════════════════════

def _build_aging_bucket(dias_vencido: int) -> str:
    if dias_vencido <= 0:   return 'corriente'
    if dias_vencido <= 30:  return 'vencido_30'
    if dias_vencido <= 60:  return 'vencido_60'
    if dias_vencido <= 90:  return 'vencido_90'
    return 'vencido_mas90'


@router.get("/cxc")
async def get_alegra_cxc(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """CxC de Alegra con aging calculado desde CFDIs sincronizados (no requiere llamada extra a la API)."""
    company_id = await get_active_company_id(request, current_user)
    today = date.today()

    invoices = await db.cfdis.find({
        'company_id':         company_id,
        'source':             'alegra',
        'tipo_cfdi':          'ingreso',
        'estatus':            {'$ne': 'cancelado'},
        'estado_conciliacion': {'$in': ['pendiente', 'parcial', None]},
    }, {'_id': 0}).to_list(5000)

    facturas = []
    aging = {'corriente': 0.0, 'vencido_30': 0.0, 'vencido_60': 0.0, 'vencido_90': 0.0, 'vencido_mas90': 0.0}
    total_pendiente = 0.0

    for inv in invoices:
        total_inv = float(inv.get('total', 0) or 0)
        cobrado   = float(inv.get('monto_cobrado', 0) or 0)
        saldo     = round(total_inv - cobrado, 2)
        if saldo < 0.01:
            continue

        fecha_venc_raw = inv.get('fecha_vencimiento') or inv.get('fecha_emision', '')
        dias_vencido = 0
        if fecha_venc_raw:
            try:
                dias_vencido = (today - date.fromisoformat(str(fecha_venc_raw)[:10])).days
            except Exception:
                pass

        bucket = _build_aging_bucket(dias_vencido)
        aging[bucket] += saldo
        total_pendiente += saldo

        facturas.append({
            'uuid':                inv.get('uuid', ''),
            'alegra_id':           inv.get('alegra_id', ''),
            'cliente_nombre':      inv.get('receptor_nombre', ''),
            'cliente_rfc':         inv.get('receptor_rfc', ''),
            'fecha_emision':       str(inv.get('fecha_emision', ''))[:10],
            'fecha_vencimiento':   str(fecha_venc_raw)[:10] if fecha_venc_raw else '',
            'saldo_pendiente':     saldo,
            'total':               total_inv,
            'monto_cobrado':       cobrado,
            'moneda':              inv.get('moneda', 'MXN'),
            'tipo_cambio':         float(inv.get('tipo_cambio', 1) or 1),
            'dias_vencido':        dias_vencido,
            'estado_conciliacion': inv.get('estado_conciliacion', 'pendiente'),
            'referencia':          inv.get('referencia', ''),
        })

    facturas.sort(key=lambda x: x['dias_vencido'], reverse=True)
    vencido_total = sum(aging[k] for k in ['vencido_30', 'vencido_60', 'vencido_90', 'vencido_mas90'])

    return {
        'cut_date':       today.isoformat(),
        'num_facturas':   len(facturas),
        'num_clientes':   len({f['cliente_nombre'] for f in facturas}),
        'total_pendiente': round(total_pendiente, 2),
        'aging':          {k: round(v, 2) for k, v in aging.items()},
        'pct_vencido':    round(vencido_total / max(total_pendiente, 1) * 100, 1),
        'facturas':       facturas,
        'source':         'alegra_sync',
        'fetched_at':     datetime.now(timezone.utc).isoformat(),
    }


@router.get("/cxp")
async def get_alegra_cxp(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """CxP de Alegra con aging calculado desde CFDIs sincronizados."""
    company_id = await get_active_company_id(request, current_user)
    today = date.today()

    bills = await db.cfdis.find({
        'company_id':         company_id,
        'source':             'alegra',
        'tipo_cfdi':          'egreso',
        'estatus':            {'$ne': 'cancelado'},
        'estado_conciliacion': {'$in': ['pendiente', 'parcial', None]},
    }, {'_id': 0}).to_list(5000)

    facturas = []
    aging = {'corriente': 0.0, 'vencido_30': 0.0, 'vencido_60': 0.0, 'vencido_90': 0.0, 'vencido_mas90': 0.0}
    total_pendiente = 0.0

    for bill in bills:
        total_bill = float(bill.get('total', 0) or 0)
        pagado     = float(bill.get('monto_pagado', 0) or 0)
        saldo      = round(total_bill - pagado, 2)
        if saldo < 0.01:
            continue

        fecha_venc_raw = bill.get('fecha_vencimiento') or bill.get('fecha_emision', '')
        dias_vencido = 0
        if fecha_venc_raw:
            try:
                dias_vencido = (today - date.fromisoformat(str(fecha_venc_raw)[:10])).days
            except Exception:
                pass

        bucket = _build_aging_bucket(dias_vencido)
        aging[bucket] += saldo
        total_pendiente += saldo

        facturas.append({
            'uuid':                bill.get('uuid', ''),
            'alegra_id':           bill.get('alegra_id', ''),
            'proveedor_nombre':    bill.get('emisor_nombre', ''),
            'proveedor_rfc':       bill.get('emisor_rfc', ''),
            'fecha_emision':       str(bill.get('fecha_emision', ''))[:10],
            'fecha_vencimiento':   str(fecha_venc_raw)[:10] if fecha_venc_raw else '',
            'saldo_pendiente':     saldo,
            'total':               total_bill,
            'monto_pagado':        pagado,
            'moneda':              bill.get('moneda', 'MXN'),
            'tipo_cambio':         float(bill.get('tipo_cambio', 1) or 1),
            'dias_vencido':        dias_vencido,
            'estado_conciliacion': bill.get('estado_conciliacion', 'pendiente'),
            'referencia':          bill.get('referencia', ''),
        })

    facturas.sort(key=lambda x: x['dias_vencido'], reverse=True)
    vencido_total = sum(aging[k] for k in ['vencido_30', 'vencido_60', 'vencido_90', 'vencido_mas90'])

    return {
        'cut_date':        today.isoformat(),
        'num_facturas':    len(facturas),
        'num_proveedores': len({f['proveedor_nombre'] for f in facturas}),
        'total_pendiente': round(total_pendiente, 2),
        'aging':           {k: round(v, 2) for k, v in aging.items()},
        'pct_vencido':     round(vencido_total / max(total_pendiente, 1) * 100, 1),
        'facturas':        facturas,
        'source':          'alegra_sync',
        'fetched_at':      datetime.now(timezone.utc).isoformat(),
    }


@router.get("/cxc-cxp-summary")
async def get_alegra_cxc_cxp_summary(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Resumen CxC + CxP de Alegra para dashboards y Tesorería."""
    cxc = await get_alegra_cxc(request, current_user)
    cxp = await get_alegra_cxp(request, current_user)
    return {
        'cut_date': date.today().isoformat(),
        'cxc': {
            'total':      cxc['total_pendiente'],
            'vencido':    sum(cxc['aging'][k] for k in ['vencido_30', 'vencido_60', 'vencido_90', 'vencido_mas90']),
            'corriente':  cxc['aging']['corriente'],
            'count':      cxc['num_clientes'],
            'pct_vencido': cxc['pct_vencido'],
        },
        'cxp': {
            'total':      cxp['total_pendiente'],
            'vencido':    sum(cxp['aging'][k] for k in ['vencido_30', 'vencido_60', 'vencido_90', 'vencido_mas90']),
            'corriente':  cxp['aging']['corriente'],
            'count':      cxp['num_proveedores'],
            'pct_vencido': cxp['pct_vencido'],
        },
        'flujo_neto_esperado': round(cxc['total_pendiente'] - cxp['total_pendiente'], 2),
        'fetched_at': datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════
# T1-B — ESTADOS FINANCIEROS (expone alegra_financials.py)
# ══════════════════════════════════════════════════════════════════════

@router.post("/generate-financials")
async def generate_alegra_financials(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    periodo: str = Query(..., description="Período YYYY-MM, ej: 2026-01"),
):
    """
    Genera Estado de Resultados + Balance General desde los CFDIs de Alegra
    y los persiste en financial_statements para que Board Report los lea.
    """
    company_id = await get_active_company_id(request, current_user)
    from services.alegra_financials import generate_alegra_financial_statements
    result = await generate_alegra_financial_statements(db, company_id, periodo)
    if result.get('status') == 'success':
        await db.companies.update_one(
            {'id': company_id},
            {'$set': {'alegra_last_financial_sync': datetime.now(timezone.utc).isoformat()}}
        )
    return result


@router.get("/financial-statements/{periodo}")
async def get_alegra_financial_statements(
    periodo: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Retorna los estados financieros de Alegra guardados para un período."""
    company_id = await get_active_company_id(request, current_user)
    docs = await db.financial_statements.find(
        {'company_id': company_id, 'periodo': periodo, 'source': 'alegra'},
        {'_id': 0}
    ).to_list(10)
    return {'success': True, 'periodo': periodo, 'count': len(docs), 'statements': docs}


# ══════════════════════════════════════════════════════════════════════
# T1-C — AUTO-CATEGORIZACIÓN CxC/CxP PARA ALEGRA
# ══════════════════════════════════════════════════════════════════════

_ALEGRA_CXC_CATEGORIES = [
    {"code": "ING-001", "nombre": "Ventas de productos"},
    {"code": "ING-002", "nombre": "Prestación de servicios"},
    {"code": "ING-003", "nombre": "Honorarios profesionales"},
    {"code": "ING-004", "nombre": "Arrendamiento cobrado"},
    {"code": "ING-005", "nombre": "Cobro de anticipos"},
    {"code": "ING-007", "nombre": "Intereses cobrados"},
    {"code": "ING-099", "nombre": "Otros ingresos por cobrar"},
]
_ALEGRA_CXP_CATEGORIES = [
    {"code": "EGR-001", "nombre": "Nómina y salarios"},
    {"code": "EGR-002", "nombre": "IMSS / INFONAVIT"},
    {"code": "EGR-003", "nombre": "ISR (pago provisional)"},
    {"code": "EGR-004", "nombre": "IVA (pago mensual)"},
    {"code": "EGR-005", "nombre": "Renta / arrendamiento"},
    {"code": "EGR-006", "nombre": "Proveedores de materia prima"},
    {"code": "EGR-007", "nombre": "Servicios (luz, agua, gas)"},
    {"code": "EGR-008", "nombre": "Telefonía e internet"},
    {"code": "EGR-009", "nombre": "Publicidad y marketing"},
    {"code": "EGR-010", "nombre": "Honorarios externos"},
    {"code": "EGR-015", "nombre": "Software y suscripciones"},
    {"code": "EGR-016", "nombre": "Pago de crédito bancario"},
    {"code": "EGR-017", "nombre": "Intereses pagados"},
    {"code": "EGR-018", "nombre": "Comisiones bancarias"},
    {"code": "EGR-099", "nombre": "Otros egresos por pagar"},
]


@router.post("/auto-categorize-cxc")
async def auto_categorize_alegra_cxc(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    solo_sin_categoria: bool = Query(True),
):
    """Auto-categoriza clientes (CxC) y proveedores (CxP) de Alegra usando Claude IA."""
    import json as _json
    company_id = await get_active_company_id(request, current_user)

    cxc_docs = await db.cfdis.find({
        'company_id': company_id, 'source': 'alegra', 'tipo_cfdi': 'ingreso',
        'estado_conciliacion': {'$in': ['pendiente', 'parcial', None]},
    }, {'_id': 0, 'receptor_nombre': 1, 'total': 1}).to_list(5000)

    cxp_docs = await db.cfdis.find({
        'company_id': company_id, 'source': 'alegra', 'tipo_cfdi': 'egreso',
        'estado_conciliacion': {'$in': ['pendiente', 'parcial', None]},
    }, {'_id': 0, 'emisor_nombre': 1, 'total': 1}).to_list(5000)

    if not cxc_docs and not cxp_docs:
        return {'success': True, 'message': 'No hay datos de Alegra para categorizar', 'updated': 0}

    if solo_sin_categoria:
        ya = await db.cxc_categorias.find(
            {'company_id': company_id}, {'nombre': 1, 'tipo': 1, '_id': 0}
        ).to_list(1000)
        ya_set = {(d['nombre'], d['tipo']) for d in ya}
        cxc_docs = [f for f in cxc_docs if (f.get('receptor_nombre', ''), 'cxc') not in ya_set]
        cxp_docs = [f for f in cxp_docs if (f.get('emisor_nombre', ''), 'cxp') not in ya_set]

    items, seen = [], set()
    for f in cxc_docs:
        n = (f.get('receptor_nombre') or '').strip()
        if n and n not in seen:
            seen.add(n)
            items.append({'nombre': n, 'tipo': 'cxc', 'monto': float(f.get('total', 0))})
    for f in cxp_docs:
        n = (f.get('emisor_nombre') or '').strip()
        if n and n not in seen:
            seen.add(n)
            items.append({'nombre': n, 'tipo': 'cxp', 'monto': float(f.get('total', 0))})

    if not items:
        return {'success': True, 'message': 'Todos ya tienen categoría asignada', 'updated': 0}

    cat_cxc_txt = '\n'.join(f'  code="{c["code"]}" | nombre="{c["nombre"]}"' for c in _ALEGRA_CXC_CATEGORIES)
    cat_cxp_txt = '\n'.join(f'  code="{c["code"]}" | nombre="{c["nombre"]}"' for c in _ALEGRA_CXP_CATEGORIES)
    items_txt   = '\n'.join(f'[{i}] nombre="{it["nombre"]}" | tipo={it["tipo"]} | monto={it["monto"]:.2f}' for i, it in enumerate(items))

    prompt = f"""Eres experto en contabilidad mexicana. Categoriza CxC y CxP de Alegra.

CATEGORÍAS CxC:
{cat_cxc_txt}

CATEGORÍAS CxP:
{cat_cxp_txt}

ELEMENTOS:
{items_txt}

REGLAS: tipo "cxc"→ING-xxx, tipo "cxp"→EGR-xxx.
Infiere por nombre: TELMEX/TELCEL→EGR-008, IMSS→EGR-002, SAT/HACIENDA→EGR-003.
Sin pista→ING-099 para cxc, EGR-099 para cxp.

Responde SOLO JSON array sin texto:
[{{"nombre":"X","tipo":"cxc","category_code":"ING-001"}}]"""

    import os as _os
    api_key = _os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        raise HTTPException(status_code=500, detail='ANTHROPIC_API_KEY no configurada')

    try:
        async with httpx.AsyncClient(timeout=60) as http:
            res = await http.post(
                'https://api.anthropic.com/v1/messages',
                headers={'x-api-key': api_key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
                json={'model': 'claude-sonnet-4-6', 'max_tokens': 4096,
                      'messages': [{'role': 'user', 'content': prompt}]},
            )
            res.raise_for_status()
            raw_text = res.json()['content'][0]['text'].strip()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=500, detail=f'Error Claude API {e.response.status_code}: {e.response.text[:200]}')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error Claude API: {str(e)}')

    try:
        assignments = _json.loads(raw_text.replace('```json', '').replace('```', '').strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error parseando respuesta IA: {str(e)}')

    all_cats = {c['code']: c for c in _ALEGRA_CXC_CATEGORIES + _ALEGRA_CXP_CATEGORIES}
    updated, errors = 0, []

    for a in assignments:
        nombre = (a.get('nombre') or '').strip()
        tipo   = a.get('tipo', 'cxc')
        code   = a.get('category_code', '')
        if not nombre or not code:
            continue
        cat = all_cats.get(code)
        if not cat:
            errors.append(f'Código desconocido: {code}')
            continue
        try:
            await db.cxc_categorias.update_one(
                {'company_id': company_id, 'nombre': nombre, 'tipo': tipo},
                {'$set': {
                    'company_id':    company_id,
                    'nombre':        nombre,
                    'tipo':          tipo,
                    'category_code': code,
                    'category_name': cat['nombre'],
                    'categorized_by': 'ai',
                    'source':        'alegra',
                    'updated_at':    datetime.now(timezone.utc),
                }},
                upsert=True
            )
            updated += 1
        except Exception as e:
            errors.append(f'Error {nombre}: {str(e)}')

    return {
        'success':   True,
        'processed': len(items),
        'updated':   updated,
        'errors':    errors,
        'message':   f'{updated} de {len(items)} clientes/proveedores categorizados con IA',
    }


@router.get("/categorias-cxc")
async def get_alegra_categorias_cxc(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Lista categorías guardadas para CxC/CxP de Alegra."""
    company_id = await get_active_company_id(request, current_user)
    docs = await db.cxc_categorias.find(
        {'company_id': company_id, 'source': 'alegra'}, {'_id': 0}
    ).to_list(1000)
    return {'categorias_guardadas': docs, 'catalogo_cxc': _ALEGRA_CXC_CATEGORIES, 'catalogo_cxp': _ALEGRA_CXP_CATEGORIES}


# ══════════════════════════════════════════════════════════════════════
# CONCILIACIÓN BANCARIA CON IA
# ══════════════════════════════════════════════════════════════════════

@router.post("/reconciliation/analyze")
async def analyze_alegra_bank_reconciliation(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    date_from: str = Query(None, description="Fecha desde YYYY-MM-DD"),
    date_to:   str = Query(None, description="Fecha hasta YYYY-MM-DD"),
    confidence_threshold: float = Query(0.65, ge=0.0, le=1.0, description="Umbral mínimo de confianza"),
):
    """
    Cruza movimientos bancarios de Alegra contra CFDIs sincronizados.
    Retorna matches con % de confianza para que el usuario apruebe o rechace.
    """
    company_id = await get_active_company_id(request, current_user)
    company = await db.companies.find_one({'id': company_id}, {'_id': 0})
    if not company.get('alegra_connected'):
        raise HTTPException(status_code=400, detail='Alegra no está conectado')

    email = company.get('alegra_email')
    token = company.get('alegra_token')

    # 1. Obtener cuentas bancarias de Alegra
    bank_accounts = await alegra_request('GET', 'bank-accounts', email, token)
    if not bank_accounts or not isinstance(bank_accounts, list):
        raise HTTPException(status_code=400, detail='No se pudieron obtener cuentas bancarias de Alegra')

    # 2. Obtener movimientos de cada cuenta
    all_movements = []
    for account in bank_accounts:
        account_id = account.get('id')
        params: dict = {'start': 0, 'limit': 200}
        if date_from: params['date_start'] = date_from
        if date_to:   params['date_end']   = date_to
        try:
            movements = await alegra_request(
                'GET', f'bank-accounts/{account_id}/bank-movements', email, token, params=params
            )
            if movements and isinstance(movements, list):
                for mov in movements:
                    mov['_account_name'] = account.get('name', '')
                    mov['_account_id']   = str(account_id)
                all_movements.extend(movements)
        except Exception as exc:
            logger.warning(f'Error obteniendo movimientos de cuenta {account_id}: {exc}')

    if not all_movements:
        return {'success': True, 'message': 'Sin movimientos bancarios en el período', 'matches': [], 'total_movements': 0}

    # 3. CFDIs pendientes de Alegra como candidatos a conciliar
    cfdi_query: dict = {
        'company_id':         company_id,
        'source':             'alegra',
        'estado_conciliacion': {'$in': ['pendiente', 'parcial']},
        'estatus':            {'$ne': 'cancelado'},
    }
    if date_from:
        cfdi_query['fecha_emision'] = {'$gte': date_from}
    cfdis_pendientes = await db.cfdis.find(cfdi_query, {'_id': 0}).to_list(5000)

    # 4. Algoritmo de matching multi-criterio
    matches: list = []
    unmatched: list = []

    for mov in all_movements:
        mov_raw_amount = float(mov.get('amount', 0) or 0)
        mov_amount = abs(mov_raw_amount)
        if mov_amount < 0.01:
            continue

        mov_date = str(mov.get('date', ''))[:10]
        mov_desc = (mov.get('description') or mov.get('observations') or '').lower()
        mov_tipo = 'ingreso' if mov_raw_amount > 0 else 'egreso'

        # Filtrar por fecha si se especificó
        if date_from and mov_date and mov_date < date_from:
            continue
        if date_to and mov_date and mov_date > date_to:
            continue

        best_cfdi  = None
        best_score = 0.0
        best_reasons: list = []

        for cfdi in cfdis_pendientes:
            if cfdi.get('tipo_cfdi') != mov_tipo:
                continue

            cfdi_total  = float(cfdi.get('total', 0) or 0)
            cfdi_cobrado = float(cfdi.get('monto_cobrado', 0) or 0)
            cfdi_pagado  = float(cfdi.get('monto_pagado', 0) or 0)
            saldo_pendiente = cfdi_total - (cfdi_cobrado if mov_tipo == 'ingreso' else cfdi_pagado)
            if saldo_pendiente < 0.01:
                continue

            score   = 0.0
            reasons: list = []

            # Criterio A: monto (peso 50%)
            if abs(mov_amount - cfdi_total) < 0.02:
                score += 0.50; reasons.append('monto_exacto')
            elif abs(mov_amount - saldo_pendiente) < 0.02:
                score += 0.42; reasons.append('monto_saldo_exacto')
            elif cfdi_total > 0 and abs(mov_amount - cfdi_total) / cfdi_total < 0.02:
                score += 0.30; reasons.append('monto_aproximado_2pct')

            # Criterio B: fecha (peso 25%)
            cfdi_fecha = str(cfdi.get('fecha_vencimiento') or cfdi.get('fecha_emision', ''))[:10]
            if cfdi_fecha and mov_date:
                try:
                    dias = abs((date.fromisoformat(mov_date) - date.fromisoformat(cfdi_fecha)).days)
                    if dias <= 3:
                        score += 0.25; reasons.append(f'fecha_±{dias}d')
                    elif dias <= 15:
                        score += 0.15; reasons.append(f'fecha_±{dias}d')
                    elif dias <= 45:
                        score += 0.05; reasons.append(f'fecha_±{dias}d')
                except Exception:
                    pass

            # Criterio C: nombre en descripción (peso 25%)
            nombres = [
                (cfdi.get('receptor_nombre') or '').lower(),
                (cfdi.get('emisor_nombre') or '').lower(),
            ]
            for nombre in nombres:
                if nombre and len(nombre) >= 4 and nombre[:6] in mov_desc:
                    score += 0.25; reasons.append('nombre_en_descripcion'); break

            ref = (cfdi.get('referencia') or '').lower()
            if ref and len(ref) >= 3 and ref in mov_desc:
                score += 0.10; reasons.append('referencia_encontrada')

            score = min(round(score, 3), 1.0)
            if score > best_score:
                best_score   = score
                best_cfdi    = cfdi
                best_reasons = reasons

        if best_cfdi and best_score >= confidence_threshold:
            cfdi_total_m = float(best_cfdi.get('total', 0) or 0)
            cobrado_m    = float(best_cfdi.get('monto_cobrado', 0) or 0)
            pagado_m     = float(best_cfdi.get('monto_pagado', 0) or 0)
            saldo_m = cfdi_total_m - (cobrado_m if mov_tipo == 'ingreso' else pagado_m)

            match_doc = {
                'match_id':   str(uuid.uuid4()),
                'company_id': company_id,
                'movement': {
                    'alegra_id':      str(mov.get('id', '')),
                    'date':           mov_date,
                    'amount':         mov_amount,
                    'type':           mov_tipo,
                    'description':    mov.get('description') or mov.get('observations', ''),
                    'bank_account':   mov.get('_account_name', ''),
                    'bank_account_id': mov.get('_account_id', ''),
                },
                'cfdi': {
                    'id':             best_cfdi.get('id', ''),
                    'uuid':           best_cfdi.get('uuid', ''),
                    'tipo_cfdi':      best_cfdi.get('tipo_cfdi', ''),
                    'receptor_nombre': best_cfdi.get('receptor_nombre', ''),
                    'emisor_nombre':  best_cfdi.get('emisor_nombre', ''),
                    'total':          cfdi_total_m,
                    'saldo_pendiente': round(saldo_m, 2),
                    'fecha_emision':  str(best_cfdi.get('fecha_emision', ''))[:10],
                    'fecha_vencimiento': str(best_cfdi.get('fecha_vencimiento', ''))[:10],
                    'referencia':     best_cfdi.get('referencia', ''),
                },
                'confidence':     best_score,
                'confidence_pct': round(best_score * 100, 1),
                'reasons':        best_reasons,
                'status':         'pending_approval',
                'created_at':     datetime.now(timezone.utc).isoformat(),
            }
            await db.alegra_reconciliation_matches.update_one(
                {'company_id': company_id, 'movement.alegra_id': match_doc['movement']['alegra_id']},
                {'$set': match_doc},
                upsert=True
            )
            matches.append(match_doc)
        else:
            unmatched.append({
                'alegra_id':  str(mov.get('id', '')),
                'date':       mov_date,
                'amount':     mov_amount,
                'type':       mov_tipo,
                'description': mov.get('description') or '',
                'best_score': best_score,
            })

    matches.sort(key=lambda x: x['confidence'], reverse=True)

    return {
        'success':            True,
        'total_movements':    len(all_movements),
        'matches_found':      len(matches),
        'unmatched':          len(unmatched),
        'confidence_threshold': confidence_threshold,
        'matches':            matches,
        'unmatched_movements': unmatched[:30],
        'message':            f'{len(matches)} movimientos cruzados con CFDIs (confianza ≥ {confidence_threshold*100:.0f}%)',
    }


@router.get("/reconciliation/pending")
async def get_pending_reconciliation_matches(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Lista matches de conciliación pendientes de aprobación."""
    company_id = await get_active_company_id(request, current_user)
    matches = await db.alegra_reconciliation_matches.find(
        {'company_id': company_id, 'status': 'pending_approval'},
        {'_id': 0}
    ).sort('confidence', -1).to_list(200)
    return {'success': True, 'count': len(matches), 'matches': matches}


@router.post("/reconciliation/approve/{match_id}")
async def approve_alegra_reconciliation(
    match_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
    monto_aplicar: Optional[float] = Query(None, description="Monto a aplicar (default: monto del movimiento)"),
):
    """Aprueba un match y actualiza el CFDI + crea registro de pago."""
    company_id = await get_active_company_id(request, current_user)

    match = await db.alegra_reconciliation_matches.find_one(
        {'match_id': match_id, 'company_id': company_id}, {'_id': 0}
    )
    if not match:
        raise HTTPException(status_code=404, detail='Match no encontrado')
    if match.get('status') == 'approved':
        raise HTTPException(status_code=400, detail='Este match ya fue aprobado')

    cfdi_id    = match['cfdi']['id']
    mov_amount = monto_aplicar or match['movement']['amount']
    tipo_cfdi  = match['cfdi']['tipo_cfdi']

    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail='CFDI no encontrado')

    cfdi_total = float(cfdi.get('total', 0) or 0)
    now_iso    = datetime.now(timezone.utc).isoformat()

    if tipo_cfdi == 'ingreso':
        ya          = float(cfdi.get('monto_cobrado', 0) or 0)
        nuevo       = round(min(ya + mov_amount, cfdi_total), 2)
        nuevo_estado = 'conciliado' if nuevo >= cfdi_total - 0.01 else 'parcial'
        await db.cfdis.update_one(
            {'id': cfdi_id, 'company_id': company_id},
            {'$set': {'monto_cobrado': nuevo, 'estado_conciliacion': nuevo_estado, 'updated_at': now_iso}}
        )
    else:
        ya          = float(cfdi.get('monto_pagado', 0) or 0)
        nuevo       = round(min(ya + mov_amount, cfdi_total), 2)
        nuevo_estado = 'conciliado' if nuevo >= cfdi_total - 0.01 else 'parcial'
        await db.cfdis.update_one(
            {'id': cfdi_id, 'company_id': company_id},
            {'$set': {'monto_pagado': nuevo, 'estado_conciliacion': nuevo_estado, 'updated_at': now_iso}}
        )

    await db.alegra_reconciliation_matches.update_one(
        {'match_id': match_id},
        {'$set': {'status': 'approved', 'approved_by': current_user['id'],
                  'approved_at': now_iso, 'monto_aplicado': round(mov_amount, 2)}}
    )

    beneficiario = match['cfdi']['receptor_nombre'] or match['cfdi']['emisor_nombre']
    await db.payments.insert_one({
        'id':                  str(uuid.uuid4()),
        'company_id':          company_id,
        'cfdi_id':             cfdi_id,
        'cfdi_uuid':           cfdi.get('uuid'),
        'tipo':                'cobro' if tipo_cfdi == 'ingreso' else 'pago',
        'concepto':            f"Conciliación Alegra — {match['movement']['description'][:80]}",
        'monto':               round(mov_amount, 2),
        'moneda':              'MXN',
        'fecha_pago':          match['movement']['date'],
        'fecha_vencimiento':   match['movement']['date'],
        'estatus':             'completado',
        'es_real':             True,
        'source':              'alegra_reconciliation',
        'alegra_movement_id':  match['movement']['alegra_id'],
        'beneficiario':        beneficiario,
        'created_at':          now_iso,
    })

    return {
        'success':       True,
        'message':       f'Conciliación aprobada. CFDI {nuevo_estado}.',
        'cfdi_id':       cfdi_id,
        'monto_aplicado': round(mov_amount, 2),
        'nuevo_estado':  nuevo_estado,
    }


@router.post("/reconciliation/reject/{match_id}")
async def reject_alegra_reconciliation(
    match_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
    motivo: str = Query('', description="Motivo del rechazo"),
):
    """Rechaza un match propuesto por la IA."""
    company_id = await get_active_company_id(request, current_user)

    match = await db.alegra_reconciliation_matches.find_one(
        {'match_id': match_id, 'company_id': company_id}, {'_id': 0}
    )
    if not match:
        raise HTTPException(status_code=404, detail='Match no encontrado')

    await db.alegra_reconciliation_matches.update_one(
        {'match_id': match_id},
        {'$set': {'status': 'rejected', 'rejected_by': current_user['id'],
                  'rejected_at': datetime.now(timezone.utc).isoformat(),
                  'motivo_rechazo': motivo}}
    )
    return {'success': True, 'message': 'Match rechazado', 'match_id': match_id}


# ─── Conciliaciones Bancarias ────────────────────────────────────────────────

@router.get("/conciliations")
async def get_alegra_conciliations(
    request: Request,
    account_id: Optional[str] = None,
    limit: int = 30,
    start: int = 0,
    fields: Optional[str] = None,
    current_user: Dict = Depends(get_current_user)
):
    """Lista conciliaciones bancarias de Alegra."""
    company_id = await get_active_company_id(request, current_user)
    company = await db.companies.find_one({'id': company_id}, {'_id': 0})
    if not company or not company.get('alegra_connected'):
        raise HTTPException(status_code=400, detail="Alegra no configurado")
    email = company.get('alegra_email')
    token = company.get('alegra_token')

    params = {'limit': min(limit, 30), 'start': start, 'order_direction': 'DESC', 'order_field': 'date'}
    if account_id:
        params['account_id'] = account_id
    if fields:
        params['fields'] = fields

    data = await alegra_request('GET', 'conciliations', email, token, params=params)
    if data is None:
        return []

    if isinstance(data, list):
        for item in data:
            await db.alegra_conciliations.update_one(
                {'company_id': company_id, 'alegra_id': str(item.get('id'))},
                {'$set': {**item, 'company_id': company_id, 'alegra_id': str(item.get('id')),
                          'synced_at': datetime.now(timezone.utc).isoformat()}},
                upsert=True
            )

    return data


@router.get("/conciliations/summary")
async def get_conciliations_summary(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Resumen de conciliaciones: total, abiertas, con transacciones."""
    company_id = await get_active_company_id(request, current_user)
    company = await db.companies.find_one({'id': company_id}, {'_id': 0})
    if not company or not company.get('alegra_connected'):
        raise HTTPException(status_code=400, detail="Alegra no configurado")
    email = company.get('alegra_email')
    token = company.get('alegra_token')

    data = await alegra_request('GET', 'conciliations', email, token,
                                params={'limit': 30, 'fields': 'balance', 'order_direction': 'DESC'})
    if not data or not isinstance(data, list):
        return {'total': 0, 'abiertas': 0, 'cerradas': 0, 'con_transacciones': 0}

    return {
        'total': len(data),
        'abiertas': sum(1 for c in data if c.get('status') == 'open'),
        'cerradas': sum(1 for c in data if c.get('status') != 'open'),
        'con_transacciones': sum(1 for c in data if c.get('transactions')),
        'ultima_fecha': data[0].get('date') if data else None,
        'ultima_cuenta': data[0].get('account', {}).get('name') if data else None,
    }


# ─── CxC / CxP desde Alegra ──────────────────────────────────────────────────

@router.get("/receivables")
async def get_alegra_receivables(
    request: Request,
    limit: int = 30,
    start: int = 0,
    current_user: Dict = Depends(get_current_user)
):
    """Cuentas por cobrar (facturas abiertas) desde Alegra."""
    company_id = await get_active_company_id(request, current_user)
    company = await db.companies.find_one({'id': company_id}, {'_id': 0})
    if not company or not company.get('alegra_connected'):
        raise HTTPException(status_code=400, detail="Alegra no configurado")
    email = company.get('alegra_email')
    token = company.get('alegra_token')

    params = {'status': 'open', 'limit': min(limit, 30), 'start': start,
              'order_field': 'dueDate', 'order_direction': 'ASC'}
    data = await alegra_request('GET', 'invoices', email, token, params=params)
    if not data or not isinstance(data, list):
        return {'invoices': [], 'total': 0, 'total_amount': 0}

    total_amount = sum(float(i.get('total', 0)) for i in data)
    vencidas = [i for i in data if i.get('dueDate') and i['dueDate'] < datetime.now().strftime('%Y-%m-%d')]

    return {
        'invoices': data,
        'total': len(data),
        'total_amount': round(total_amount, 2),
        'vencidas': len(vencidas),
        'monto_vencido': round(sum(float(i.get('total', 0)) for i in vencidas), 2),
    }


@router.get("/payables")
async def get_alegra_payables(
    request: Request,
    limit: int = 30,
    start: int = 0,
    current_user: Dict = Depends(get_current_user)
):
    """Cuentas por pagar (bills abiertas) desde Alegra."""
    company_id = await get_active_company_id(request, current_user)
    company = await db.companies.find_one({'id': company_id}, {'_id': 0})
    if not company or not company.get('alegra_connected'):
        raise HTTPException(status_code=400, detail="Alegra no configurado")
    email = company.get('alegra_email')
    token = company.get('alegra_token')

    params = {'status': 'open', 'limit': min(limit, 30), 'start': start,
              'order_field': 'dueDate', 'order_direction': 'ASC'}
    data = await alegra_request('GET', 'bills', email, token, params=params)
    if not data or not isinstance(data, list):
        return {'bills': [], 'total': 0, 'total_amount': 0}

    total_amount = sum(float(b.get('total', 0)) for b in data)
    vencidas = [b for b in data if b.get('dueDate') and b['dueDate'] < datetime.now().strftime('%Y-%m-%d')]

    return {
        'bills': data,
        'total': len(data),
        'total_amount': round(total_amount, 2),
        'vencidas': len(vencidas),
        'monto_vencido': round(sum(float(b.get('total', 0)) for b in vencidas), 2),
    }
