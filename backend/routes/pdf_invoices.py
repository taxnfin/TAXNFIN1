"""
PDF Invoice Extraction Module
Extracts data from PDF invoices and creates payments/collections
"""
import os
import uuid
import json
import tempfile
import aiofiles
from datetime import datetime, timezone
from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Request
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from core.database import db
from core.auth import get_current_user, get_active_company_id

import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pdf-invoices", tags=["PDF Invoices"])


class ExtractedInvoiceData(BaseModel):
    """Extracted invoice data from PDF"""
    emisor_nombre: Optional[str] = None
    emisor_rfc: Optional[str] = None
    receptor_nombre: Optional[str] = None
    receptor_rfc: Optional[str] = None
    fecha: Optional[str] = None
    folio: Optional[str] = None
    folio_fiscal: Optional[str] = None
    concepto: Optional[str] = None
    subtotal: Optional[float] = None
    iva: Optional[float] = None
    total: Optional[float] = None
    moneda: Optional[str] = "MXN"
    tipo_cambio: Optional[float] = 1.0
    metodo_pago: Optional[str] = None
    forma_pago: Optional[str] = None
    uso_cfdi: Optional[str] = None
    tipo_comprobante: Optional[str] = None
    es_pago: Optional[bool] = None  # True if company is receptor (expense), False if emisor (income)


async def extract_invoice_data_from_pdf(file_path: str, company_rfc: str) -> ExtractedInvoiceData:
    """
    Extract invoice data from PDF.
    NOTE: AI extraction disabled — returns empty template.
    To enable, configure an LLM API key and implement PDF parsing.
    """
    raise HTTPException(
        status_code=501,
        detail="Extracción de PDF por IA deshabilitada. Configure una API key de LLM para habilitar esta función."
    )


@router.post("/extract")
async def extract_pdf_invoice(
    file: UploadFile = File(...),
    request: Request = None,
    current_user: Dict = Depends(get_current_user)
):
    """
    Extract data from a PDF invoice
    Returns extracted data for user confirmation before creating payment
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Get company RFC
    company = await db.companies.find_one({'id': company_id}, {'_id': 0, 'rfc': 1, 'nombre': 1})
    if not company or not company.get('rfc'):
        raise HTTPException(status_code=400, detail="Company RFC not configured")
    
    company_rfc = company['rfc']
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Save file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_path = tmp_file.name
    
    try:
        # Extract data
        extracted_data = await extract_invoice_data_from_pdf(tmp_path, company_rfc)
        
        # Check for duplicates by folio_fiscal (UUID)
        is_duplicate = False
        duplicate_message = None
        if extracted_data.folio_fiscal:
            # Check in CFDIs
            existing_cfdi = await db.cfdis.find_one({
                'company_id': company_id,
                '$or': [
                    {'uuid': extracted_data.folio_fiscal},
                    {'folio_fiscal': extracted_data.folio_fiscal}
                ]
            }, {'_id': 0, 'id': 1, 'emisor_nombre': 1, 'total': 1})
            
            if existing_cfdi:
                is_duplicate = True
                duplicate_message = f"Ya existe un CFDI con este folio fiscal ({extracted_data.folio_fiscal[:8]}...). Emisor: {existing_cfdi.get('emisor_nombre')}, Total: {existing_cfdi.get('total')}"
            
            # Also check in payments
            if not is_duplicate:
                existing_payment = await db.payments.find_one({
                    'company_id': company_id,
                    'pdf_folio_fiscal': extracted_data.folio_fiscal
                }, {'_id': 0, 'id': 1, 'beneficiario': 1, 'monto': 1})
                
                if existing_payment:
                    is_duplicate = True
                    duplicate_message = f"Ya existe un pago importado con este folio fiscal ({extracted_data.folio_fiscal[:8]}...). Beneficiario: {existing_payment.get('beneficiario')}, Monto: {existing_payment.get('monto')}"
        
        # Determine type description
        tipo_desc = "PAGO (Gasto/Compra)" if extracted_data.es_pago else "COBRANZA (Ingreso/Venta)"
        tercero = extracted_data.emisor_nombre if extracted_data.es_pago else extracted_data.receptor_nombre
        
        return {
            "success": True,
            "message": f"Factura extraída exitosamente - {tipo_desc}",
            "data": extracted_data.model_dump(),
            "tipo": "pago" if extracted_data.es_pago else "cobro",
            "tercero": tercero,
            "company_rfc": company_rfc,
            "is_duplicate": is_duplicate,
            "duplicate_message": duplicate_message
        }
    finally:
        # Clean up temp file
        os.unlink(tmp_path)


@router.post("/create-from-pdf")
async def create_payment_from_pdf(
    file: UploadFile = File(...),
    category_id: str = Form(None),
    subcategory_id: str = Form(None),
    bank_account_id: str = Form(None),
    notas: str = Form(None),
    request: Request = None,
    current_user: Dict = Depends(get_current_user)
):
    """
    Extract PDF and create payment/collection in one step
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Get company RFC
    company = await db.companies.find_one({'id': company_id}, {'_id': 0, 'rfc': 1, 'nombre': 1})
    if not company or not company.get('rfc'):
        raise HTTPException(status_code=400, detail="Company RFC not configured")
    
    company_rfc = company['rfc']
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Save file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_path = tmp_file.name
    
    try:
        # Extract data
        extracted_data = await extract_invoice_data_from_pdf(tmp_path, company_rfc)
        
        # Create payment document
        tipo_pago = "pago" if extracted_data.es_pago else "cobro"
        tercero = extracted_data.emisor_nombre if extracted_data.es_pago else extracted_data.receptor_nombre
        tercero_rfc = extracted_data.emisor_rfc if extracted_data.es_pago else extracted_data.receptor_rfc
        
        # Parse date
        fecha_str = extracted_data.fecha
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d') if fecha_str else datetime.now(timezone.utc)
        except:
            fecha = datetime.now(timezone.utc)
        
        payment_doc = {
            'id': str(uuid.uuid4()),
            'company_id': company_id,
            'bank_account_id': bank_account_id,
            'tipo': tipo_pago,
            'concepto': extracted_data.concepto or f"Factura {extracted_data.folio}",
            'monto': extracted_data.total,
            'moneda': extracted_data.moneda or 'MXN',
            'tipo_cambio': extracted_data.tipo_cambio or 1.0,
            'metodo_pago': 'transferencia',
            'fecha_vencimiento': fecha.isoformat(),
            'fecha_pago': None,  # Not paid yet
            'estatus': 'pendiente',
            'referencia': extracted_data.folio or '',
            'beneficiario': tercero,
            'beneficiario_rfc': tercero_rfc,
            'es_real': True,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'source': 'pdf_extraction',
            'category_id': category_id,
            'subcategory_id': subcategory_id,
            'notas': notas,
            # PDF invoice specific fields
            'pdf_folio': extracted_data.folio,
            'pdf_folio_fiscal': extracted_data.folio_fiscal,
            'pdf_emisor_nombre': extracted_data.emisor_nombre,
            'pdf_emisor_rfc': extracted_data.emisor_rfc,
            'pdf_receptor_nombre': extracted_data.receptor_nombre,
            'pdf_receptor_rfc': extracted_data.receptor_rfc,
            'pdf_subtotal': extracted_data.subtotal,
            'pdf_iva': extracted_data.iva,
            'pdf_metodo_pago': extracted_data.metodo_pago,
            'pdf_forma_pago': extracted_data.forma_pago,
        }
        
        await db.payments.insert_one(payment_doc)
        
        # Remove _id for response
        payment_doc.pop('_id', None)
        
        tipo_desc = "PAGO" if extracted_data.es_pago else "COBRANZA"
        
        return {
            "success": True,
            "message": f"{tipo_desc} creado exitosamente desde PDF",
            "payment": payment_doc,
            "tipo": tipo_pago,
            "tercero": tercero
        }
    finally:
        # Clean up temp file
        os.unlink(tmp_path)


@router.post("/confirm")
async def confirm_extracted_invoice(
    extracted_data: dict,
    category_id: str = None,
    subcategory_id: str = None,
    bank_account_id: str = None,
    notas: str = None,
    request: Request = None,
    current_user: Dict = Depends(get_current_user)
):
    """
    Confirm extracted data and create payment/collection
    Use this after /extract endpoint to confirm and save
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Determine type
    es_pago = extracted_data.get('es_pago', True)
    tipo_pago = "pago" if es_pago else "cobro"
    tercero = extracted_data.get('emisor_nombre') if es_pago else extracted_data.get('receptor_nombre')
    tercero_rfc = extracted_data.get('emisor_rfc') if es_pago else extracted_data.get('receptor_rfc')
    
    # Parse date
    fecha_str = extracted_data.get('fecha')
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d') if fecha_str else datetime.now(timezone.utc)
    except:
        fecha = datetime.now(timezone.utc)
    
    payment_doc = {
        'id': str(uuid.uuid4()),
        'company_id': company_id,
        'bank_account_id': bank_account_id,
        'tipo': tipo_pago,
        'concepto': extracted_data.get('concepto') or f"Factura {extracted_data.get('folio', '')}",
        'monto': float(extracted_data.get('total', 0) or 0),
        'moneda': extracted_data.get('moneda', 'MXN'),
        'tipo_cambio': float(extracted_data.get('tipo_cambio', 1) or 1),
        'metodo_pago': 'transferencia',
        'fecha_vencimiento': fecha.isoformat(),
        'fecha_pago': None,
        'estatus': 'pendiente',
        'referencia': extracted_data.get('folio', ''),
        'beneficiario': tercero,
        'beneficiario_rfc': tercero_rfc,
        'es_real': True,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'source': 'pdf_extraction',
        'category_id': category_id,
        'subcategory_id': subcategory_id,
        'notas': notas,
        # PDF invoice specific fields
        'pdf_folio': extracted_data.get('folio'),
        'pdf_folio_fiscal': extracted_data.get('folio_fiscal'),
        'pdf_emisor_nombre': extracted_data.get('emisor_nombre'),
        'pdf_emisor_rfc': extracted_data.get('emisor_rfc'),
        'pdf_receptor_nombre': extracted_data.get('receptor_nombre'),
        'pdf_receptor_rfc': extracted_data.get('receptor_rfc'),
        'pdf_subtotal': extracted_data.get('subtotal'),
        'pdf_iva': extracted_data.get('iva'),
        'pdf_metodo_pago': extracted_data.get('metodo_pago'),
        'pdf_forma_pago': extracted_data.get('forma_pago'),
    }
    
    await db.payments.insert_one(payment_doc)
    payment_doc.pop('_id', None)
    
    tipo_desc = "PAGO" if es_pago else "COBRANZA"
    
    return {
        "success": True,
        "message": f"{tipo_desc} creado exitosamente",
        "payment": payment_doc,
        "tipo": tipo_pago,
        "tercero": tercero
    }
