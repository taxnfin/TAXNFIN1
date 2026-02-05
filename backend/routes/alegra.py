"""
Alegra Integration Module
Syncs customers, vendors, invoices, bills, and payments with Alegra accounting software
for cash flow management purposes.
"""
import os
import base64
import uuid
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, Query
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
    
    # Process and save invoices as payments (cobros pendientes)
    created = 0
    updated = 0
    skipped = 0
    errors = 0
    
    for invoice in all_invoices:
        try:
            alegra_id = str(invoice.get('id'))
            
            # Get client info
            client = invoice.get('client', {})
            client_name = ""
            if isinstance(client, dict):
                name_obj = client.get('name', {})
                if isinstance(name_obj, dict):
                    client_name = name_obj.get('fullName') or f"{name_obj.get('firstName', '')} {name_obj.get('lastName', '')}".strip()
                else:
                    client_name = str(name_obj) if name_obj else ''
            
            # Calculate balance
            total = float(invoice.get('total', 0) or 0)
            total_paid = float(invoice.get('totalPaid', 0) or 0)
            balance = float(invoice.get('balance', total - total_paid) or 0)
            
            # Determine status
            inv_status = invoice.get('status', 'open')
            if balance <= 0:
                payment_status = 'completado'
            elif total_paid > 0:
                payment_status = 'parcial'
            else:
                payment_status = 'pendiente'
            
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
            
            # Apply date filter logic:
            # - For PAID invoices (completado): filter by payment date
            # - For PENDING invoices: filter by due date
            if date_from or date_to:
                should_include = False
                
                if payment_status == 'completado' and fecha_pago:
                    # Paid invoice: check if payment date is in range
                    if date_from and date_to:
                        should_include = date_from <= fecha_pago[:10] <= date_to
                    elif date_from:
                        should_include = fecha_pago[:10] >= date_from
                    elif date_to:
                        should_include = fecha_pago[:10] <= date_to
                else:
                    # Pending/Partial invoice: check if due date is in range
                    if fecha_vencimiento:
                        if date_from and date_to:
                            should_include = date_from <= fecha_vencimiento[:10] <= date_to
                        elif date_from:
                            should_include = fecha_vencimiento[:10] >= date_from
                        elif date_to:
                            should_include = fecha_vencimiento[:10] <= date_to
                
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
            
            payment_doc = {
                'alegra_id': alegra_id,
                'alegra_type': 'invoice',
                'company_id': company_id,
                'tipo': 'cobro',
                'concepto': f"Factura {invoice.get('numberTemplate', {}).get('prefix', '')}{invoice.get('number', alegra_id)}",
                'monto': total,
                'monto_pagado': total_paid,
                'saldo_pendiente': balance,
                'moneda': moneda,
                'tipo_cambio_historico': tipo_cambio if moneda != 'MXN' else None,
                'metodo_pago': 'transferencia',
                'fecha_vencimiento': fecha_vencimiento,
                'fecha_pago': None if payment_status != 'completado' else fecha,
                'estatus': payment_status,
                'referencia': f"{invoice.get('numberTemplate', {}).get('prefix', '')}{invoice.get('number', '')}",
                'beneficiario': client_name,
                'es_real': True,
                'source': 'alegra',
                'alegra_status': inv_status,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Check if exists
            existing = await db.payments.find_one({'company_id': company_id, 'alegra_id': alegra_id, 'alegra_type': 'invoice'})
            if existing:
                await db.payments.update_one({'_id': existing['_id']}, {'$set': payment_doc})
                updated += 1
            else:
                payment_doc['id'] = str(uuid.uuid4())
                payment_doc['created_at'] = datetime.now(timezone.utc).isoformat()
                await db.payments.insert_one(payment_doc)
                created += 1
                
        except Exception as e:
            logger.error(f"Error syncing invoice {invoice.get('id')}: {str(e)}")
            errors += 1
    
    return {
        "success": True,
        "message": f"Facturas de venta (CxC) sincronizadas desde Alegra",
        "stats": {
            "total": len(all_invoices),
            "created": created,
            "updated": updated,
            "skipped": skipped,
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
    
    # Process and save bills as payments (pagos pendientes)
    created = 0
    updated = 0
    skipped = 0
    errors = 0
    
    for bill in all_bills:
        try:
            alegra_id = str(bill.get('id'))
            
            # Get vendor info
            vendor = bill.get('provider', {})
            vendor_name = ""
            if isinstance(vendor, dict):
                name_obj = vendor.get('name', {})
                if isinstance(name_obj, dict):
                    vendor_name = name_obj.get('fullName') or f"{name_obj.get('firstName', '')} {name_obj.get('lastName', '')}".strip()
                else:
                    vendor_name = str(name_obj) if name_obj else ''
            
            # Calculate balance
            total = float(bill.get('total', 0) or 0)
            total_paid = float(bill.get('totalPaid', 0) or 0)
            balance = float(bill.get('balance', total - total_paid) or 0)
            
            # Determine status
            bill_status = bill.get('status', 'open')
            if balance <= 0:
                payment_status = 'completado'
            elif total_paid > 0:
                payment_status = 'parcial'
            else:
                payment_status = 'pendiente'
            
            # Parse dates
            fecha = bill.get('date', '')
            fecha_vencimiento = bill.get('dueDate', fecha)
            
            # Extract currency and exchange rate
            currency_data = bill.get('currency', {})
            moneda = currency_data.get('code', 'MXN') if isinstance(currency_data, dict) else 'MXN'
            tipo_cambio = float(currency_data.get('exchangeRate', 1) or 1) if isinstance(currency_data, dict) else 1
            
            # Save exchange rate to fx_rates if not MXN and rate is not 1
            if moneda != 'MXN' and tipo_cambio and tipo_cambio != 1:
                await save_alegra_exchange_rate(company_id, moneda, tipo_cambio, fecha)
            
            payment_doc = {
                'alegra_id': alegra_id,
                'alegra_type': 'bill',
                'company_id': company_id,
                'tipo': 'pago',
                'concepto': f"Factura proveedor {bill.get('numberTemplate', {}).get('prefix', '')}{bill.get('number', alegra_id)}",
                'monto': total,
                'monto_pagado': total_paid,
                'saldo_pendiente': balance,
                'moneda': moneda,
                'tipo_cambio_historico': tipo_cambio if moneda != 'MXN' else None,
                'metodo_pago': 'transferencia',
                'fecha_vencimiento': fecha_vencimiento,
                'fecha_pago': None if payment_status != 'completado' else fecha,
                'estatus': payment_status,
                'referencia': f"{bill.get('numberTemplate', {}).get('prefix', '')}{bill.get('number', '')}",
                'beneficiario': vendor_name,
                'es_real': True,
                'source': 'alegra',
                'alegra_status': bill_status,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Check if exists
            existing = await db.payments.find_one({'company_id': company_id, 'alegra_id': alegra_id, 'alegra_type': 'bill'})
            if existing:
                await db.payments.update_one({'_id': existing['_id']}, {'$set': payment_doc})
                updated += 1
            else:
                payment_doc['id'] = str(uuid.uuid4())
                payment_doc['created_at'] = datetime.now(timezone.utc).isoformat()
                await db.payments.insert_one(payment_doc)
                created += 1
                
        except Exception as e:
            logger.error(f"Error syncing bill {bill.get('id')}: {str(e)}")
            errors += 1
    
    return {
        "success": True,
        "message": f"Facturas de proveedor (CxP) sincronizadas desde Alegra",
        "stats": {
            "total": len(all_bills),
            "created": created,
            "updated": updated,
            "skipped": skipped,
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
    Sync payment receipts from Alegra
    These are actual payments received or made
    """
    company_id = await get_active_company_id(request, current_user)
    company = await db.companies.find_one({'id': company_id}, {'_id': 0})
    
    if not company.get('alegra_connected'):
        raise HTTPException(status_code=400, detail="Alegra no está conectado")
    
    email = company.get('alegra_email')
    token = company.get('alegra_token')
    
    # Fetch payments from Alegra (bank-accounts endpoint)
    # Alegra uses /bank-accounts for payment movements
    all_payments = []
    
    try:
        # Get bank accounts first
        bank_accounts = await alegra_request("GET", "bank-accounts", email, token)
        
        # For each bank account, get movements
        for account in bank_accounts:
            account_id = account.get('id')
            start = 0
            limit = 100
            
            while True:
                params = {"start": start, "limit": limit}
                try:
                    # Get movements for this account
                    movements = await alegra_request("GET", f"bank-accounts/{account_id}/bank-movements", email, token, params=params)
                    
                    if not movements or len(movements) == 0:
                        break
                    
                    for mov in movements:
                        mov['bank_account_name'] = account.get('name', '')
                        mov['bank_account_id'] = account_id
                    
                    all_payments.extend(movements)
                    
                    if len(movements) < limit:
                        break
                    
                    start += limit
                except:
                    break
    except Exception as e:
        logger.error(f"Error fetching payments: {str(e)}")
    
    # Process bank movements
    created = 0
    updated = 0
    errors = 0
    
    for payment in all_payments:
        try:
            alegra_id = str(payment.get('id'))
            
            # Determine type based on amount sign or type
            amount = float(payment.get('amount', 0) or 0)
            tipo = 'cobro' if amount > 0 else 'pago'
            
            payment_doc = {
                'alegra_id': alegra_id,
                'alegra_type': 'bank_movement',
                'company_id': company_id,
                'tipo': tipo,
                'concepto': payment.get('description', '') or payment.get('observations', '') or f"Movimiento bancario {alegra_id}",
                'monto': abs(amount),
                'moneda': 'MXN',
                'metodo_pago': 'transferencia',
                'fecha_vencimiento': payment.get('date', ''),
                'fecha_pago': payment.get('date', ''),
                'estatus': 'completado',
                'referencia': payment.get('reference', ''),
                'beneficiario': payment.get('contact', {}).get('name', '') if isinstance(payment.get('contact'), dict) else '',
                'es_real': True,
                'source': 'alegra',
                'alegra_bank_account': payment.get('bank_account_name'),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Check if exists
            existing = await db.payments.find_one({'company_id': company_id, 'alegra_id': alegra_id, 'alegra_type': 'bank_movement'})
            if existing:
                await db.payments.update_one({'_id': existing['_id']}, {'$set': payment_doc})
                updated += 1
            else:
                payment_doc['id'] = str(uuid.uuid4())
                payment_doc['created_at'] = datetime.now(timezone.utc).isoformat()
                await db.payments.insert_one(payment_doc)
                created += 1
                
        except Exception as e:
            logger.error(f"Error syncing payment {payment.get('id')}: {str(e)}")
            errors += 1
    
    return {
        "success": True,
        "message": f"Movimientos bancarios sincronizados desde Alegra",
        "stats": {
            "total": len(all_payments),
            "created": created,
            "updated": updated,
            "errors": errors
        }
    }


@router.post("/sync/all")
async def sync_all_alegra_data(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    date_from: str = Query(None, description="Date from (YYYY-MM-DD)"),
    date_to: str = Query(None, description="Date to (YYYY-MM-DD)")
):
    """
    Sync all data from Alegra: contacts, invoices, bills, and payments
    With optional date range filtering
    """
    company_id = await get_active_company_id(request, current_user)
    company = await db.companies.find_one({'id': company_id}, {'_id': 0})
    
    if not company.get('alegra_connected'):
        raise HTTPException(status_code=400, detail="Alegra no está conectado")
    
    results = {}
    
    # Sync contacts
    try:
        contacts_result = await sync_alegra_contacts(request, current_user, "all")
        results['contacts'] = contacts_result.get('stats', {})
    except Exception as e:
        results['contacts'] = {'error': str(e)}
    
    # Sync invoices (CxC) with date filters
    try:
        invoices_result = await sync_alegra_invoices(request, current_user, "all", date_from, date_to)
        results['invoices'] = invoices_result.get('stats', {})
    except Exception as e:
        results['invoices'] = {'error': str(e)}
    
    # Sync bills (CxP) with date filters
    try:
        bills_result = await sync_alegra_bills(request, current_user, "all", date_from, date_to)
        results['bills'] = bills_result.get('stats', {})
    except Exception as e:
        results['bills'] = {'error': str(e)}
    
    # Sync bank movements with date filters
    try:
        payments_result = await sync_alegra_payments(request, current_user, date_from, date_to)
        results['payments'] = payments_result.get('stats', {})
    except Exception as e:
        results['payments'] = {'error': str(e)}
    
    # Update last sync time
    await db.companies.update_one(
        {'id': company_id},
        {'$set': {'alegra_last_sync': datetime.now(timezone.utc).isoformat()}}
    )
    
    return {
        "success": True,
        "message": "Sincronización completa con Alegra",
        "results": results
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
    clear_payments: bool = Query(True, description="Clear payments from Alegra")
):
    """
    Clear all data synced from Alegra for the active company
    This allows re-syncing from scratch
    """
    company_id = await get_active_company_id(request, current_user)
    
    results = {
        "customers_deleted": 0,
        "vendors_deleted": 0,
        "payments_deleted": 0
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
    
    # Reset last sync time
    await db.companies.update_one(
        {'id': company_id},
        {'$set': {'alegra_last_sync': None}}
    )
    
    total_deleted = results['customers_deleted'] + results['vendors_deleted'] + results['payments_deleted']
    
    return {
        "success": True,
        "message": f"Se eliminaron {total_deleted} registros de Alegra",
        "results": results
    }
