"""Category routes"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Dict, List, Optional
from datetime import datetime

from core.database import db
from core.auth import get_current_user, get_active_company_id
from models.category import Category, CategoryCreate, SubCategory, SubCategoryCreate
from services.audit import audit_log

router = APIRouter(prefix="/categories")


@router.post("", response_model=Category)
async def create_category(category_data: CategoryCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    """Create a new category"""
    company_id = await get_active_company_id(request, current_user)
    category = Category(company_id=company_id, **category_data.model_dump())
    doc = category.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.categories.insert_one(doc)
    await audit_log(category.company_id, 'Category', category.id, 'CREATE', current_user['id'])
    return category


@router.get("", response_model=List[dict])
async def list_categories(
    request: Request, 
    current_user: Dict = Depends(get_current_user),
    tipo: Optional[str] = Query(None, description="Filter by tipo: ingreso or egreso")
):
    """List all categories with their subcategories"""
    company_id = await get_active_company_id(request, current_user)
    
    query = {'company_id': company_id, 'activo': True}
    if tipo:
        query['tipo'] = tipo
    
    categories = await db.categories.find(query, {'_id': 0}).to_list(1000)
    
    # Get subcategories
    subcategories = await db.subcategories.find(
        {'company_id': company_id, 'activo': True}, 
        {'_id': 0}
    ).to_list(1000)
    
    # Map subcategories to categories
    subcats_by_category = {}
    for sc in subcategories:
        cat_id = sc.get('category_id')
        if cat_id not in subcats_by_category:
            subcats_by_category[cat_id] = []
        subcats_by_category[cat_id].append(sc)
    
    # Attach subcategories (using 'subcategorias' for frontend consistency)
    for cat in categories:
        cat['subcategorias'] = subcats_by_category.get(cat['id'], [])
        if isinstance(cat.get('created_at'), str):
            cat['created_at'] = datetime.fromisoformat(cat['created_at'])
    
    return categories


@router.put("/{category_id}")
async def update_category(category_id: str, category_data: CategoryCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    """Update a category"""
    company_id = await get_active_company_id(request, current_user)
    existing = await db.categories.find_one({'id': category_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    update_data = category_data.model_dump()
    await db.categories.update_one(
        {'id': category_id, 'company_id': company_id},
        {'$set': update_data}
    )
    await audit_log(company_id, 'Category', category_id, 'UPDATE', current_user['id'], existing, update_data)
    
    updated = await db.categories.find_one({'id': category_id}, {'_id': 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return updated


@router.delete("/{category_id}")
async def delete_category(category_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Delete (soft) a category"""
    company_id = await get_active_company_id(request, current_user)
    existing = await db.categories.find_one({'id': category_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    await db.categories.update_one(
        {'id': category_id},
        {'$set': {'activo': False}}
    )
    # Also deactivate subcategories
    await db.subcategories.update_many(
        {'category_id': category_id},
        {'$set': {'activo': False}}
    )
    await audit_log(company_id, 'Category', category_id, 'DELETE', current_user['id'])
    return {'status': 'success', 'message': 'Categoría eliminada'}


# Subcategory endpoints
@router.post("/subcategories", response_model=SubCategory)
async def create_subcategory(subcategory_data: SubCategoryCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    """Create a new subcategory"""
    company_id = await get_active_company_id(request, current_user)
    
    # Verify category exists
    category = await db.categories.find_one({'id': subcategory_data.category_id, 'company_id': company_id}, {'_id': 0})
    if not category:
        raise HTTPException(status_code=404, detail="Categoría padre no encontrada")
    
    subcategory = SubCategory(company_id=company_id, **subcategory_data.model_dump())
    doc = subcategory.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.subcategories.insert_one(doc)
    await audit_log(subcategory.company_id, 'SubCategory', subcategory.id, 'CREATE', current_user['id'])
    return subcategory


@router.delete("/subcategories/{subcategory_id}")
async def delete_subcategory(subcategory_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Delete (soft) a subcategory"""
    company_id = await get_active_company_id(request, current_user)
    existing = await db.subcategories.find_one({'id': subcategory_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Subcategoría no encontrada")
    
    await db.subcategories.update_one(
        {'id': subcategory_id},
        {'$set': {'activo': False}}
    )
    await audit_log(company_id, 'SubCategory', subcategory_id, 'DELETE', current_user['id'])
    return {'status': 'success', 'message': 'Subcategoría eliminada'}
