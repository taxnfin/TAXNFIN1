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

from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
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
    Extract invoice data from PDF using Gemini AI
    """
    api_key = os.environ.get('EMERGENT_LLM_KEY')
    if not api_key:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY not configured")
    
    chat = LlmChat(
        api_key=api_key,
        session_id=f"invoice-extract-{uuid.uuid4()}",
        system_message="""Eres un experto en extracción de datos de facturas mexicanas (CFDI).
Tu tarea es extraer información estructurada de facturas en PDF.
Siempre responde en formato JSON válido con los campos solicitados.
Si un campo no está presente o no puedes identificarlo, usa null.
Para montos numéricos, usa solo números sin símbolos de moneda.
Para fechas, usa formato YYYY-MM-DD."""
    ).with_model("gemini", "gemini-2.5-flash")
    
    pdf_file = FileContentWithMimeType(
        file_path=file_path,
        mime_type="application/pdf"
    )
    
    extraction_prompt = f"""Extrae los siguientes datos de esta factura PDF y devuélvelos en formato JSON:

{{
    "emisor_nombre": "nombre del emisor/proveedor",
    "emisor_rfc": "RFC del emisor",
    "receptor_nombre": "nombre del receptor/cliente",
    "receptor_rfc": "RFC del receptor",
    "fecha": "fecha de emisión en formato YYYY-MM-DD",
    "folio": "número de folio de la factura",
    "folio_fiscal": "UUID/folio fiscal del CFDI",
    "concepto": "descripción breve del concepto principal",
    "subtotal": número sin símbolos,
    "iva": número del IVA sin símbolos,
    "total": número total sin símbolos,
    "moneda": "MXN o USD",
    "tipo_cambio": número del tipo de cambio (1 si es MXN),
    "metodo_pago": "PUE o PPD",
    "forma_pago": "descripción de la forma de pago",
    "uso_cfdi": "uso del CFDI",
    "tipo_comprobante": "Ingreso, Egreso, etc."
}}

IMPORTANTE: 
- Solo responde con el JSON, sin texto adicional
- El RFC de la empresa principal es: {company_rfc}
- Si el emisor_rfc coincide con {company_rfc}, es una factura de VENTA (cobranza)
- Si el receptor_rfc coincide con {company_rfc}, es una factura de COMPRA (pago a proveedor)"""

    user_message = UserMessage(
        text=extraction_prompt,
        file_contents=[pdf_file]
    )
    
    response = await chat.send_message(user_message)
    
    # Parse JSON response
    try:
        # Clean response - remove markdown code blocks if present
        clean_response = response.strip()
        if clean_response.startswith("```json"):
            clean_response = clean_response[7:]
        if clean_response.startswith("```"):
            clean_response = clean_response[3:]
        if clean_response.endswith("```"):
            clean_response = clean_response[:-3]
        clean_response = clean_response.strip()
        
        data = json.loads(clean_response)
        
        # Determine if it's a payment or collection based on RFC
        emisor_rfc = data.get('emisor_rfc', '').upper().strip()
        receptor_rfc = data.get('receptor_rfc', '').upper().strip()
        company_rfc_clean = company_rfc.upper().strip()
        
        # If company is the receptor, it's a payment (expense)
        # If company is the emisor, it's a collection (income)
        es_pago = receptor_rfc == company_rfc_clean
        
        return ExtractedInvoiceData(
            emisor_nombre=data.get('emisor_nombre'),
            emisor_rfc=emisor_rfc,
            receptor_nombre=data.get('receptor_nombre'),
            receptor_rfc=receptor_rfc,
            fecha=data.get('fecha'),
            folio=data.get('folio'),
            folio_fiscal=data.get('folio_fiscal'),
            concepto=data.get('concepto'),
            subtotal=float(data.get('subtotal', 0) or 0),
            iva=float(data.get('iva', 0) or 0),
            total=float(data.get('total', 0) or 0),
            moneda=data.get('moneda', 'MXN'),
            tipo_cambio=float(data.get('tipo_cambio', 1) or 1),
            metodo_pago=data.get('metodo_pago'),
            forma_pago=data.get('forma_pago'),
            uso_cfdi=data.get('uso_cfdi'),
            tipo_comprobante=data.get('tipo_comprobante'),
            es_pago=es_pago
        )
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {response}")
        raise HTTPException(status_code=500, detail=f"Error parsing invoice data: {str(e)}")


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
