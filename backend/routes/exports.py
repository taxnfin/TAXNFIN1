"""DIOT and accounting export routes"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import io
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id
from models.enums import UserRole

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/diot/preview")
async def get_diot_preview(request: Request, current_user: Dict = Depends(get_current_user), fecha_desde: str = None, fecha_hasta: str = None):
    """
    Get DIOT data preview - ONLY PAID EGRESO CFDIs WITH IVA ACREDITABLE
    
    IMPORTANT: DIOT only includes CFDIs that:
    1. Are type 'egreso' (expenses)
    2. Have been PAID (pagados) - via payment record or bank reconciliation
    3. Generate IVA acreditable (IVA > 0)
    
    EXCLUSIONS (per SAT rules):
    - Nómina (uso_cfdi = 'CN01' or tipo_comprobante = 'N')
    - CFDIs with no IVA (no IVA acreditable to report)
    - Sueldos y salarios
    - Asimilados a salarios
    
    The date filter is based on PAYMENT DATE, not emission date.
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Get all EGRESO CFDIs EXCLUDING NOMINA and non-IVA items
    # DIOT exclusions: CN01 (sin efectos fiscales/nómina), tipo_comprobante='N' (nómina)
    cfdi_query = {
        'company_id': company_id,
        'tipo_cfdi': 'egreso',
        # Exclude nómina and non-deductible items
        'uso_cfdi': {'$nin': ['CN01', 'CP01', 'D01', 'D02', 'D03', 'D04', 'D05', 'D06', 'D07', 'D08', 'D09', 'D10']},
        # Must have IVA acreditable
        '$or': [
            {'impuestos': {'$gt': 0}},
            {'iva_trasladado': {'$gt': 0}}
        ]
    }
    cfdis = await db.cfdis.find(cfdi_query, {'_id': 0}).to_list(10000)
    
    # Get categories
    categories = {c['id']: c for c in await db.categories.find({'company_id': company_id}, {'_id': 0}).to_list(1000)}
    subcategories = {s['id']: s for s in await db.subcategories.find({'company_id': company_id}, {'_id': 0}).to_list(1000)}
    
    # Get payments to check which CFDIs are paid
    payments = await db.payments.find({'company_id': company_id, 'tipo': 'pago', 'estatus': 'completado'}, {'_id': 0}).to_list(10000)
    payments_by_cfdi = {}
    for p in payments:
        cfdi_id = p.get('cfdi_id')
        if cfdi_id:
            if cfdi_id not in payments_by_cfdi:
                payments_by_cfdi[cfdi_id] = []
            payments_by_cfdi[cfdi_id].append(p)
    
    # Get reconciliations to find bank transaction info (for TC from bank statement)
    reconciliations = await db.reconciliations.find({'company_id': company_id}, {'_id': 0}).to_list(10000)
    recon_by_cfdi = {r['cfdi_id']: r for r in reconciliations if r.get('cfdi_id')}
    
    # Get bank transactions (for payment date and TC)
    bank_txns = await db.bank_transactions.find({'company_id': company_id}, {'_id': 0}).to_list(10000)
    bank_txn_by_id = {t['id']: t for t in bank_txns}
    
    # Parse date filters
    fecha_desde_dt = None
    fecha_hasta_dt = None
    if fecha_desde:
        try:
            fecha_desde_dt = datetime.fromisoformat(fecha_desde.replace('Z', '+00:00')) if 'T' in fecha_desde else datetime.strptime(fecha_desde, '%Y-%m-%d')
        except:
            pass
    if fecha_hasta:
        try:
            fecha_hasta_dt = datetime.fromisoformat(fecha_hasta.replace('Z', '+00:00')) if 'T' in fecha_hasta else datetime.strptime(fecha_hasta, '%Y-%m-%d')
            fecha_hasta_dt = fecha_hasta_dt.replace(hour=23, minute=59, second=59)
        except:
            pass
    
    # Cache for FX rates by date
    fx_rates_cache = {}
    
    async def get_fx_rate_for_date(moneda: str, fecha: str) -> float:
        """Get FX rate for a specific date, with caching"""
        cache_key = f"{moneda}_{fecha[:10]}"
        if cache_key in fx_rates_cache:
            return fx_rates_cache[cache_key]
        
        # Try to find exact date rate
        rate = await db.fx_rates.find_one({
            'company_id': company_id,
            '$or': [
                {'moneda_cotizada': moneda},
                {'moneda_origen': moneda}
            ],
            'fecha_vigencia': {'$regex': f'^{fecha[:10]}'}
        }, {'_id': 0})
        
        if rate:
            tc = rate.get('tipo_cambio') or rate.get('tasa') or 1
            fx_rates_cache[cache_key] = tc
            return tc
        
        # Fallback: find closest rate before the date
        rate = await db.fx_rates.find_one({
            'company_id': company_id,
            '$or': [
                {'moneda_cotizada': moneda},
                {'moneda_origen': moneda}
            ],
            'fecha_vigencia': {'$lte': fecha}
        }, {'_id': 0}, sort=[('fecha_vigencia', -1)])
        
        if rate:
            tc = rate.get('tipo_cambio') or rate.get('tasa') or 1
            fx_rates_cache[cache_key] = tc
            return tc
        
        # Default fallback
        default_rate = 17.5 if moneda == 'USD' else 19.0 if moneda == 'EUR' else 1
        fx_rates_cache[cache_key] = default_rate
        return default_rate
    
    records = []
    total_iva_acreditable = 0
    total_iva_retenido = 0
    total_monto = 0
    total_monto_mxn = 0
    
    for cfdi in cfdis:
        # Get CFDI currency
        moneda = cfdi.get('moneda', 'MXN')
        
        # Get payment info if exists
        cfdi_payments = payments_by_cfdi.get(cfdi['id'], [])
        fecha_pago_str = ''
        pagado = False
        tipo_cambio_pago = 1.0
        fecha_pago_dt = None
        
        # Check if paid via payment record
        if cfdi_payments:
            pagado = True
            latest_payment = max(cfdi_payments, key=lambda p: p.get('fecha_pago', datetime.min) if p.get('fecha_pago') else datetime.min)
            fecha_pago = latest_payment.get('fecha_pago')
            if fecha_pago:
                if isinstance(fecha_pago, datetime):
                    fecha_pago_str = fecha_pago.strftime('%Y-%m-%d')
                    fecha_pago_dt = fecha_pago
                else:
                    fecha_pago_str = str(fecha_pago)[:10]
                    try:
                        fecha_pago_dt = datetime.fromisoformat(str(fecha_pago).replace('Z', '+00:00'))
                    except:
                        pass
            # Use stored TC if available
            if latest_payment.get('tipo_cambio_historico'):
                tipo_cambio_pago = latest_payment.get('tipo_cambio_historico')
        
        # Also check if paid via reconciliation (bank transaction)
        recon = recon_by_cfdi.get(cfdi['id'])
        if recon and not pagado:
            bank_txn = bank_txn_by_id.get(recon.get('bank_transaction_id'))
            if bank_txn:
                pagado = True
                fecha_mov = bank_txn.get('fecha_movimiento')
                if fecha_mov:
                    if isinstance(fecha_mov, datetime):
                        fecha_pago_str = fecha_mov.strftime('%Y-%m-%d')
                        fecha_pago_dt = fecha_mov
                    else:
                        fecha_pago_str = str(fecha_mov)[:10]
                        try:
                            fecha_pago_dt = datetime.fromisoformat(str(fecha_mov).replace('Z', '+00:00'))
                        except:
                            pass
        elif recon and pagado:
            # Already paid but reconciled - use bank transaction date as fecha_pago
            bank_txn = bank_txn_by_id.get(recon.get('bank_transaction_id'))
            if bank_txn:
                fecha_mov = bank_txn.get('fecha_movimiento')
                if fecha_mov:
                    if isinstance(fecha_mov, datetime):
                        fecha_pago_str = fecha_mov.strftime('%Y-%m-%d')
                        fecha_pago_dt = fecha_mov
                    else:
                        fecha_pago_str = str(fecha_mov)[:10]
                        try:
                            fecha_pago_dt = datetime.fromisoformat(str(fecha_mov).replace('Z', '+00:00'))
                        except:
                            pass
        
        # DIOT ONLY INCLUDES PAID CFDIs - Skip unpaid ones
        if not pagado:
            continue
        
        # Filter by payment date if date range is specified
        if fecha_pago_dt:
            # Normalize to naive datetime for comparison
            fecha_pago_naive = fecha_pago_dt.replace(tzinfo=None) if hasattr(fecha_pago_dt, 'tzinfo') and fecha_pago_dt.tzinfo else fecha_pago_dt
            if fecha_desde_dt:
                fecha_desde_naive = fecha_desde_dt.replace(tzinfo=None) if hasattr(fecha_desde_dt, 'tzinfo') and fecha_desde_dt.tzinfo else fecha_desde_dt
                if fecha_pago_naive < fecha_desde_naive:
                    continue
            if fecha_hasta_dt:
                fecha_hasta_naive = fecha_hasta_dt.replace(tzinfo=None) if hasattr(fecha_hasta_dt, 'tzinfo') and fecha_hasta_dt.tzinfo else fecha_hasta_dt
                if fecha_pago_naive > fecha_hasta_naive:
                    continue
        elif fecha_desde_dt or fecha_hasta_dt:
            # If we have date filters but no payment date, skip this record
            continue
        
        # Get FX rate for payment date if currency is not MXN
        if moneda != 'MXN' and fecha_pago_str:
            tipo_cambio_pago = await get_fx_rate_for_date(moneda, fecha_pago_str)
        elif moneda != 'MXN':
            # Use emission date FX rate as fallback
            fecha_emision = cfdi.get('fecha_emision', '')
            if fecha_emision:
                fecha_str = fecha_emision.strftime('%Y-%m-%d') if isinstance(fecha_emision, datetime) else str(fecha_emision)[:10]
                tipo_cambio_pago = await get_fx_rate_for_date(moneda, fecha_str)
        
        # Determine tipo_tercero based on RFC
        rfc = cfdi.get('emisor_rfc', '')
        if len(rfc) == 13:
            tipo_tercero = '04'  # Persona Moral Nacional
            tipo_tercero_desc = 'Proveedor Nacional (PM)'
        elif len(rfc) == 12:
            tipo_tercero = '04'  # Persona Física Nacional
            tipo_tercero_desc = 'Proveedor Nacional (PF)'
        elif rfc.startswith('XEXX') or rfc.startswith('XAXX'):
            tipo_tercero = '05'  # Extranjero
            tipo_tercero_desc = 'Proveedor Extranjero'
        else:
            tipo_tercero = '04'
            tipo_tercero_desc = 'Proveedor Nacional'
        
        subtotal = cfdi.get('subtotal', 0) or 0
        impuestos = cfdi.get('impuestos', 0) or 0
        total = cfdi.get('total', 0) or 0
        
        # Calculate MXN amounts
        subtotal_mxn = subtotal * tipo_cambio_pago if moneda != 'MXN' else subtotal
        total_mxn = total * tipo_cambio_pago if moneda != 'MXN' else total
        
        # Get IVA components from CFDI (parsed from XML)
        # IVA acreditable (trasladado)
        iva_acreditable = cfdi.get('iva_trasladado', 0) or impuestos
        if iva_acreditable == 0 and impuestos > 0:
            iva_acreditable = impuestos
        
        # IVA retenido (from CFDI) - check both field names for compatibility
        iva_retenido = cfdi.get('iva_retenido', 0) or cfdi.get('retencion_iva', 0) or 0
        
        # ISR retenido (if present) - check both field names for compatibility
        isr_retenido = cfdi.get('isr_retenido', 0) or cfdi.get('retencion_isr', 0) or 0
        
        # Convert IVA to MXN
        iva_acreditable_mxn = iva_acreditable * tipo_cambio_pago if moneda != 'MXN' else iva_acreditable
        iva_retenido_mxn = iva_retenido * tipo_cambio_pago if moneda != 'MXN' else iva_retenido
        isr_retenido_mxn = isr_retenido * tipo_cambio_pago if moneda != 'MXN' else isr_retenido
        
        categoria = categories.get(cfdi.get('category_id'), {}).get('nombre', '')
        subcategoria = subcategories.get(cfdi.get('subcategory_id'), {}).get('nombre', '')
        
        # Get fecha emision
        fecha_emision = cfdi.get('fecha_emision', '')
        if isinstance(fecha_emision, datetime):
            fecha_emision_str = fecha_emision.strftime('%Y-%m-%d')
        else:
            fecha_emision_str = str(fecha_emision)[:10] if fecha_emision else ''
        
        records.append({
            'tipo_tercero': tipo_tercero,
            'tipo_tercero_desc': tipo_tercero_desc,
            'tipo_operacion': '85',  # Otros (default)
            'tipo_operacion_desc': 'Otros',
            'rfc': rfc,
            'nombre': cfdi.get('emisor_nombre', ''),
            'pais': 'MX',
            'nacionalidad': 'Nacional',
            # Original amounts (in CFDI currency)
            'moneda': moneda,
            'valor_actos_pagados': total,
            'subtotal': subtotal,
            # MXN amounts (converted)
            'valor_actos_pagados_mxn': round(total_mxn, 2),
            'subtotal_mxn': round(subtotal_mxn, 2),
            'tipo_cambio': round(tipo_cambio_pago, 4),
            # For DIOT report (always in MXN)
            'valor_actos_0': 0,
            'valor_actos_exentos': 0,
            'valor_actos_16': round(subtotal_mxn, 2),
            'iva_retenido': round(iva_retenido_mxn, 2),
            'isr_retenido': round(isr_retenido_mxn, 2),
            'iva_acreditable': round(iva_acreditable_mxn, 2),
            # Original IVA (in CFDI currency)
            'iva_retenido_original': round(iva_retenido, 2),
            'isr_retenido_original': round(isr_retenido, 2),
            'iva_acreditable_original': round(iva_acreditable, 2),
            # Dates
            'fecha_emision': fecha_emision_str,
            'fecha_pago': fecha_pago_str,
            'pagado': pagado,
            'uuid': cfdi.get('uuid', ''),
            'categoria': categoria,
            'subcategoria': subcategoria,
            'cfdi_id': cfdi.get('id', '')
        })
        
        total_iva_acreditable += iva_acreditable_mxn
        total_iva_retenido += iva_retenido_mxn
        total_monto += total
        total_monto_mxn += total_mxn
    
    return {
        'records': records,
        'summary': {
            'totalOperaciones': len(records),
            'totalIVA': round(total_iva_acreditable, 2),
            'totalIVARetenido': round(total_iva_retenido, 2),
            'totalMonto': round(total_monto, 2),
            'totalMontoMXN': round(total_monto_mxn, 2)
        }
    }

# ===== EXPORTAR DIOT =====
@router.get("/export/diot")
async def export_diot(request: Request, current_user: Dict = Depends(get_current_user), fecha_desde: str = None, fecha_hasta: str = None):
    """Export CFDIs in DIOT format (CSV) - ONLY EGRESO WITH IVA, EXCLUDES NOMINA"""
    from fastapi.responses import StreamingResponse
    import io
    import csv
    
    company_id = await get_active_company_id(request, current_user)
    
    # DIOT query: Only egreso CFDIs with IVA acreditable, excluding nómina
    query = {
        'company_id': company_id,
        'tipo_cfdi': 'egreso',
        # Exclude nómina and non-deductible items (CN01 = sin efectos fiscales / nómina)
        'uso_cfdi': {'$nin': ['CN01', 'CP01', 'D01', 'D02', 'D03', 'D04', 'D05', 'D06', 'D07', 'D08', 'D09', 'D10']},
        # Must have IVA acreditable
        '$or': [
            {'impuestos': {'$gt': 0}},
            {'iva_trasladado': {'$gt': 0}}
        ]
    }
    if fecha_desde:
        query['fecha_emision'] = {'$gte': fecha_desde}
    if fecha_hasta:
        if 'fecha_emision' in query:
            query['fecha_emision']['$lte'] = fecha_hasta
        else:
            query['fecha_emision'] = {'$lte': fecha_hasta}
    
    cfdis = await db.cfdis.find(query, {'_id': 0}).sort('fecha_emision', 1).to_list(10000)
    
    # Get categories
    categories = {c['id']: c for c in await db.categories.find({'company_id': company_id}, {'_id': 0}).to_list(1000)}
    subcategories = {s['id']: s for s in await db.subcategories.find({'company_id': company_id}, {'_id': 0}).to_list(1000)}
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # DIOT Header
    writer.writerow([
        'Tipo Tercero', 'Tipo Operación', 'RFC', 'Nombre/Razón Social',
        'País', 'Nacionalidad', 'Valor Actos o Actividades Pagados',
        'Valor Actos o Actividades 0%', 'Valor Actos o Actividades Exentos',
        'Valor Actos o Actividades Tasa 16%', 'IVA Retenido', 'IVA Acreditable',
        'Fecha Emisión', 'UUID', 'Categoría', 'Subcategoría', 'Estado Conciliación'
    ])
    
    for cfdi in cfdis:
        tipo_tercero = '04' if cfdi.get('tipo_cfdi') == 'egreso' else '05'
        tipo_operacion = '03'
        categoria = categories.get(cfdi.get('category_id'), {}).get('nombre', '')
        subcategoria = subcategories.get(cfdi.get('subcategory_id'), {}).get('nombre', '')
        
        writer.writerow([
            tipo_tercero,
            tipo_operacion,
            cfdi.get('emisor_rfc', ''),
            cfdi.get('emisor_nombre', ''),
            'MX',
            'Nacional',
            cfdi.get('total', 0),
            0,
            0,
            cfdi.get('subtotal', 0),
            0,
            cfdi.get('impuestos', 0),
            cfdi.get('fecha_emision', '')[:10] if cfdi.get('fecha_emision') else '',
            cfdi.get('uuid', ''),
            categoria,
            subcategoria,
            cfdi.get('estado_conciliacion', 'pendiente')
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=DIOT_export.csv"}
    )

# ===== PLANTILLA ESTADO DE CUENTA - MOVED TO routes/bank_transactions.py =====


@router.get("/export/coi")
async def export_coi(
    fecha_inicio: datetime = Query(...),
    fecha_fin: datetime = Query(...),
    current_user: Dict = Depends(get_current_user)
):
    """Exporta a formato COI (Contabilidad)"""
    
    service = AccountingExportService(db)
    csv_data = await service.export_to_coi(
        company_id=current_user['company_id'],
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )
    
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=coi_export_{fecha_inicio.strftime('%Y%m%d')}.csv"}
    )

@router.get("/export/xml-fiscal")
async def export_xml_fiscal(
    fecha_inicio: datetime = Query(...),
    fecha_fin: datetime = Query(...),
    current_user: Dict = Depends(get_current_user)
):
    """Exporta a XML Fiscal (Balanza SAT)"""
    
    service = AccountingExportService(db)
    xml_data = await service.export_to_xml_fiscal(
        company_id=current_user['company_id'],
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )
    
    return StreamingResponse(
        iter([xml_data]),
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename=balanza_sat_{fecha_inicio.strftime('%Y%m%d')}.xml"}
    )

@router.get("/export/alegra")
async def export_alegra(
    fecha_inicio: datetime = Query(...),
    fecha_fin: datetime = Query(...),
    current_user: Dict = Depends(get_current_user)
):
    """Exporta a formato Alegra (JSON)"""
    
    service = AccountingExportService(db)
    json_data = await service.export_to_alegra(
        company_id=current_user['company_id'],
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )
    
    return StreamingResponse(
        iter([json_data]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=alegra_export_{fecha_inicio.strftime('%Y%m%d')}.json"}
    )

@router.get("/export/cashflow")
async def export_cashflow_report(
    formato: str = Query("excel", regex="^(excel|json)$"),
    current_user: Dict = Depends(get_current_user)
):
    """Exporta reporte de cashflow 13 semanas"""
    
    service = AccountingExportService(db)
    data = await service.export_cashflow_report(
        company_id=current_user['company_id'],
        formato=formato
    )
    
    if formato == 'excel':
        return StreamingResponse(
            iter([data]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=cashflow_report_{datetime.now().strftime('%Y%m%d')}.csv"}
        )
    else:
        return StreamingResponse(
            iter([data]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=cashflow_report_{datetime.now().strftime('%Y%m%d')}.json"}
        )



