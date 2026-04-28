"""Projections week detail and subcategories routes"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import uuid
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id
from services.fx import get_fx_rate_by_date
from models.enums import UserRole
from models.category import SubCategory, SubCategoryCreate

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/projections/week-detail")
async def get_week_transactions_detail(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    week_start: str = Query(..., description="Start date of the week (YYYY-MM-DD)"),
    week_end: str = Query(..., description="End date of the week (YYYY-MM-DD)"),
    tipo: str = Query('ingreso', description="Type: 'ingreso' or 'egreso'")
):
    """
    Get detailed breakdown of all transactions that make up INGRESOS or EGRESOS for a specific week.
    This is used for auditing and reconciling the cash flow projection numbers.
    
    Returns:
    - cfdis: CFDIs within the week's date range
    - payments: Completed payments within the week
    - total_cfdi: Sum of CFDI amounts
    - total_payments: Sum of payment amounts
    - difference: The gap between payments and CFDIs (unmatched deposits/disbursements)
    """
    from datetime import datetime
    
    company_id = await get_active_company_id(request, current_user)
    
    # Get FX rates for conversion
    rates_docs = await db.fx_rates.find({'company_id': company_id}).sort('fecha_vigencia', -1).to_list(100)
    rates = {'MXN': 1.0, 'USD': 17.50, 'EUR': 19.00}
    for r in rates_docs:
        moneda = r.get('moneda_cotizada') or r.get('moneda_origen')
        tasa = r.get('tipo_cambio') or r.get('tasa')
        if moneda and tasa:
            rates[moneda] = tasa
    
    def convert_to_mxn(amount, currency):
        if not amount:
            return 0
        if currency == 'MXN' or not currency:
            return amount
        return amount * rates.get(currency, 1)
    
    # Get CFDIs for this week
    cfdi_tipo = 'ingreso' if tipo == 'ingreso' else 'egreso'
    cfdi_query = {
        'company_id': company_id,
        'tipo_cfdi': cfdi_tipo,
        'fecha_emision': {'$gte': week_start, '$lt': week_end + 'T23:59:59'}
    }
    cfdis = await db.cfdis.find(cfdi_query, {'_id': 0, 'xml_original': 0}).to_list(1000)
    
    # Get categories for names
    categories = await db.categories.find({'company_id': company_id}, {'_id': 0}).to_list(500)
    categories_map = {c['id']: c for c in categories}
    
    # Get subcategories
    subcategories = await db.subcategories.find({'company_id': company_id}, {'_id': 0}).to_list(500)
    subcategories_map = {s['id']: s for s in subcategories}
    
    # Process CFDIs
    cfdi_records = []
    total_cfdi_mxn = 0
    for cfdi in cfdis:
        monto_mxn = convert_to_mxn(cfdi.get('total', 0), cfdi.get('moneda', 'MXN'))
        total_cfdi_mxn += monto_mxn
        
        cat = categories_map.get(cfdi.get('category_id'), {})
        subcat = subcategories_map.get(cfdi.get('subcategory_id'), {})
        
        cfdi_records.append({
            'id': cfdi.get('id'),
            'uuid': cfdi.get('uuid'),
            'fecha': cfdi.get('fecha_emision'),
            'monto': cfdi.get('total'),
            'moneda': cfdi.get('moneda', 'MXN'),
            'monto_mxn': round(monto_mxn, 2),
            'origen': 'CFDI',
            'categoria': cat.get('nombre', 'Sin categoría'),
            'subcategoria': subcat.get('nombre', ''),
            'emisor': cfdi.get('emisor_nombre'),
            'receptor': cfdi.get('receptor_nombre')
        })
    
    # Get payments for this week
    payment_tipo = 'cobro' if tipo == 'ingreso' else 'pago'
    payment_query = {
        'company_id': company_id,
        'tipo': payment_tipo,
        'estatus': 'completado',
        '$or': [
            {'fecha_pago': {'$gte': week_start, '$lt': week_end + 'T23:59:59'}},
            {'fecha_vencimiento': {'$gte': week_start, '$lt': week_end + 'T23:59:59'}, 'fecha_pago': None}
        ]
    }
    payments = await db.payments.find(payment_query, {'_id': 0}).to_list(1000)
    
    # Process payments - track which have CFDI linkage
    payment_records = []
    total_payments_mxn = 0
    for p in payments:
        monto_mxn = convert_to_mxn(p.get('monto', 0), p.get('moneda', 'MXN'))
        total_payments_mxn += monto_mxn
        
        # Determine origin
        origen = 'Banco' if p.get('bank_transaction_id') else ('CFDI' if p.get('cfdi_id') else 'Manual')
        
        cat = categories_map.get(p.get('category_id'), {})
        subcat = subcategories_map.get(p.get('subcategory_id'), {})
        
        payment_records.append({
            'id': p.get('id'),
            'fecha': p.get('fecha_pago') or p.get('fecha_vencimiento'),
            'monto': p.get('monto'),
            'moneda': p.get('moneda', 'MXN'),
            'monto_mxn': round(monto_mxn, 2),
            'origen': origen,
            'categoria': cat.get('nombre', p.get('concepto', 'Sin categoría')),
            'subcategoria': subcat.get('nombre', ''),
            'beneficiario': p.get('beneficiario', ''),
            'referencia': p.get('referencia', ''),
            'cfdi_id': p.get('cfdi_id'),
            'bank_transaction_id': p.get('bank_transaction_id')
        })
    
    # Calculate difference (unmatched transactions)
    difference = total_payments_mxn - total_cfdi_mxn
    
    return {
        'week_start': week_start,
        'week_end': week_end,
        'tipo': tipo,
        'cfdis': cfdi_records,
        'payments': payment_records,
        'totals': {
            'cfdi_count': len(cfdi_records),
            'cfdi_total_mxn': round(total_cfdi_mxn, 2),
            'payment_count': len(payment_records),
            'payment_total_mxn': round(total_payments_mxn, 2),
            'difference_mxn': round(difference, 2),
            'note': 'Diferencia positiva = Cobros sin CFDI; Negativa = CFDIs sin cobro registrado'
        }
    }

# ===== SUBCATEGORIES ENDPOINTS (for frontend compatibility) =====
@router.post("/subcategories")
async def create_subcategory_direct(request: Request, current_user: Dict = Depends(get_current_user)):
    """Create a new subcategory"""
    company_id = await get_active_company_id(request, current_user)
    data = await request.json()
    
    # Validate category exists
    category = await db.categories.find_one({'id': data.get('category_id'), 'company_id': company_id}, {'_id': 0})
    if not category:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    subcategory_doc = {
        'id': str(uuid.uuid4()),
        'company_id': company_id,
        'category_id': data.get('category_id'),
        'nombre': data.get('nombre'),
        'descripcion': data.get('descripcion', ''),
        'activo': True,
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    await db.subcategories.insert_one(subcategory_doc)
    
    return {
        'id': subcategory_doc['id'],
        'nombre': subcategory_doc['nombre'],
        'category_id': subcategory_doc['category_id'],
        'activo': True
    }

@router.delete("/subcategories/{subcategory_id}")
async def delete_subcategory_direct(subcategory_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Delete a subcategory (soft delete)"""
    company_id = await get_active_company_id(request, current_user)
    
    result = await db.subcategories.update_one(
        {'id': subcategory_id, 'company_id': company_id},
        {'$set': {'activo': False}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Subcategoría no encontrada")
    
    return {'status': 'success', 'message': 'Subcategoría eliminada'}

