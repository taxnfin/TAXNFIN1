"""CFDI AI categorization and operations routes"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging

from core.database import db
from core.auth import get_current_user
from services.audit import audit_log
from models.enums import UserRole

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/cfdi/{cfdi_id}/ai-categorize")
async def ai_categorize_single_cfdi(cfdi_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Use AI to suggest a category for a single CFDI"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get the CFDI
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0, 'xml_original': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    # Get available categories for this company (matching the CFDI type)
    categories = await db.categories.find({
        'company_id': company_id, 
        'activo': True,
        'tipo': cfdi.get('tipo_cfdi', 'egreso')
    }, {'_id': 0}).to_list(100)
    
    # Get subcategories for each category
    for cat in categories:
        subcats = await db.subcategories.find({'category_id': cat['id'], 'activo': True}, {'_id': 0}).to_list(100)
        cat['subcategorias'] = subcats
    
    if not categories:
        return {
            'success': False,
            'error': f'No hay categorías de tipo "{cfdi.get("tipo_cfdi", "egreso")}" disponibles',
            'suggestion': None
        }
    
    # Call AI service
    result = await categorize_cfdi_with_ai(cfdi, categories)
    
    return {
        'success': result.get('success', False),
        'cfdi_id': cfdi_id,
        'cfdi_uuid': cfdi.get('uuid'),
        'suggestion': {
            'category_id': result.get('category_id'),
            'subcategory_id': result.get('subcategory_id'),
            'confidence': result.get('confidence', 0),
            'reasoning': result.get('reasoning', '')
        },
        'error': result.get('error')
    }

@router.post("/cfdi/ai-categorize-batch")
async def ai_categorize_batch_cfdis(request: Request, current_user: Dict = Depends(get_current_user), apply_suggestions: bool = Query(False, description="Apply high-confidence suggestions automatically")):
    """Use AI to categorize all uncategorized CFDIs"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get uncategorized CFDIs
    uncategorized_cfdis = await db.cfdis.find({
        'company_id': company_id,
        '$or': [
            {'category_id': None},
            {'category_id': {'$exists': False}}
        ]
    }, {'_id': 0, 'xml_original': 0}).to_list(100)
    
    if not uncategorized_cfdis:
        return {
            'success': True,
            'message': 'No hay CFDIs sin categorizar',
            'processed': 0,
            'results': []
        }
    
    # Get all categories
    categories = await db.categories.find({'company_id': company_id, 'activo': True}, {'_id': 0}).to_list(100)
    for cat in categories:
        subcats = await db.subcategories.find({'category_id': cat['id'], 'activo': True}, {'_id': 0}).to_list(100)
        cat['subcategorias'] = subcats
    
    # Process each CFDI
    results = []
    applied_count = 0
    
    for cfdi in uncategorized_cfdis:
        # Filter categories by CFDI type
        matching_categories = [c for c in categories if c['tipo'] == cfdi.get('tipo_cfdi', 'egreso')]
        
        if not matching_categories:
            results.append({
                'cfdi_id': cfdi['id'],
                'cfdi_uuid': cfdi.get('uuid'),
                'success': False,
                'error': f'No hay categorías de tipo "{cfdi.get("tipo_cfdi", "egreso")}"'
            })
            continue
        
        result = await categorize_cfdi_with_ai(cfdi, matching_categories)
        
        # Apply suggestion if high confidence and apply_suggestions is True
        if apply_suggestions and result.get('success') and result.get('confidence', 0) >= 70:
            update_data = {}
            if result.get('category_id'):
                update_data['category_id'] = result['category_id']
            if result.get('subcategory_id'):
                update_data['subcategory_id'] = result['subcategory_id']
            
            if update_data:
                await db.cfdis.update_one({'id': cfdi['id']}, {'$set': update_data})
                await audit_log(company_id, 'CFDI', cfdi['id'], 'AI_CATEGORIZE', current_user['id'])
                result['applied'] = True
                applied_count += 1
            else:
                result['applied'] = False
        else:
            result['applied'] = False
        
        results.append({
            'cfdi_id': cfdi['id'],
            'cfdi_uuid': cfdi.get('uuid'),
            'emisor': cfdi.get('emisor_nombre', cfdi.get('emisor_rfc')),
            'total': cfdi.get('total'),
            **result
        })
    
    return {
        'success': True,
        'processed': len(uncategorized_cfdis),
        'applied': applied_count,
        'results': results
    }

# ===== CATEGORIZAR CFDI/TRANSACCIÓN =====
@router.put("/cfdi/{cfdi_id}/categorize")
async def categorize_cfdi(
    cfdi_id: str, 
    request: Request, 
    current_user: Dict = Depends(get_current_user), 
    category_id: str = None, 
    subcategory_id: str = None, 
    customer_id: str = None,
    vendor_id: str = None,
    etiquetas: List[str] = None
):
    company_id = await get_active_company_id(request, current_user)
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    update_data = {}
    if category_id:
        update_data['category_id'] = category_id
    if subcategory_id:
        update_data['subcategory_id'] = subcategory_id
    if customer_id:
        update_data['customer_id'] = customer_id
    if vendor_id:
        update_data['vendor_id'] = vendor_id
    if etiquetas is not None:
        update_data['etiquetas'] = etiquetas
    
    await db.cfdis.update_one({'id': cfdi_id}, {'$set': update_data})
    await audit_log(company_id, 'CFDI', cfdi_id, 'CATEGORIZE', current_user['id'])
    return {'status': 'success', 'message': 'CFDI categorizado'}

@router.put("/cfdi/{cfdi_id}/reconciliation-status")
async def update_cfdi_reconciliation(cfdi_id: str, status: str, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    if status not in ['pendiente', 'conciliado', 'no_conciliable']:
        raise HTTPException(status_code=400, detail="Estado inválido")
    
    await db.cfdis.update_one({'id': cfdi_id}, {'$set': {'estado_conciliacion': status}})
    await audit_log(company_id, 'CFDI', cfdi_id, 'UPDATE_RECONCILIATION', current_user['id'])
    return {'status': 'success', 'message': f'Estado actualizado a {status}'}

@router.put("/cfdi/{cfdi_id}/notes")
async def update_cfdi_notes(cfdi_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Update notes for a CFDI"""
    company_id = await get_active_company_id(request, current_user)
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    body = await request.json()
    notas = body.get('notas', '')
    
    await db.cfdis.update_one({'id': cfdi_id}, {'$set': {'notas': notas}})
    await audit_log(company_id, 'CFDI', cfdi_id, 'UPDATE_NOTES', current_user['id'])
    return {'status': 'success', 'message': 'Notas actualizadas'}

# ===== DIOT (Declaración Informativa de Operaciones con Terceros) =====
# ==================== DIOT PREVIEW & EXPORT MOVED TO routes/exports.py ====================

