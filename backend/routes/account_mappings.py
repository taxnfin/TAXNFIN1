"""Account mapping routes - Configurable account-to-category mapping"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime, timezone
import uuid

from core.database import db
from core.auth import get_current_user
from models.enums import UserRole

router = APIRouter()

# Standard financial categories that TaxnFin uses
FINANCIAL_CATEGORIES = [
    {'key': 'ingresos', 'label': 'Ingresos / Ventas', 'group': 'income', 'description': 'Ingresos principales del negocio'},
    {'key': 'otros_ingresos', 'label': 'Otros Ingresos', 'group': 'income', 'description': 'Ingresos no operativos (intereses, ganancia cambiaria, etc.)'},
    {'key': 'costo_ventas', 'label': 'Costo de Ventas', 'group': 'cost', 'description': 'Costos directamente asociados a la producción/servicio'},
    {'key': 'gastos_venta', 'label': 'Gastos de Venta', 'group': 'opex', 'description': 'Comisiones, publicidad, envíos, promociones'},
    {'key': 'gastos_administracion', 'label': 'Gastos de Administración', 'group': 'opex', 'description': 'Sueldos admin, renta oficina, servicios, papelería'},
    {'key': 'gastos_generales', 'label': 'Gastos Generales', 'group': 'opex', 'description': 'Otros gastos operativos no clasificados'},
    {'key': 'gastos_financieros', 'label': 'Gastos Financieros', 'group': 'financial', 'description': 'Intereses, comisiones bancarias, pérdida cambiaria'},
    {'key': 'otros_gastos', 'label': 'Otros Gastos', 'group': 'other', 'description': 'Gastos no operativos extraordinarios'},
    {'key': 'impuestos', 'label': 'Impuestos', 'group': 'tax', 'description': 'ISR, IETU, impuestos por pagar'},
    {'key': 'depreciacion', 'label': 'Depreciación', 'group': 'non_cash', 'description': 'Depreciación de activos fijos'},
    {'key': 'amortizacion', 'label': 'Amortización', 'group': 'non_cash', 'description': 'Amortización de activos intangibles'},
]


class AccountMappingCreate(BaseModel):
    source_type: str        # 'category' (TaxnFin categories), 'account_code' (SAT code), 'account_name' (text match)
    source_id: Optional[str] = None   # category_id for type=category
    source_value: str       # category name, account code prefix, or text pattern
    target_category: str    # One of FINANCIAL_CATEGORIES keys
    integration: str        # 'alegra', 'contalink', 'all'


class AccountMappingUpdate(BaseModel):
    target_category: str


@router.get("/account-mappings/categories")
async def get_financial_categories(current_user: Dict = Depends(get_current_user)):
    """Get all standard financial statement categories for mapping"""
    return FINANCIAL_CATEGORIES


@router.get("/account-mappings")
async def get_account_mappings(current_user: Dict = Depends(get_current_user)):
    """Get all custom account mappings for the company"""
    mappings = await db.account_mappings.find(
        {'company_id': current_user['company_id']},
        {'_id': 0}
    ).to_list(200)
    return mappings


@router.post("/account-mappings")
async def create_account_mapping(data: AccountMappingCreate, current_user: Dict = Depends(get_current_user)):
    """Create a new account mapping"""
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    valid_targets = [c['key'] for c in FINANCIAL_CATEGORIES]
    if data.target_category not in valid_targets:
        raise HTTPException(status_code=400, detail=f"Categoría destino inválida: {data.target_category}")
    
    doc = {
        'id': str(uuid.uuid4()),
        'company_id': current_user['company_id'],
        'source_type': data.source_type,
        'source_id': data.source_id,
        'source_value': data.source_value,
        'target_category': data.target_category,
        'integration': data.integration,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'created_by': current_user['id'],
    }
    
    await db.account_mappings.insert_one(doc)
    del doc['_id']
    return doc


@router.put("/account-mappings/{mapping_id}")
async def update_account_mapping(mapping_id: str, data: AccountMappingUpdate, current_user: Dict = Depends(get_current_user)):
    """Update target category of a mapping"""
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    result = await db.account_mappings.update_one(
        {'id': mapping_id, 'company_id': current_user['company_id']},
        {'$set': {'target_category': data.target_category}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Mapeo no encontrado")
    return {'status': 'ok'}


@router.delete("/account-mappings/{mapping_id}")
async def delete_account_mapping(mapping_id: str, current_user: Dict = Depends(get_current_user)):
    """Delete an account mapping"""
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    result = await db.account_mappings.delete_one({
        'id': mapping_id,
        'company_id': current_user['company_id']
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Mapeo no encontrado")
    return {'status': 'ok'}


@router.post("/account-mappings/auto-detect")
async def auto_detect_mappings(current_user: Dict = Depends(get_current_user)):
    """Auto-detect and suggest mappings based on existing categories and their names"""
    company_id = current_user['company_id']
    
    categories = await db.categories.find(
        {'company_id': company_id},
        {'_id': 0}
    ).to_list(100)
    
    # Existing mappings
    existing = await db.account_mappings.find(
        {'company_id': company_id},
        {'_id': 0}
    ).to_list(200)
    existing_ids = {m['source_id'] for m in existing if m.get('source_id')}
    
    suggestions = []
    
    # Keyword-based suggestions
    keyword_map = {
        'costo_ventas': ['costo', 'mercancia', 'materia prima', 'produccion', 'inventario', 'manufactura'],
        'gastos_venta': ['venta', 'comision', 'publicidad', 'marketing', 'envio', 'flete', 'logistica'],
        'gastos_administracion': ['sueldo', 'nomina', 'renta', 'oficina', 'admin', 'servicio', 'papeleria', 'telefono', 'internet', 'software'],
        'gastos_financieros': ['banco', 'bancario', 'interes', 'comision bancaria', 'financiero', 'cambiaria'],
        'impuestos': ['impuesto', 'isr', 'iva', 'ietu', 'fiscal'],
        'ingresos': ['venta', 'ingreso', 'servicio prestado', 'honorario'],
        'otros_gastos': ['extraordinario', 'multa', 'donacion', 'siniestro'],
        'depreciacion': ['deprecia'],
    }
    
    for cat in categories:
        if cat['id'] in existing_ids:
            continue
        
        cat_name = cat.get('nombre', '').lower()
        cat_tipo = cat.get('tipo', '')
        suggested_target = None
        confidence = 0
        
        # If category is income type, always map to ingresos
        if cat_tipo == 'ingreso':
            suggested_target = 'ingresos'
            confidence = 0.9
        else:
            # Only check expense keywords for egreso categories
            for target, keywords in keyword_map.items():
                for kw in keywords:
                    if kw in cat_name:
                        suggested_target = target
                        confidence = 0.8 if len(kw) > 4 else 0.6
                        break
                if suggested_target:
                    break
        
        if not suggested_target:
            suggested_target = 'gastos_generales'
            confidence = 0.3
        
        suggestions.append({
            'source_id': cat['id'],
            'source_value': cat.get('nombre', ''),
            'source_type': 'category',
            'integration': 'alegra',
            'suggested_target': suggested_target,
            'confidence': confidence,
        })
    
    return suggestions
