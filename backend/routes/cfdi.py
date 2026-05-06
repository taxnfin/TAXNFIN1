"""CFDI routes - Electronic invoice management"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id
from models.cfdi import CFDI
from services.audit import audit_log

router = APIRouter(prefix="/cfdi")
logger = logging.getLogger(__name__)


@router.get("/summary")
async def get_cfdi_summary(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    moneda_vista: str = Query('MXN', description="Moneda para mostrar totales"),
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None
):
    """Get summary of CFDIs by type and status with currency conversion"""
    company_id = await get_active_company_id(request, current_user)
    
    query = {'company_id': company_id}
    if fecha_desde or fecha_hasta:
        query['fecha_emision'] = {}
        if fecha_desde:
            query['fecha_emision']['$gte'] = fecha_desde
        if fecha_hasta:
            query['fecha_emision']['$lte'] = fecha_hasta + 'T23:59:59'
    
    # Get all CFDIs
    cfdis = await db.cfdis.find(query, {'_id': 0, 'xml_original': 0}).to_list(10000)
    
    # Get company's base currency
    company = await db.companies.find_one({'id': company_id}, {'_id': 0, 'moneda_base': 1})
    moneda_base = company.get('moneda_base', 'MXN') if company else 'MXN'
    
    # Get FX rates
    rates_docs = await db.fx_rates.find({'company_id': company_id}).sort('fecha_vigencia', -1).to_list(100)
    rates = {'MXN': 1.0, 'USD': 17.50, 'EUR': 19.00}  # Defaults
    for r in rates_docs:
        moneda = r.get('moneda_cotizada') or r.get('moneda_origen')
        tasa = r.get('tipo_cambio') or r.get('tasa')
        if moneda and tasa:
            rates[moneda] = tasa
    
    # Calculate totals by currency and converted
    totals_by_currency = {'ingresos': {}, 'egresos': {}}
    totals_converted = {'ingresos': 0.0, 'egresos': 0.0}
    pendientes = 0
    conciliados = 0
    
    for c in cfdis:
        # Usar saldo pendiente real (total - lo ya cobrado/pagado)
        total_original = c.get('total', 0) or 0
        if c.get('tipo_cfdi') == 'ingreso':
            ya_cobrado = c.get('monto_cobrado', 0) or 0
            total = max(0, total_original - ya_cobrado)
        else:
            ya_pagado = c.get('monto_pagado', 0) or 0
            total = max(0, total_original - ya_pagado)
        
        # Omitir CFDIs sin saldo pendiente
        if total <= 0.01:
            continue
            
        moneda = c.get('moneda', 'MXN') or 'MXN'
        tipo = 'ingresos' if c.get('tipo_cfdi') == 'ingreso' else 'egresos'
        
        # Sum by ORIGINAL currency (pendiente real)
        if moneda not in totals_by_currency[tipo]:
            totals_by_currency[tipo][moneda] = 0
        totals_by_currency[tipo][moneda] += total
        
        # Convert to view currency.
        # 1) Prefer the precomputed `total_mxn` (written by Alegra sync) when
        #    converting to MXN — uses the exact rate at the time of issuance
        #    rather than the latest cached rate.
        # 2) Fallback: derive from the row's `tipo_cambio`.
        # 3) Last resort: use the company-level rates table.
        cfdi_tc = c.get('tipo_cambio') or 0
        # No usar precomputed_mxn ya que es el total completo, no el pendiente
        # Calcular MXN del pendiente usando el tipo de cambio de la factura
        
        if moneda == moneda_vista:
            totals_converted[tipo] += total
        elif moneda_vista == 'MXN' and moneda != 'MXN' and cfdi_tc and cfdi_tc > 0:
            totals_converted[tipo] += total * cfdi_tc
        elif moneda_vista == 'MXN' and moneda == 'MXN':
            totals_converted[tipo] += total
        elif moneda != 'MXN' and cfdi_tc and cfdi_tc > 0:
            # foreign -> view currency, going via MXN with the row's own rate
            in_mxn = total * cfdi_tc
            if moneda_vista == 'MXN':
                totals_converted[tipo] += in_mxn
            elif moneda_vista in rates and rates[moneda_vista]:
                totals_converted[tipo] += in_mxn / rates[moneda_vista]
            else:
                totals_converted[tipo] += in_mxn
        elif moneda in rates and moneda_vista in rates:
            # MXN -> foreign, or fallback to company-level rates table
            if moneda == 'MXN':
                converted = total / rates.get(moneda_vista, 1)
            elif moneda_vista == 'MXN':
                converted = total * rates.get(moneda, 1)
            else:
                to_mxn = total * rates.get(moneda, 1)
                converted = to_mxn / rates.get(moneda_vista, 1)
            totals_converted[tipo] += converted
        else:
            totals_converted[tipo] += total
        
        # Count reconciliation status
        if c.get('estado_conciliacion') == 'conciliado':
            conciliados += 1
        else:
            pendientes += 1
    
    return {
        'moneda_vista': moneda_vista,
        'moneda_base': moneda_base,
        'totales_por_moneda': totals_by_currency,
        'totales_convertidos': {
            'ingresos': round(totals_converted['ingresos'], 2),
            'egresos': round(totals_converted['egresos'], 2)
        },
        'balance_convertido': round(totals_converted['ingresos'] - totals_converted['egresos'], 2),
        'tipos_cambio_usados': rates,
        'total_cfdis': len(cfdis),
        'conciliados': conciliados,
        'pendientes': pendientes,
        'porcentaje_conciliado': round(conciliados / len(cfdis) * 100, 1) if cfdis else 0
    }


@router.get("", response_model=List[CFDI])
async def list_cfdis(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    limit: int = Query(100, le=1000),
    skip: int = Query(0, ge=0)
):
    """List all CFDIs for the current company"""
    company_id = await get_active_company_id(request, current_user)
    
    cfdis = await db.cfdis.find(
        {'company_id': company_id},
        {'_id': 0, 'xml_original': 0}
    ).sort('fecha_emision', -1).skip(skip).limit(limit).to_list(limit)
    
    for c in cfdis:
        for field in ['fecha_emision', 'fecha_timbrado', 'created_at']:
            if isinstance(c.get(field), str):
                c[field] = datetime.fromisoformat(c[field])
    return cfdis


@router.get("/{cfdi_id}")
async def get_cfdi(cfdi_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Get a single CFDI by ID"""
    company_id = await get_active_company_id(request, current_user)
    
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    for field in ['fecha_emision', 'fecha_timbrado', 'created_at']:
        if isinstance(cfdi.get(field), str):
            cfdi[field] = datetime.fromisoformat(cfdi[field])
    
    return cfdi


@router.get("/{cfdi_id}/payment-history")
async def get_cfdi_payment_history(cfdi_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Get payment history for a CFDI including all partial payments with bank transaction details"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get the CFDI first
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    # Get all reconciliations for this CFDI
    reconciliations = await db.reconciliations.find(
        {'cfdi_id': cfdi_id, 'company_id': company_id},
        {'_id': 0}
    ).to_list(100)
    
    # Get all payments for this CFDI
    payments = await db.payments.find(
        {'cfdi_id': cfdi_id, 'company_id': company_id},
        {'_id': 0}
    ).to_list(100)
    
    # Build payment history with bank transaction details
    payment_history = []
    
    for payment in payments:
        # Get the associated bank transaction
        bank_txn = None
        if payment.get('bank_transaction_id'):
            bank_txn = await db.bank_transactions.find_one(
                {'id': payment['bank_transaction_id'], 'company_id': company_id},
                {'_id': 0, 'descripcion': 1, 'referencia': 1, 'fecha_movimiento': 1, 'fecha_valor': 1, 'monto': 1, 'moneda': 1}
            )
        
        # Get the bank account info
        bank_account = None
        if payment.get('bank_account_id'):
            bank_account = await db.bank_accounts.find_one(
                {'id': payment['bank_account_id'], 'company_id': company_id},
                {'_id': 0, 'banco': 1, 'nombre': 1, 'moneda': 1}
            )
        
        history_entry = {
            'id': payment['id'],
            'fecha': payment.get('fecha_pago') or payment.get('created_at'),
            'monto': payment.get('monto', 0),
            'moneda': payment.get('moneda', 'MXN'),
            'concepto': payment.get('concepto', ''),
            'tipo': payment.get('tipo', 'pago'),
            'estatus': payment.get('estatus', 'completado'),
            'referencia_bancaria': bank_txn.get('referencia') if bank_txn else None,
            'descripcion_bancaria': bank_txn.get('descripcion') if bank_txn else None,
            'fecha_movimiento_banco': bank_txn.get('fecha_movimiento') if bank_txn else None,
            'banco': bank_account.get('banco') if bank_account else None,
            'cuenta': bank_account.get('nombre') if bank_account else None,
            'bank_transaction_id': payment.get('bank_transaction_id')
        }
        payment_history.append(history_entry)
    
    # Sort by date descending
    payment_history.sort(key=lambda x: x['fecha'] if x['fecha'] else '', reverse=True)
    
    # Calculate summary
    total_pagado = sum(p['monto'] for p in payment_history if p['estatus'] == 'completado')
    cfdi_total = cfdi.get('total', 0)
    saldo_pendiente = max(0, cfdi_total - total_pagado)
    
    return {
        'cfdi_id': cfdi_id,
        'cfdi_uuid': cfdi.get('uuid'),
        'cfdi_total': cfdi_total,
        'cfdi_moneda': cfdi.get('moneda', 'MXN'),
        'emisor_nombre': cfdi.get('emisor_nombre'),
        'receptor_nombre': cfdi.get('receptor_nombre'),
        'tipo_cfdi': cfdi.get('tipo_cfdi'),
        'fecha_emision': cfdi.get('fecha_emision'),
        'total_pagado': total_pagado,
        'saldo_pendiente': saldo_pendiente,
        'porcentaje_pagado': (total_pagado / cfdi_total * 100) if cfdi_total > 0 else 0,
        'estado_pago': 'pagado' if saldo_pendiente < 0.01 else ('parcial' if total_pagado > 0 else 'pendiente'),
        'pagos': payment_history,
        'total_pagos': len(payment_history)
    }


@router.delete("/bulk-delete")
async def bulk_delete_cfdis(
    request: Request, 
    current_user: Dict = Depends(get_current_user),
    category_id: Optional[str] = Query(None, description="Filter by category"),
    estado_conciliacion: Optional[str] = Query(None, description="Filter by reconciliation status"),
    fecha_desde: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    fecha_hasta: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    emisor: Optional[str] = Query(None, description="Filter by emisor name/RFC"),
    receptor: Optional[str] = Query(None, description="Filter by receptor name/RFC")
):
    """Delete multiple CFDIs based on filters"""
    company_id = await get_active_company_id(request, current_user)
    
    # Build query filter
    query = {'company_id': company_id}
    
    if category_id:
        query['category_id'] = category_id
    
    if estado_conciliacion:
        query['estado_conciliacion'] = estado_conciliacion
    
    if fecha_desde:
        query['fecha_emision'] = {'$gte': fecha_desde}
    
    if fecha_hasta:
        if 'fecha_emision' in query:
            query['fecha_emision']['$lte'] = fecha_hasta + 'T23:59:59'
        else:
            query['fecha_emision'] = {'$lte': fecha_hasta + 'T23:59:59'}
    
    if emisor:
        query['$or'] = query.get('$or', [])
        query['$or'].extend([
            {'emisor_nombre': {'$regex': emisor, '$options': 'i'}},
            {'emisor_rfc': {'$regex': emisor, '$options': 'i'}}
        ])
    
    if receptor:
        if '$or' not in query:
            query['$or'] = []
        query['$or'].extend([
            {'receptor_nombre': {'$regex': receptor, '$options': 'i'}},
            {'receptor_rfc': {'$regex': receptor, '$options': 'i'}}
        ])
    
    # Get CFDIs to delete
    cfdis_to_delete = await db.cfdis.find(query, {'id': 1, '_id': 0}).to_list(10000)
    cfdi_ids = [c['id'] for c in cfdis_to_delete]
    
    if not cfdi_ids:
        return {'status': 'success', 'message': 'No hay CFDIs para eliminar', 'deleted': 0}
    
    # Delete associated payments and reconciliations
    await db.payments.delete_many({'cfdi_id': {'$in': cfdi_ids}, 'company_id': company_id})
    await db.reconciliations.delete_many({'cfdi_id': {'$in': cfdi_ids}, 'company_id': company_id})
    
    # Delete CFDIs
    result = await db.cfdis.delete_many(query)
    
    # Audit log
    await audit_log(company_id, 'CFDI', f'bulk_delete_{len(cfdi_ids)}', 'BULK_DELETE', current_user['id'])
    
    return {
        'status': 'success', 
        'message': f'Se eliminaron {result.deleted_count} CFDIs correctamente',
        'deleted': result.deleted_count
    }


@router.delete("/{cfdi_id}")
async def delete_cfdi(cfdi_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Delete a CFDI"""
    company_id = await get_active_company_id(request, current_user)
    
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    # Delete associated payments and reconciliations
    await db.payments.delete_many({'cfdi_id': cfdi_id, 'company_id': company_id})
    await db.reconciliations.delete_many({'cfdi_id': cfdi_id, 'company_id': company_id})
    
    await db.cfdis.delete_one({'id': cfdi_id, 'company_id': company_id})
    await audit_log(company_id, 'CFDI', cfdi_id, 'DELETE', current_user['id'])
    
    return {'status': 'success', 'message': 'CFDI eliminado correctamente'}


@router.put("/{cfdi_id}/categorize")
async def categorize_cfdi(
    cfdi_id: str, 
    request: Request, 
    current_user: Dict = Depends(get_current_user),
    category_id: Optional[str] = Query(None),
    subcategory_id: Optional[str] = Query(None),
    vendor_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None)
):
    """Assign category and subcategory to a CFDI"""
    company_id = await get_active_company_id(request, current_user)
    
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    update_data = {}
    if category_id:
        update_data['category_id'] = category_id
    if subcategory_id:
        update_data['subcategory_id'] = subcategory_id
    if vendor_id:
        update_data['vendor_id'] = vendor_id
    if customer_id:
        update_data['customer_id'] = customer_id
    
    if update_data:
        await db.cfdis.update_one({'id': cfdi_id}, {'$set': update_data})
        await audit_log(company_id, 'CFDI', cfdi_id, 'CATEGORIZE', current_user['id'], update_data)

    # Propagar categoría/vendor/customer a todos los payments vinculados a este CFDI
    payment_update = {}
    if category_id:
        payment_update['category_id'] = category_id
    if subcategory_id:
        payment_update['subcategory_id'] = subcategory_id
    if vendor_id:
        payment_update['vendor_id'] = vendor_id
    if customer_id:
        payment_update['customer_id'] = customer_id

    payments_actualizados = 0
    if payment_update:
        result = await db.payments.update_many(
            {'company_id': company_id, 'cfdi_id': cfdi_id},
            {'$set': payment_update}
        )
        payments_actualizados = result.modified_count

    return {
        'status': 'success',
        'message': 'CFDI categorizado correctamente',
        'payments_actualizados': payments_actualizados
    }


@router.put("/{cfdi_id}/reconciliation-status")
async def update_cfdi_reconciliation_status(
    cfdi_id: str,
    data: dict,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Update the reconciliation status of a CFDI"""
    company_id = await get_active_company_id(request, current_user)
    
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    estado = data.get('estado_conciliacion', 'pendiente')
    if estado not in ['pendiente', 'conciliado', 'no_conciliable']:
        raise HTTPException(status_code=400, detail="Estado inválido")
    
    await db.cfdis.update_one({'id': cfdi_id}, {'$set': {'estado_conciliacion': estado}})
    await audit_log(company_id, 'CFDI', cfdi_id, 'UPDATE_STATUS', current_user['id'], {'estado': estado})
    
    return {'status': 'success', 'message': f'Estado actualizado a {estado}'}


@router.put("/{cfdi_id}/notes")
async def update_cfdi_notes(
    cfdi_id: str,
    data: dict,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Update notes for a CFDI"""
    company_id = await get_active_company_id(request, current_user)
    
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    notas = data.get('notas', '')
    
    await db.cfdis.update_one({'id': cfdi_id}, {'$set': {'notas': notas}})
    await audit_log(company_id, 'CFDI', cfdi_id, 'UPDATE_NOTES', current_user['id'])
    
    return {'status': 'success', 'message': 'Notas actualizadas'}



@router.post("/sync-payment-amounts")
async def sync_cfdi_payment_amounts(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    Synchronize CFDI monto_pagado/monto_cobrado with actual payment records.
    This fixes inconsistencies where CFDIs show paid amounts but have no associated payments,
    or vice versa.
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Get all CFDIs
    cfdis = await db.cfdis.find({'company_id': company_id}, {'_id': 0}).to_list(5000)
    
    # Get all completed payments (only those with truly reconciled bank transactions)
    bank_txns = await db.bank_transactions.find({'company_id': company_id}, {'_id': 0}).to_list(5000)
    reconciled_txn_ids = set(t['id'] for t in bank_txns if t.get('conciliado') == True)
    
    all_payments = await db.payments.find({'company_id': company_id, 'estatus': 'completado'}, {'_id': 0}).to_list(5000)
    
    # Filter to only include payments with truly reconciled bank transactions
    valid_payments = [p for p in all_payments if not p.get('bank_transaction_id') or p.get('bank_transaction_id') in reconciled_txn_ids]
    
    # Build a map of cfdi_id -> total paid/collected from valid payments
    cfdi_payment_totals = {}
    for payment in valid_payments:
        cfdi_id = payment.get('cfdi_id')
        if cfdi_id:
            if cfdi_id not in cfdi_payment_totals:
                cfdi_payment_totals[cfdi_id] = {'cobrado': 0, 'pagado': 0}
            if payment.get('tipo') == 'cobro':
                cfdi_payment_totals[cfdi_id]['cobrado'] += payment.get('monto', 0)
            else:
                cfdi_payment_totals[cfdi_id]['pagado'] += payment.get('monto', 0)
    
    updated_count = 0
    for cfdi in cfdis:
        cfdi_id = cfdi.get('id')
        current_cobrado = cfdi.get('monto_cobrado', 0) or 0
        current_pagado = cfdi.get('monto_pagado', 0) or 0
        
        # Get actual totals from valid payments
        actual = cfdi_payment_totals.get(cfdi_id, {'cobrado': 0, 'pagado': 0})
        actual_cobrado = actual['cobrado']
        actual_pagado = actual['pagado']
        
        # Check if update needed
        if current_cobrado != actual_cobrado or current_pagado != actual_pagado:
            await db.cfdis.update_one(
                {'id': cfdi_id},
                {'$set': {'monto_cobrado': actual_cobrado, 'monto_pagado': actual_pagado}}
            )
            updated_count += 1
            logger.info(f"CFDI {cfdi_id}: cobrado {current_cobrado} -> {actual_cobrado}, pagado {current_pagado} -> {actual_pagado}")
    
    return {
        'status': 'success',
        'message': f'Sincronización completada. {updated_count} CFDIs actualizados.',
        'updated_count': updated_count
    }


@router.get("/audit/fx-validation")
async def validate_cfdi_exchange_rates(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    limit: int = Query(500, le=2000)
):
    """Audit per-CFDI exchange rates against the official Banxico FIX (DOF) rate
    of the issuance day.
    
    Returns a list of CFDIs with deviation status:
      - ok: |actual - official| <= 1%
      - warning: 1% < |dev| <= 5%
      - critical: |dev| > 5% (likely capture error, may affect SAT deductibility)
    
    Requires BANXICO_TOKEN env var. If absent, returns an explanatory error.
    """
    from services.banxico_fx import get_official_rate, evaluate_deviation, _token
    
    if not _token():
        return {
            'success': False,
            'error': 'banxico_token_missing',
            'message': (
                'BANXICO_TOKEN no está configurado. Solicita el token gratuito en '
                'https://www.banxico.org.mx/SieAPIRest/service/v1/token y agrégalo '
                'al archivo backend/.env como BANXICO_TOKEN=tu_token_de_64_caracteres'
            )
        }
    
    company_id = await get_active_company_id(request, current_user)
    query = {'company_id': company_id, 'moneda': {'$ne': 'MXN'}}
    if fecha_desde:
        query.setdefault('fecha_emision', {})['$gte'] = fecha_desde
    if fecha_hasta:
        query.setdefault('fecha_emision', {})['$lte'] = fecha_hasta + 'T23:59:59'
    
    cursor = db.cfdis.find(query, {'_id': 0}).limit(limit)
    
    results = []
    summary_counts = {'ok': 0, 'warning': 0, 'critical': 0, 'unknown': 0}
    
    async for c in cursor:
        moneda = (c.get('moneda') or '').upper()
        actual = float(c.get('tipo_cambio') or 0)
        if actual <= 0 or moneda == 'MXN':
            continue
        
        fecha_iso = (c.get('fecha_emision') or '')[:10]
        if not fecha_iso:
            continue
        
        official = await get_official_rate(moneda, fecha_iso)
        if official is None:
            evaluation = {'status': 'unknown', 'deviation_pct': None,
                          'official_rate': None, 'actual_rate': round(actual, 4)}
        else:
            evaluation = evaluate_deviation(actual, official)
        
        summary_counts[evaluation['status']] = summary_counts.get(evaluation['status'], 0) + 1
        
        results.append({
            'cfdi_id': c.get('id'),
            'uuid': c.get('uuid'),
            'fecha_emision': fecha_iso,
            'moneda': moneda,
            'folio': c.get('folio_alegra') or c.get('referencia') or '',
            'emisor': c.get('emisor_nombre') or c.get('emisor_rfc') or '',
            'receptor': c.get('receptor_nombre') or c.get('receptor_rfc') or '',
            'total': c.get('total'),
            **evaluation,
        })
    
    return {
        'success': True,
        'count': len(results),
        'summary': summary_counts,
        'thresholds': {'ok_max_pct': 1.0, 'warning_max_pct': 5.0},
        'results': results,
    }


from pydantic import BaseModel as _BM


class FXFixRequest(_BM):
    cfdi_ids: List[str]
    confirm: bool = False


@router.post("/audit/fx-fix")
async def fix_cfdi_exchange_rates(
    payload: FXFixRequest,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Rewrite the `tipo_cambio` of the given CFDIs with the official Banxico
    FIX rate of the issuance date. Recomputes `total_mxn`, `subtotal`,
    `impuestos` and `iva_trasladado` accordingly. Writes an audit_log entry per
    CFDI.
    
    Body:
        {"cfdi_ids": [...], "confirm": true}
    """
    from services.banxico_fx import get_official_rate, _token
    
    if not _token():
        raise HTTPException(status_code=400, detail='BANXICO_TOKEN no configurado')
    if not payload.confirm:
        raise HTTPException(status_code=400, detail='Falta confirm=true')
    if not payload.cfdi_ids:
        raise HTTPException(status_code=400, detail='Lista vacía')
    
    company_id = await get_active_company_id(request, current_user)
    
    fixed = []
    skipped = []
    
    for cfdi_id in payload.cfdi_ids:
        c = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
        if not c:
            skipped.append({'cfdi_id': cfdi_id, 'reason': 'not_found'})
            continue
        
        moneda = (c.get('moneda') or '').upper()
        if moneda == 'MXN' or moneda not in ('USD', 'EUR', 'GBP', 'CAD'):
            skipped.append({'cfdi_id': cfdi_id, 'reason': f'unsupported_currency_{moneda}'})
            continue
        
        fecha_iso = (c.get('fecha_emision') or '')[:10]
        if not fecha_iso:
            skipped.append({'cfdi_id': cfdi_id, 'reason': 'no_date'})
            continue
        
        official = await get_official_rate(moneda, fecha_iso)
        if official is None or official <= 0:
            skipped.append({'cfdi_id': cfdi_id, 'reason': 'no_dof_rate'})
            continue
        
        old_tc = float(c.get('tipo_cambio') or 0)
        # `total` is stored in the original currency (after Phase 39 fix), so
        # only `tipo_cambio` and the MXN-derived fields need to change.
        total_orig = float(c.get('total_moneda_original') or c.get('total') or 0)
        new_total_mxn = round(total_orig * official, 2)
        new_subtotal = round(total_orig / 1.16, 2) if total_orig > 0 else 0
        new_impuestos = round(total_orig - new_subtotal, 2)
        
        await db.cfdis.update_one(
            {'id': cfdi_id},
            {'$set': {
                'tipo_cambio': round(official, 4),
                'total_mxn': new_total_mxn,
                'subtotal': new_subtotal,
                'impuestos': new_impuestos,
                'iva_trasladado': new_impuestos,
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }}
        )
        
        # Audit log entry
        try:
            await audit_log(
                company_id=company_id,
                entidad='cfdi',
                entity_id=cfdi_id,
                accion='fx_corrected_to_dof',
                user_id=current_user.get('id') or current_user.get('email', 'unknown'),
                datos_anteriores={
                    'tipo_cambio': old_tc,
                    'total_mxn': c.get('total_mxn'),
                },
                datos_nuevos={
                    'tipo_cambio': round(official, 4),
                    'total_mxn': new_total_mxn,
                    'fuente': 'banxico_fix_dof',
                    'fecha_emision': fecha_iso,
                    'moneda': moneda,
                }
            )
        except Exception as e:
            logger.warning("Audit log failed for cfdi %s: %s", cfdi_id, e)
        
        fixed.append({
            'cfdi_id': cfdi_id,
            'old_tc': old_tc,
            'new_tc': round(official, 4),
            'total_mxn': new_total_mxn,
        })
    
    return {
        'success': True,
        'fixed_count': len(fixed),
        'skipped_count': len(skipped),
        'fixed': fixed,
        'skipped': skipped,
    }
