"""FX Rates routes - Exchange rate management"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Dict, List, Optional
from datetime import datetime, timezone
import uuid
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id
from models.fx import FXRate, FXRateCreate
from services.audit import audit_log

router = APIRouter(prefix="/fx-rates")
logger = logging.getLogger(__name__)


@router.get("")
async def list_fx_rates(request: Request, current_user: Dict = Depends(get_current_user)):
    """List all FX rates, normalizing field names from both old and new formats"""
    company_id = await get_active_company_id(request, current_user)
    rates = await db.fx_rates.find({'company_id': company_id}, {'_id': 0}).sort('fecha_vigencia', -1).to_list(1000)
    
    normalized = []
    for r in rates:
        # Normalize field names (support both old and new formats)
        rate_obj = {
            'id': r.get('id', str(uuid.uuid4())),
            'company_id': r.get('company_id'),
            'moneda_base': r.get('moneda_base') or r.get('moneda_destino') or 'MXN',
            'moneda_cotizada': r.get('moneda_cotizada') or r.get('moneda_origen'),
            'tipo_cambio': r.get('tipo_cambio') or r.get('tasa') or 0,
            'fuente': r.get('fuente', 'manual'),
            'auto_sync': r.get('auto_sync', False),
            'fecha_vigencia': r.get('fecha_vigencia'),
            'created_at': r.get('created_at') or r.get('fecha_vigencia')
        }
        
        # Convert date strings to datetime
        for field in ['fecha_vigencia', 'created_at']:
            if isinstance(rate_obj.get(field), str):
                try:
                    rate_obj[field] = datetime.fromisoformat(rate_obj[field].replace('Z', '+00:00'))
                except:
                    pass
        
        normalized.append(rate_obj)
    
    return normalized


@router.post("", response_model=FXRate)
async def create_fx_rate(rate_data: FXRateCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    """Create a new FX rate"""
    company_id = await get_active_company_id(request, current_user)
    rate = FXRate(company_id=company_id, **rate_data.model_dump())
    doc = rate.model_dump()
    for field in ['fecha_vigencia', 'created_at']:
        doc[field] = doc[field].isoformat()
    await db.fx_rates.insert_one(doc)
    await audit_log(rate.company_id, 'FXRate', rate.id, 'CREATE', current_user['id'])
    return rate


@router.delete("/{rate_id}")
async def delete_fx_rate(rate_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Delete an FX rate"""
    company_id = await get_active_company_id(request, current_user)
    rate = await db.fx_rates.find_one({'id': rate_id, 'company_id': company_id}, {'_id': 0})
    if not rate:
        raise HTTPException(status_code=404, detail="Tipo de cambio no encontrado")
    await db.fx_rates.delete_one({'id': rate_id})
    await audit_log(company_id, 'FXRate', rate_id, 'DELETE', current_user['id'])
    return {'status': 'success', 'message': 'Tipo de cambio eliminado'}


@router.get("/latest")
async def get_latest_fx_rates(request: Request, current_user: Dict = Depends(get_current_user)):
    """Get the latest FX rates for each currency"""
    company_id = await get_active_company_id(request, current_user)
    
    # Aggregate to get the latest rate for each currency
    pipeline = [
        {'$match': {'company_id': company_id}},
        {'$sort': {'fecha_vigencia': -1}},
        {'$group': {
            '_id': {'$ifNull': ['$moneda_cotizada', '$moneda_origen']},
            'tipo_cambio': {'$first': {'$ifNull': ['$tipo_cambio', '$tasa']}},
            'fecha_vigencia': {'$first': '$fecha_vigencia'},
            'fuente': {'$first': '$fuente'},
            'id': {'$first': '$id'}
        }}
    ]
    
    results = await db.fx_rates.aggregate(pipeline).to_list(100)
    
    rates = {}
    for r in results:
        if r['_id']:
            rates[r['_id']] = {
                'moneda': r['_id'],
                'tipo_cambio': r['tipo_cambio'],
                'fecha_vigencia': r['fecha_vigencia'],
                'fuente': r.get('fuente', 'manual')
            }
    
    return rates


@router.get("/by-date")
async def get_fx_rate_by_date(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    moneda: str = Query(..., description="Currency code (e.g., USD, EUR)"),
    fecha: str = Query(..., description="Date in YYYY-MM-DD format")
):
    """Get the FX rate for a specific currency and date"""
    company_id = await get_active_company_id(request, current_user)
    
    # Find the rate closest to but not after the specified date
    rate = await db.fx_rates.find_one(
        {
            'company_id': company_id,
            '$or': [
                {'moneda_cotizada': moneda},
                {'moneda_origen': moneda}
            ],
            'fecha_vigencia': {'$lte': fecha + 'T23:59:59'}
        },
        {'_id': 0},
        sort=[('fecha_vigencia', -1)]
    )
    
    if not rate:
        # Try to find any rate for this currency
        rate = await db.fx_rates.find_one(
            {
                'company_id': company_id,
                '$or': [
                    {'moneda_cotizada': moneda},
                    {'moneda_origen': moneda}
                ]
            },
            {'_id': 0},
            sort=[('fecha_vigencia', -1)]
        )
    
    if not rate:
        # Return default rates
        default_rates = {'USD': 17.50, 'EUR': 19.00, 'MXN': 1.0}
        return {
            'moneda': moneda,
            'tipo_cambio': default_rates.get(moneda, 1.0),
            'fecha_vigencia': fecha,
            'fuente': 'default'
        }
    
    return {
        'moneda': moneda,
        'tipo_cambio': rate.get('tipo_cambio') or rate.get('tasa') or 1.0,
        'fecha_vigencia': rate.get('fecha_vigencia'),
        'fuente': rate.get('fuente', 'manual')
    }


@router.get("/first-of-month")
async def get_first_of_month_rate(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    moneda: str = Query(..., description="Currency code"),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None)
):
    """Get the FX rate for the first day of a month (for DIOT and reports)"""
    company_id = await get_active_company_id(request, current_user)
    
    # Default to current month if not specified
    now = datetime.now(timezone.utc)
    if not year:
        year = now.year
    if not month:
        month = now.month
    
    # Calculate first day of month
    first_day = datetime(year, month, 1, tzinfo=timezone.utc)
    first_day_str = first_day.strftime('%Y-%m-%d')
    
    # Find the rate for the first day or closest before
    rate = await db.fx_rates.find_one(
        {
            'company_id': company_id,
            '$or': [
                {'moneda_cotizada': moneda},
                {'moneda_origen': moneda}
            ],
            'fecha_vigencia': {'$lte': first_day_str + 'T23:59:59'}
        },
        {'_id': 0},
        sort=[('fecha_vigencia', -1)]
    )
    
    if not rate:
        # Return default
        default_rates = {'USD': 17.50, 'EUR': 19.00, 'MXN': 1.0}
        return {
            'moneda': moneda,
            'tipo_cambio': default_rates.get(moneda, 1.0),
            'fecha': first_day_str,
            'fuente': 'default'
        }
    
    return {
        'moneda': moneda,
        'tipo_cambio': rate.get('tipo_cambio') or rate.get('tasa') or 1.0,
        'fecha': first_day_str,
        'fuente': rate.get('fuente', 'manual')
    }


@router.get("/alerts")
async def get_fx_alerts(request: Request, current_user: Dict = Depends(get_current_user)):
    """Get FX rate alerts (significant changes, missing rates, etc.)"""
    company_id = await get_active_company_id(request, current_user)
    
    alerts = []
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    # Check for each currency
    for moneda in ['USD', 'EUR']:
        # Get latest rate
        latest = await db.fx_rates.find_one(
            {
                'company_id': company_id,
                '$or': [
                    {'moneda_cotizada': moneda},
                    {'moneda_origen': moneda}
                ]
            },
            {'_id': 0},
            sort=[('fecha_vigencia', -1)]
        )
        
        if not latest:
            alerts.append({
                'type': 'missing',
                'moneda': moneda,
                'message': f'No hay tipos de cambio registrados para {moneda}'
            })
            continue
        
        # Check if rate is outdated (more than 7 days old)
        fecha_str = latest.get('fecha_vigencia', '')
        if fecha_str:
            try:
                fecha = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
                days_old = (datetime.now(timezone.utc) - fecha).days
                if days_old > 7:
                    alerts.append({
                        'type': 'outdated',
                        'moneda': moneda,
                        'days_old': days_old,
                        'message': f'El tipo de cambio de {moneda} tiene {days_old} días de antigüedad'
                    })
            except:
                pass
    
    return {'alerts': alerts, 'count': len(alerts)}
