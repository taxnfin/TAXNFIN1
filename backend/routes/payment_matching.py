"""Payment matching, auto-reconciliation and batch payment routes"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
import uuid
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id
from services.audit import audit_log
from services.fx import get_fx_rate_by_date
from models.enums import UserRole, PaymentStatus, PaymentMethod

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/payments/{payment_id}/match-candidates")
async def get_payment_match_candidates(
    payment_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Find bank transactions that could match this payment.
    Searches by:
    - UUID of the linked CFDI in the transaction description
    - Similar amount (+/- 1%)
    - Date within 30 days
    """
    company_id = await get_active_company_id(request, current_user)
    
    payment = await db.payments.find_one({'id': payment_id, 'company_id': company_id}, {'_id': 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    
    candidates = []
    
    # Get the linked CFDI if exists
    cfdi = None
    cfdi_uuid = None
    if payment.get('cfdi_id'):
        cfdi = await db.cfdis.find_one({'id': payment['cfdi_id']}, {'_id': 0})
        if cfdi:
            cfdi_uuid = cfdi.get('uuid', '')
    
    # Search bank transactions
    # Criteria: not yet reconciled, same company, similar amount or matching UUID
    monto = payment.get('monto', 0)
    moneda = payment.get('moneda', 'MXN')
    tipo_esperado = 'credito' if payment['tipo'] == 'cobro' else 'debito'
    
    # Build query
    query = {
        'company_id': company_id,
        'conciliado': False
    }
    
    # Get all unreconciled transactions
    transactions = await db.bank_transactions.find(query, {'_id': 0}).to_list(500)
    
    for txn in transactions:
        score = 0
        match_reasons = []
        
        # Check if UUID is in description
        if cfdi_uuid and cfdi_uuid.upper() in (txn.get('descripcion', '') + txn.get('referencia', '')).upper():
            score += 100
            match_reasons.append(f"UUID encontrado en descripción")
        
        # Check amount (within 1% tolerance or exact)
        txn_monto = txn.get('monto', 0)
        if txn_monto > 0:
            diff_pct = abs(txn_monto - monto) / monto * 100 if monto > 0 else 100
            if diff_pct < 0.01:  # Exact match
                score += 80
                match_reasons.append(f"Monto exacto")
            elif diff_pct < 1:  # Within 1%
                score += 60
                match_reasons.append(f"Monto similar ({diff_pct:.2f}% diferencia)")
            elif diff_pct < 5:  # Within 5%
                score += 30
                match_reasons.append(f"Monto cercano ({diff_pct:.2f}% diferencia)")
        
        # Check transaction type matches
        if txn.get('tipo_movimiento') == tipo_esperado:
            score += 20
            match_reasons.append(f"Tipo coincide ({tipo_esperado})")
        
        # Check currency matches
        if txn.get('moneda', 'MXN') == moneda:
            score += 10
            match_reasons.append(f"Moneda coincide ({moneda})")
        
        # Only include if score is meaningful
        if score >= 30:
            # Get bank account info
            bank_account = await db.bank_accounts.find_one({'id': txn.get('bank_account_id')}, {'_id': 0, 'banco': 1, 'nombre': 1})
            
            candidates.append({
                'transaction_id': txn['id'],
                'fecha': txn.get('fecha_movimiento'),
                'descripcion': txn.get('descripcion', '')[:100],
                'referencia': txn.get('referencia', ''),
                'monto': txn_monto,
                'tipo': txn.get('tipo_movimiento'),
                'moneda': txn.get('moneda', 'MXN'),
                'banco': bank_account.get('banco', '') if bank_account else '',
                'cuenta': bank_account.get('nombre', '') if bank_account else '',
                'score': score,
                'match_reasons': match_reasons
            })
    
    # Sort by score descending
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    return {
        'payment_id': payment_id,
        'payment_monto': monto,
        'payment_moneda': moneda,
        'payment_tipo': payment['tipo'],
        'cfdi_uuid': cfdi_uuid,
        'candidates': candidates[:10],  # Top 10 matches
        'total_found': len(candidates)
    }


@router.post("/payments/{payment_id}/auto-reconcile")
async def auto_reconcile_payment(
    payment_id: str,
    request: Request,
    transaction_id: str = Query(..., description="ID del movimiento bancario a conciliar"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Reconcile a payment with a bank transaction after user authorization.
    """
    company_id = await get_active_company_id(request, current_user)
    
    payment = await db.payments.find_one({'id': payment_id, 'company_id': company_id}, {'_id': 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    
    transaction = await db.bank_transactions.find_one({'id': transaction_id, 'company_id': company_id}, {'_id': 0})
    if not transaction:
        raise HTTPException(status_code=404, detail="Movimiento bancario no encontrado")
    
    if transaction.get('conciliado'):
        raise HTTPException(status_code=400, detail="El movimiento ya está conciliado")
    
    # Mark transaction as reconciled and link to payment
    await db.bank_transactions.update_one(
        {'id': transaction_id},
        {'$set': {
            'conciliado': True,
            'payment_id': payment_id,
            'cfdi_ids': [payment.get('cfdi_id')] if payment.get('cfdi_id') else [],
            'fecha_conciliacion': datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Update payment with transaction reference
    await db.payments.update_one(
        {'id': payment_id},
        {'$set': {
            'bank_transaction_id': transaction_id,
            'conciliado': True
        }}
    )
    
    await audit_log(company_id, 'Payment', payment_id, 'AUTO_RECONCILE', current_user['id'])
    
    return {
        'status': 'success',
        'message': 'Pago conciliado exitosamente',
        'payment_id': payment_id,
        'transaction_id': transaction_id
    }


@router.get("/bank-transactions/{txn_id}/match-cfdi")
async def find_matching_cfdi_for_transaction(
    txn_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
    tolerance_days: int = Query(60, description="Tolerancia de días para buscar CFDIs (default: 60)")
):
    """
    P0 - Matching Automático de CFDIs
    Find CFDIs that match a bank transaction by amount and date (±tolerance_days).
    Used when creating payments from bank movements to suggest automatic CFDI links.
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Get the bank transaction
    txn = await db.bank_transactions.find_one({'id': txn_id, 'company_id': company_id}, {'_id': 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Movimiento bancario no encontrado")
    
    monto = txn.get('monto', 0)
    moneda = txn.get('moneda', 'MXN')
    fecha_txn_str = txn.get('fecha_movimiento')
    tipo_movimiento = txn.get('tipo_movimiento', 'credito')  # credito = cobro, debito = pago
    
    # Parse the transaction date
    if isinstance(fecha_txn_str, str):
        try:
            fecha_txn = datetime.fromisoformat(fecha_txn_str.replace('Z', '+00:00'))
        except:
            fecha_txn = datetime.now(timezone.utc)
    else:
        fecha_txn = fecha_txn_str or datetime.now(timezone.utc)
    
    # Define date range (±tolerance_days)
    fecha_inicio = (fecha_txn - timedelta(days=tolerance_days)).isoformat()
    fecha_fin = (fecha_txn + timedelta(days=tolerance_days)).isoformat()
    
    # Determine CFDI type based on transaction type
    # credito (deposit) = ingreso (we received payment for a sale)
    # debito (withdrawal) = egreso (we paid for a purchase) OR nomina
    cfdi_tipo = 'ingreso' if tipo_movimiento == 'credito' else 'egreso'
    
    # Build query to find matching CFDIs
    # Look for CFDIs with similar amount and within date range
    # For debito, also include nomina type
    if tipo_movimiento == 'debito':
        query = {
            'company_id': company_id,
            'tipo_cfdi': {'$in': ['egreso', 'nomina']},
            'estatus': 'vigente',
            'fecha_emision': {'$gte': fecha_inicio, '$lte': fecha_fin}
        }
    else:
        query = {
            'company_id': company_id,
            'tipo_cfdi': cfdi_tipo,
            'estatus': 'vigente',
            'fecha_emision': {'$gte': fecha_inicio, '$lte': fecha_fin}
        }
    
    # Get candidate CFDIs
    cfdis = await db.cfdis.find(query, {'_id': 0}).to_list(200)
    
    # Get transaction description for name matching
    txn_descripcion_upper = (txn.get('descripcion', '') + ' ' + txn.get('referencia', '')).upper()
    
    matches = []
    for cfdi in cfdis:
        cfdi_total = cfdi.get('total', 0)
        cfdi_moneda = cfdi.get('moneda', 'MXN')
        is_nomina = cfdi.get('tipo_cfdi') == 'nomina' or cfdi.get('is_nomina', False)
        
        # Calculate pending amount
        if cfdi.get('tipo_cfdi') == 'ingreso':
            monto_cubierto = cfdi.get('monto_cobrado', 0) or 0
        else:
            monto_cubierto = cfdi.get('monto_pagado', 0) or 0
        
        saldo_pendiente = cfdi_total - monto_cubierto
        
        # Skip fully paid CFDIs
        if saldo_pendiente < 0.01:
            continue
        
        # Calculate match score
        score = 0
        match_reasons = []
        
        # Amount matching (compare with transaction amount)
        # Allow for some tolerance (0.5% for banking fees, rounding)
        # Compare with both total and saldo_pendiente
        if monto > 0:
            # Calculate differences with both total and pending
            diff_pct_pending = abs(monto - saldo_pendiente) / saldo_pendiente * 100 if saldo_pendiente > 0 else 100
            diff_pct_total = abs(monto - cfdi_total) / cfdi_total * 100 if cfdi_total > 0 else 100
            
            # Use the better match (smaller difference)
            diff_pct = min(diff_pct_pending, diff_pct_total)
            match_with_total = diff_pct_total < diff_pct_pending
            
            if diff_pct < 0.1:  # Exact match (within 0.1%)
                score += 55
                match_reasons.append("Monto exacto" + (" (total)" if match_with_total else ""))
            elif diff_pct < 0.5:  # Near-exact match
                score += 50
                match_reasons.append("Monto exacto" + (" (total)" if match_with_total else ""))
            elif diff_pct < 2:  # Within 2%
                score += 35
                match_reasons.append(f"Monto muy cercano ({diff_pct:.1f}% dif)")
            elif diff_pct < 5:  # Within 5%
                score += 20
                match_reasons.append(f"Monto cercano ({diff_pct:.1f}% dif)")
            elif diff_pct < 10:  # Within 10%
                score += 10
                match_reasons.append(f"Monto aproximado ({diff_pct:.1f}% dif)")
            else:
                continue  # Too different, skip this CFDI
        
        # Date proximity bonus
        cfdi_fecha_str = cfdi.get('fecha_emision')
        if cfdi_fecha_str:
            try:
                cfdi_fecha = datetime.fromisoformat(cfdi_fecha_str.replace('Z', '+00:00')) if isinstance(cfdi_fecha_str, str) else cfdi_fecha_str
                days_diff = abs((fecha_txn - cfdi_fecha).days)
                
                if days_diff <= 7:
                    score += 30
                    match_reasons.append("Fecha muy cercana (≤7 días)")
                elif days_diff <= 15:
                    score += 20
                    match_reasons.append(f"Fecha cercana ({days_diff} días)")
                elif days_diff <= 30:
                    score += 10
                    match_reasons.append(f"Fecha dentro de 30 días")
                else:
                    score += 5
                    match_reasons.append(f"Fecha dentro de {days_diff} días")
            except:
                pass
        
        # Currency match bonus
        if cfdi_moneda == moneda:
            score += 10
            match_reasons.append(f"Moneda coincide ({moneda})")
        
        # Check if CFDI UUID appears in transaction description or reference
        cfdi_uuid = cfdi.get('uuid', '')
        if cfdi_uuid and cfdi_uuid.upper()[:8] in txn_descripcion_upper:
            score += 40
            match_reasons.append("UUID parcial en descripción")
        
        # NAME MATCHING: Check if receptor/emisor name appears in transaction description
        # This is especially important for nóminas where receptor is the employee
        nombres_buscar = []
        if is_nomina:
            # For nóminas, search for employee name (receptor)
            receptor = cfdi.get('receptor_nombre', '')
            if receptor:
                nombres_buscar.append(receptor.upper())
        else:
            # For regular egresos, search for provider name (emisor)
            emisor = cfdi.get('emisor_nombre', '')
            if emisor:
                nombres_buscar.append(emisor.upper())
            # Also check receptor in case it's in description
            receptor = cfdi.get('receptor_nombre', '')
            if receptor:
                nombres_buscar.append(receptor.upper())
        
        # Check name parts in transaction description
        # Improved matching: also check if transaction description is contained in CFDI name
        name_matched = False
        for nombre in nombres_buscar:
            if name_matched:
                break
                
            nombre_parts = [p for p in nombre.split() if len(p) > 2]
            if not nombre_parts:
                continue
                
            # Method 1: Check how many CFDI name parts appear in bank description
            matches_count = sum(1 for part in nombre_parts if part in txn_descripcion_upper)
            
            # Method 2: Check if bank description (possibly truncated) is start of CFDI name
            # This handles cases like "INGENIERIA EN MAQUINARIA Y ENE" matching "INGENIERIA EN MAQUINARIA Y ENERGIA..."
            txn_desc_clean = txn_descripcion_upper.replace(',', ' ').replace('.', ' ').strip()
            txn_parts = [p for p in txn_desc_clean.split() if len(p) > 2]
            
            # Check if transaction description words match start of CFDI name
            if txn_parts and len(txn_parts) >= 2:
                # Count consecutive matches from start
                consecutive_matches = 0
                for i, part in enumerate(txn_parts):
                    if i < len(nombre_parts) and part in nombre_parts[i]:
                        consecutive_matches += 1
                    elif part in nombre:  # Part appears anywhere in name
                        consecutive_matches += 0.5
                    else:
                        break
                
                # If most of transaction description matches CFDI name start
                if consecutive_matches >= len(txn_parts) * 0.8:
                    score += 45
                    match_reasons.append(f"Nombre coincide (descripción truncada)")
                    name_matched = True
                    continue
            
            # Original method: count name parts in description
            if matches_count >= 3:
                score += 50
                match_reasons.append(f"Nombre completo coincide")
                name_matched = True
            elif matches_count >= 2:
                score += 35
                match_reasons.append(f"Nombre parcial coincide ({matches_count} partes)")
                name_matched = True
            elif matches_count >= 1 and len(nombre_parts) <= 2:
                score += 20
                match_reasons.append(f"Nombre parcial coincide")
                name_matched = True
            
            # Method 3: Check similarity between names (for truncated bank descriptions)
            if not name_matched and txn_desc_clean:
                # See if bank description is a prefix of CFDI name
                nombre_sin_espacios = ''.join(nombre.split())
                desc_sin_espacios = ''.join(txn_desc_clean.split())
                
                if len(desc_sin_espacios) >= 10 and nombre_sin_espacios.startswith(desc_sin_espacios[:min(len(desc_sin_espacios), 20)]):
                    score += 40
                    match_reasons.append(f"Nombre truncado coincide")
                    name_matched = True
        
        # Only include if score is meaningful
        if score >= 20:
            matches.append({
                'cfdi_id': cfdi.get('id'),
                'uuid': cfdi_uuid,
                'uuid_short': cfdi_uuid[:8] if cfdi_uuid else '',
                'tipo_cfdi': cfdi_tipo,
                'fecha_emision': cfdi.get('fecha_emision'),
                'emisor_nombre': cfdi.get('emisor_nombre', ''),
                'receptor_nombre': cfdi.get('receptor_nombre', ''),
                'total': cfdi_total,
                'saldo_pendiente': saldo_pendiente,
                'moneda': cfdi_moneda,
                'score': score,
                'match_reasons': match_reasons,
                'confidence': 'alta' if score >= 60 else 'media' if score >= 40 else 'baja'
            })
    
    # Sort by score descending
    matches.sort(key=lambda x: x['score'], reverse=True)
    
    # Prepare response
    best_match = matches[0] if matches else None
    
    return {
        'transaction_id': txn_id,
        'transaction_monto': monto,
        'transaction_moneda': moneda,
        'transaction_fecha': fecha_txn_str,
        'transaction_tipo': tipo_movimiento,
        'cfdi_tipo_esperado': cfdi_tipo,
        'tolerance_days': tolerance_days,
        'best_match': best_match,
        'all_matches': matches[:10],  # Top 10
        'total_matches': len(matches),
        'auto_link_recommended': best_match is not None and best_match['score'] >= 60
    }


@router.post("/payments/from-bank-with-cfdi-match")
async def create_payment_from_bank_with_cfdi_match(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    bank_transaction_id: str = Query(..., description="ID del movimiento bancario"),
    cfdi_id: Optional[str] = Query(None, description="ID del CFDI a vincular (opcional, se detecta automáticamente si no se provee)"),
    auto_detect: bool = Query(True, description="Detectar CFDI automáticamente por monto y fecha")
):
    """
    P0 - Create a payment from a bank transaction with automatic CFDI matching.
    If auto_detect=True and no cfdi_id provided, will try to find the best matching CFDI.
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Get the bank transaction
    txn = await db.bank_transactions.find_one({'id': bank_transaction_id, 'company_id': company_id}, {'_id': 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Movimiento bancario no encontrado")
    
    if txn.get('conciliado'):
        raise HTTPException(status_code=400, detail="Este movimiento ya está conciliado")
    
    # Check if payment already exists for this bank transaction (prevent duplicates)
    existing_payment = await db.payments.find_one({
        'company_id': company_id,
        'bank_transaction_id': bank_transaction_id
    }, {'_id': 0, 'id': 1})
    
    if existing_payment:
        raise HTTPException(status_code=400, detail="Ya existe un pago para este movimiento bancario")
    
    # Get bank account info
    bank_account = await db.bank_accounts.find_one({'id': txn.get('bank_account_id')}, {'_id': 0})
    moneda = txn.get('moneda') or (bank_account.get('moneda') if bank_account else 'MXN')
    
    # Determine payment type
    tipo = 'cobro' if txn.get('tipo_movimiento') == 'credito' else 'pago'
    
    # Auto-detect CFDI if requested and not provided
    matched_cfdi = None
    match_info = None
    
    if cfdi_id:
        # Use provided CFDI
        matched_cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
        if not matched_cfdi:
            raise HTTPException(status_code=404, detail="CFDI no encontrado")
    elif auto_detect:
        # Try to find matching CFDI automatically
        # Use internal call to match-cfdi endpoint logic
        monto = txn.get('monto', 0)
        fecha_txn_str = txn.get('fecha_movimiento')
        tipo_movimiento = txn.get('tipo_movimiento', 'credito')
        
        if isinstance(fecha_txn_str, str):
            try:
                fecha_txn = datetime.fromisoformat(fecha_txn_str.replace('Z', '+00:00'))
            except:
                fecha_txn = datetime.now(timezone.utc)
        else:
            fecha_txn = fecha_txn_str or datetime.now(timezone.utc)
        
        # Define date range (±60 days as requested by user)
        fecha_inicio = (fecha_txn - timedelta(days=60)).isoformat()
        fecha_fin = (fecha_txn + timedelta(days=60)).isoformat()
        
        cfdi_tipo = 'ingreso' if tipo_movimiento == 'credito' else 'egreso'
        
        query = {
            'company_id': company_id,
            'tipo_cfdi': cfdi_tipo,
            'estatus': 'vigente',
            'fecha_emision': {'$gte': fecha_inicio, '$lte': fecha_fin}
        }
        
        cfdis = await db.cfdis.find(query, {'_id': 0}).to_list(100)
        
        best_score = 0
        best_cfdi = None
        
        for cfdi in cfdis:
            cfdi_total = cfdi.get('total', 0)
            monto_cubierto = cfdi.get('monto_cobrado' if cfdi_tipo == 'ingreso' else 'monto_pagado', 0) or 0
            saldo_pendiente = cfdi_total - monto_cubierto
            
            if saldo_pendiente < 0.01:
                continue
            
            score = 0
            if monto > 0 and saldo_pendiente > 0:
                diff_pct = abs(monto - saldo_pendiente) / saldo_pendiente * 100
                if diff_pct < 0.5:
                    score += 50
                elif diff_pct < 2:
                    score += 35
                elif diff_pct < 5:
                    score += 20
                elif diff_pct < 10:
                    score += 10
                else:
                    continue
            
            # Date proximity
            cfdi_fecha_str = cfdi.get('fecha_emision')
            if cfdi_fecha_str:
                try:
                    cfdi_fecha = datetime.fromisoformat(cfdi_fecha_str.replace('Z', '+00:00')) if isinstance(cfdi_fecha_str, str) else cfdi_fecha_str
                    days_diff = abs((fecha_txn - cfdi_fecha).days)
                    if days_diff <= 7:
                        score += 30
                    elif days_diff <= 15:
                        score += 20
                    elif days_diff <= 30:
                        score += 10
                    else:
                        score += 5
                except:
                    pass
            
            # Currency match
            if cfdi.get('moneda', 'MXN') == moneda:
                score += 10
            
            if score > best_score:
                best_score = score
                best_cfdi = cfdi
        
        # Only auto-link if confidence is high (score >= 60)
        if best_score >= 60 and best_cfdi:
            matched_cfdi = best_cfdi
            match_info = {
                'auto_detected': True,
                'score': best_score,
                'confidence': 'alta' if best_score >= 60 else 'media'
            }
    
    # Create the payment
    payment_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    payment_doc = {
        'id': payment_id,
        'company_id': company_id,
        'bank_account_id': txn.get('bank_account_id'),
        'cfdi_id': matched_cfdi.get('id') if matched_cfdi else None,
        'tipo': tipo,
        'concepto': txn.get('descripcion') or f"Movimiento bancario {txn.get('referencia', '')}",
        'monto': txn.get('monto', 0),
        'moneda': moneda,
        'metodo_pago': 'transferencia',
        'fecha_vencimiento': txn.get('fecha_movimiento'),
        'fecha_pago': now.isoformat(),
        'estatus': 'completado',
        'referencia': txn.get('referencia', ''),
        'beneficiario': txn.get('merchant_name') or txn.get('descripcion', '')[:50] if txn.get('descripcion') else '',
        'es_real': True,
        'bank_transaction_id': bank_transaction_id,
        'created_at': now.isoformat()
    }
    
    # Get historical exchange rate for non-MXN currencies
    if moneda != 'MXN':
        rate = await db.fx_rates.find_one(
            {'company_id': company_id, '$or': [
                {'moneda_cotizada': moneda},
                {'moneda_origen': moneda}
            ]},
            {'_id': 0},
            sort=[('fecha_vigencia', -1)]
        )
        if rate:
            payment_doc['tipo_cambio_historico'] = rate.get('tipo_cambio') or rate.get('tasa') or 1
        else:
            default_rates = {'USD': 17.50, 'EUR': 19.00}
            payment_doc['tipo_cambio_historico'] = default_rates.get(moneda, 1)
    
    await db.payments.insert_one(payment_doc)
    
    # Update CFDI if linked
    if matched_cfdi:
        if tipo == 'cobro':
            current_cobrado = matched_cfdi.get('monto_cobrado', 0) or 0
            new_cobrado = current_cobrado + payment_doc['monto']
            await db.cfdis.update_one(
                {'id': matched_cfdi['id']},
                {'$set': {'monto_cobrado': new_cobrado}}
            )
        else:
            current_pagado = matched_cfdi.get('monto_pagado', 0) or 0
            new_pagado = current_pagado + payment_doc['monto']
            await db.cfdis.update_one(
                {'id': matched_cfdi['id']},
                {'$set': {'monto_pagado': new_pagado}}
            )
    
    # Mark bank transaction as reconciled
    await db.bank_transactions.update_one(
        {'id': bank_transaction_id},
        {'$set': {
            'conciliado': True,
            'payment_id': payment_id,
            'fecha_conciliacion': now.isoformat()
        }}
    )
    
    # Create reconciliation record
    recon_doc = {
        'id': str(uuid.uuid4()),
        'company_id': company_id,
        'bank_transaction_id': bank_transaction_id,
        'cfdi_id': matched_cfdi.get('id') if matched_cfdi else None,
        'metodo_conciliacion': 'automatica' if match_info else 'manual',
        'tipo_conciliacion': 'con_uuid' if matched_cfdi else 'sin_uuid',
        'porcentaje_match': match_info.get('score', 100) if match_info else 100,
        'fecha_conciliacion': now.isoformat(),
        'user_id': current_user['id'],
        'notas': f"Creado desde módulo Cobranza y Pagos. {'Auto-detectado.' if match_info else ''}",
        'created_at': now.isoformat()
    }
    await db.reconciliations.insert_one(recon_doc)
    
    await audit_log(company_id, 'Payment', payment_id, 'CREATE_FROM_BANK', current_user['id'])
    
    return {
        'status': 'success',
        'payment_id': payment_id,
        'payment_tipo': tipo,
        'payment_monto': payment_doc['monto'],
        'cfdi_linked': matched_cfdi is not None,
        'cfdi_id': matched_cfdi.get('id') if matched_cfdi else None,
        'cfdi_uuid': matched_cfdi.get('uuid') if matched_cfdi else None,
        'match_info': match_info,
        'message': f"{'Cobro' if tipo == 'cobro' else 'Pago'} creado" + 
                   (f" y vinculado a CFDI {matched_cfdi.get('uuid', '')[:8]}..." if matched_cfdi else " sin CFDI asociado")
    }


@router.post("/bank-transactions/batch-create-payments")
async def batch_create_payments_from_bank(
    request: Request,
    data: dict,
    current_user: Dict = Depends(get_current_user)
):
    """
    Create multiple payments from bank transactions with automatic CFDI matching.
    Expects: { "transaction_ids": ["id1", "id2", ...], "auto_detect": true }
    """
    company_id = await get_active_company_id(request, current_user)
    
    transaction_ids = data.get('transaction_ids', [])
    auto_detect = data.get('auto_detect', True)
    
    if not transaction_ids:
        raise HTTPException(status_code=400, detail="Se requiere al menos un ID de transacción")
    
    results = []
    created = 0
    linked_with_cfdi = 0
    errors = 0
    
    for txn_id in transaction_ids:
        try:
            # Check if payment already exists for this bank transaction (prevent duplicates)
            existing_payment = await db.payments.find_one({
                'company_id': company_id,
                'bank_transaction_id': txn_id
            }, {'_id': 0, 'id': 1})
            
            if existing_payment:
                results.append({'transaction_id': txn_id, 'status': 'skipped', 'message': 'Ya tiene pago creado'})
                continue
            
            # Get the bank transaction
            txn = await db.bank_transactions.find_one({'id': txn_id, 'company_id': company_id}, {'_id': 0})
            if not txn:
                results.append({'transaction_id': txn_id, 'status': 'error', 'message': 'No encontrado'})
                errors += 1
                continue
            
            if txn.get('conciliado'):
                results.append({'transaction_id': txn_id, 'status': 'skipped', 'message': 'Ya conciliado'})
                continue
            
            # Get bank account info
            bank_account = await db.bank_accounts.find_one({'id': txn.get('bank_account_id')}, {'_id': 0})
            moneda = txn.get('moneda') or (bank_account.get('moneda') if bank_account else 'MXN')
            
            # Determine payment type
            tipo = 'cobro' if txn.get('tipo_movimiento') == 'credito' else 'pago'
            
            # Try to find matching CFDI if auto_detect is enabled
            matched_cfdi = None
            if auto_detect:
                monto = txn.get('monto', 0)
                fecha_txn_str = txn.get('fecha_movimiento')
                tipo_movimiento = txn.get('tipo_movimiento', 'credito')
                
                if isinstance(fecha_txn_str, str):
                    try:
                        fecha_txn = datetime.fromisoformat(fecha_txn_str.replace('Z', '+00:00'))
                    except:
                        fecha_txn = datetime.now(timezone.utc)
                else:
                    fecha_txn = fecha_txn_str or datetime.now(timezone.utc)
                
                fecha_inicio = (fecha_txn - timedelta(days=60)).isoformat()
                fecha_fin = (fecha_txn + timedelta(days=60)).isoformat()
                
                cfdi_tipo = 'ingreso' if tipo_movimiento == 'credito' else 'egreso'
                
                query = {
                    'company_id': company_id,
                    'tipo_cfdi': cfdi_tipo,
                    'estatus': 'vigente',
                    'fecha_emision': {'$gte': fecha_inicio, '$lte': fecha_fin}
                }
                
                cfdis = await db.cfdis.find(query, {'_id': 0}).to_list(50)
                
                best_score = 0
                best_cfdi = None
                
                for cfdi in cfdis:
                    cfdi_total = cfdi.get('total', 0)
                    monto_cubierto = cfdi.get('monto_cobrado' if cfdi_tipo == 'ingreso' else 'monto_pagado', 0) or 0
                    saldo_pendiente = cfdi_total - monto_cubierto
                    
                    if saldo_pendiente < 0.01:
                        continue
                    
                    score = 0
                    if monto > 0 and saldo_pendiente > 0:
                        diff_pct = abs(monto - saldo_pendiente) / saldo_pendiente * 100
                        if diff_pct < 0.5:
                            score += 50
                        elif diff_pct < 2:
                            score += 35
                        elif diff_pct < 5:
                            score += 20
                        elif diff_pct < 10:
                            score += 10
                        else:
                            continue
                    
                    cfdi_fecha_str = cfdi.get('fecha_emision')
                    if cfdi_fecha_str:
                        try:
                            cfdi_fecha = datetime.fromisoformat(cfdi_fecha_str.replace('Z', '+00:00')) if isinstance(cfdi_fecha_str, str) else cfdi_fecha_str
                            days_diff = abs((fecha_txn - cfdi_fecha).days)
                            if days_diff <= 7:
                                score += 30
                            elif days_diff <= 15:
                                score += 20
                            elif days_diff <= 30:
                                score += 10
                            else:
                                score += 5
                        except:
                            pass
                    
                    if cfdi.get('moneda', 'MXN') == moneda:
                        score += 10
                    
                    if score > best_score:
                        best_score = score
                        best_cfdi = cfdi
                
                if best_score >= 60 and best_cfdi:
                    matched_cfdi = best_cfdi
            
            # Create the payment
            payment_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            
            payment_doc = {
                'id': payment_id,
                'company_id': company_id,
                'bank_account_id': txn.get('bank_account_id'),
                'cfdi_id': matched_cfdi.get('id') if matched_cfdi else None,
                'tipo': tipo,
                'concepto': txn.get('descripcion') or f"Movimiento bancario {txn.get('referencia', '')}",
                'monto': txn.get('monto', 0),
                'moneda': moneda,
                'metodo_pago': 'transferencia',
                'fecha_vencimiento': txn.get('fecha_movimiento'),
                'fecha_pago': now.isoformat(),
                'estatus': 'completado',
                'referencia': txn.get('referencia', ''),
                'beneficiario': txn.get('merchant_name') or (txn.get('descripcion', '')[:50] if txn.get('descripcion') else ''),
                'es_real': True,
                'bank_transaction_id': txn_id,
                'created_at': now.isoformat()
            }
            
            await db.payments.insert_one(payment_doc)
            
            # Update CFDI if linked
            if matched_cfdi:
                if tipo == 'cobro':
                    current_cobrado = matched_cfdi.get('monto_cobrado', 0) or 0
                    new_cobrado = current_cobrado + payment_doc['monto']
                    await db.cfdis.update_one(
                        {'id': matched_cfdi['id']},
                        {'$set': {'monto_cobrado': new_cobrado}}
                    )
                else:
                    current_pagado = matched_cfdi.get('monto_pagado', 0) or 0
                    new_pagado = current_pagado + payment_doc['monto']
                    await db.cfdis.update_one(
                        {'id': matched_cfdi['id']},
                        {'$set': {'monto_pagado': new_pagado}}
                    )
                linked_with_cfdi += 1
            
            # Mark bank transaction as reconciled
            await db.bank_transactions.update_one(
                {'id': txn_id},
                {'$set': {
                    'conciliado': True,
                    'payment_id': payment_id,
                    'fecha_conciliacion': now.isoformat()
                }}
            )
            
            # Create reconciliation record
            recon_doc = {
                'id': str(uuid.uuid4()),
                'company_id': company_id,
                'bank_transaction_id': txn_id,
                'cfdi_id': matched_cfdi.get('id') if matched_cfdi else None,
                'metodo_conciliacion': 'automatica' if matched_cfdi else 'manual',
                'tipo_conciliacion': 'con_uuid' if matched_cfdi else 'sin_uuid',
                'porcentaje_match': 100,
                'fecha_conciliacion': now.isoformat(),
                'user_id': current_user['id'],
                'notas': 'Creado en lote desde módulo Cobranza y Pagos',
                'created_at': now.isoformat()
            }
            await db.reconciliations.insert_one(recon_doc)
            
            created += 1
            results.append({
                'transaction_id': txn_id,
                'payment_id': payment_id,
                'status': 'created',
                'tipo': tipo,
                'cfdi_linked': matched_cfdi is not None,
                'cfdi_uuid': matched_cfdi.get('uuid')[:8] + '...' if matched_cfdi else None
            })
            
        except Exception as e:
            logger.error(f"Error creating payment from txn {txn_id}: {e}")
            results.append({'transaction_id': txn_id, 'status': 'error', 'message': str(e)})
            errors += 1
    
    return {
        'status': 'success',
        'created': created,
        'linked_with_cfdi': linked_with_cfdi,
        'errors': errors,
        'results': results,
        'message': f'Se crearon {created} pagos/cobros' + 
                   (f', {linked_with_cfdi} vinculados con CFDI' if linked_with_cfdi > 0 else '') +
                   (f', {errors} errores' if errors > 0 else '')
    }


# GET /payments moved to routes/payments.py

@router.get("/payments/summary")
async def get_payments_summary(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    fecha_corte: Optional[str] = Query(None, description="Fecha de corte para totales")
):
    company_id = await get_active_company_id(request, current_user)
    
    if not fecha_corte:
        fecha_corte = (datetime.now(timezone.utc) + timedelta(days=15)).isoformat()
    
    # Get current exchange rate for USD -> MXN
    fx_rate_usd = await db.fx_rates.find_one(
        {'moneda_origen': 'USD', 'moneda_destino': 'MXN'},
        sort=[('timestamp', -1)]
    )
    usd_to_mxn = fx_rate_usd['tasa'] if fx_rate_usd else 17.5
    
    fx_rate_eur = await db.fx_rates.find_one(
        {'moneda_origen': 'EUR', 'moneda_destino': 'MXN'},
        sort=[('timestamp', -1)]
    )
    eur_to_mxn = fx_rate_eur['tasa'] if fx_rate_eur else 19.0
    
    def convert_to_mxn(monto, moneda):
        """Convert amount to MXN"""
        if not monto:
            return 0
        if moneda == 'USD':
            return monto * usd_to_mxn
        elif moneda == 'EUR':
            return monto * eur_to_mxn
        return monto  # Already MXN
    
    # Get all CFDIs to calculate pending amounts
    all_cfdis = await db.cfdis.find({
        'company_id': company_id,
        'estado_cancelacion': {'$ne': 'cancelado'}
    }, {'_id': 0}).to_list(5000)
    
    # Calculate pending amounts from CFDIs by currency
    total_por_cobrar_mxn = 0
    total_por_cobrar_usd = 0
    total_por_pagar_mxn = 0
    total_por_pagar_usd = 0
    cobros_pendientes_count = 0
    pagos_pendientes_count = 0
    
    for cfdi in all_cfdis:
        total = cfdi.get('total', 0) or 0
        moneda = cfdi.get('moneda', 'MXN')
        tipo = cfdi.get('tipo', '')
        
        if tipo == 'ingreso':
            monto_cobrado = cfdi.get('monto_cobrado', 0) or 0
            pendiente = total - monto_cobrado
            if pendiente > 0.01:
                if moneda == 'USD':
                    total_por_cobrar_usd += pendiente
                else:
                    total_por_cobrar_mxn += pendiente
                cobros_pendientes_count += 1
        elif tipo == 'egreso':
            monto_pagado = cfdi.get('monto_pagado', 0) or 0
            pendiente = total - monto_pagado
            if pendiente > 0.01:
                if moneda == 'USD':
                    total_por_pagar_usd += pendiente
                else:
                    total_por_pagar_mxn += pendiente
                pagos_pendientes_count += 1
    
    # Get completed payments this month by currency
    start_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    completed_payments = await db.payments.find({
        'company_id': company_id,
        'estatus': 'completado',
        'fecha_pago': {'$gte': start_of_month.isoformat()}
    }, {'_id': 0}).to_list(1000)
    
    # Calculate paid/collected this month by currency
    pagado_mes_mxn = 0
    pagado_mes_usd = 0
    cobrado_mes_mxn = 0
    cobrado_mes_usd = 0
    
    for p in completed_payments:
        monto = p.get('monto', 0) or 0
        moneda = p.get('moneda', 'MXN')
        if p['tipo'] == 'pago':
            if moneda == 'USD':
                pagado_mes_usd += monto
            else:
                pagado_mes_mxn += monto
        else:  # cobro
            if moneda == 'USD':
                cobrado_mes_usd += monto
            else:
                cobrado_mes_mxn += monto
    
    # Get pending payments with domiciliacion
    pending_payments = await db.payments.find({
        'company_id': company_id,
        'estatus': 'pendiente'
    }, {'_id': 0}).to_list(1000)
    
    domiciliados = [p for p in pending_payments if p.get('domiciliacion_activa')]
    monto_domiciliado = sum(
        convert_to_mxn(p['monto'], p.get('moneda', 'MXN')) 
        for p in domiciliados
    )
    
    # Calculate totals in MXN
    total_por_cobrar_total = total_por_cobrar_mxn + convert_to_mxn(total_por_cobrar_usd, 'USD')
    total_por_pagar_total = total_por_pagar_mxn + convert_to_mxn(total_por_pagar_usd, 'USD')
    total_pagado_mes = pagado_mes_mxn + convert_to_mxn(pagado_mes_usd, 'USD')
    total_cobrado_mes = cobrado_mes_mxn + convert_to_mxn(cobrado_mes_usd, 'USD')
    
    return {
        'fecha_corte': fecha_corte,
        'total_por_pagar': round(total_por_pagar_total, 2),
        'total_por_pagar_mxn': round(total_por_pagar_mxn, 2),
        'total_por_pagar_usd': round(total_por_pagar_usd, 2),
        'total_por_cobrar': round(total_por_cobrar_total, 2),
        'total_por_cobrar_mxn': round(total_por_cobrar_mxn, 2),
        'total_por_cobrar_usd': round(total_por_cobrar_usd, 2),
        'pagos_pendientes': pagos_pendientes_count,
        'cobros_pendientes': cobros_pendientes_count,
        'total_pagado_mes': round(total_pagado_mes, 2),
        'pagado_mes_mxn': round(pagado_mes_mxn, 2),
        'pagado_mes_usd': round(pagado_mes_usd, 2),
        'total_cobrado_mes': round(total_cobrado_mes, 2),
        'cobrado_mes_mxn': round(cobrado_mes_mxn, 2),
        'cobrado_mes_usd': round(cobrado_mes_usd, 2),
        'domiciliaciones_activas': len(domiciliados),
        'monto_domiciliado': round(monto_domiciliado, 2),
        'tc_usd': usd_to_mxn,
        'tc_eur': eur_to_mxn
    }


@router.get("/payments/breakdown")
async def get_payments_breakdown(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get complete breakdown for Cobranza y Pagos module.
    
    Source of truth: Bank reconciliations
    - Cobrado = Reconciled deposits (créditos)
    - Pagado = Reconciled withdrawals (débitos)
    - Por Cobrar / Por Pagar = From CFDIs pending
    - Proyecciones = For variance analysis
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Get FX rates
    fx_rate_usd = await db.fx_rates.find_one(
        {'company_id': company_id, '$or': [{'moneda_cotizada': 'USD'}, {'moneda_origen': 'USD'}]},
        {'_id': 0},
        sort=[('fecha_vigencia', -1)]
    )
    usd_to_mxn = fx_rate_usd.get('tipo_cambio') or fx_rate_usd.get('tasa') if fx_rate_usd else 17.5
    
    def convert_to_mxn(monto, moneda):
        if not monto:
            return 0
        if moneda == 'USD':
            return monto * usd_to_mxn
        return monto
    
    # ===== SECTION 1: FROM CFDI / SAT (PENDING) =====
    all_cfdis = await db.cfdis.find({
        'company_id': company_id,
        'estatus': 'vigente'
    }, {'_id': 0}).to_list(5000)
    
    por_cobrar_list = []
    total_por_cobrar_mxn = 0
    total_por_cobrar_usd = 0
    
    por_pagar_list = []
    total_por_pagar_mxn = 0
    total_por_pagar_usd = 0
    
    for cfdi in all_cfdis:
        total = cfdi.get('total', 0) or 0
        moneda = cfdi.get('moneda', 'MXN')
        tipo_cfdi = cfdi.get('tipo_cfdi', cfdi.get('tipo', ''))
        
        if tipo_cfdi == 'ingreso':
            monto_cobrado = cfdi.get('monto_cobrado', 0) or 0
            pendiente = total - monto_cobrado
            if pendiente > 0.01:
                por_cobrar_list.append({
                    'cfdi_id': cfdi.get('id'),
                    'uuid': cfdi.get('uuid', '')[:8] + '...' if cfdi.get('uuid') else '',
                    'emisor': cfdi.get('emisor_nombre', ''),
                    'receptor': cfdi.get('receptor_nombre', ''),
                    'fecha': cfdi.get('fecha_emision'),
                    'total': total,
                    'cobrado': monto_cobrado,
                    'pendiente': pendiente,
                    'moneda': moneda
                })
                if moneda == 'USD':
                    total_por_cobrar_usd += pendiente
                else:
                    total_por_cobrar_mxn += pendiente
                    
        elif tipo_cfdi == 'egreso':
            monto_pagado = cfdi.get('monto_pagado', 0) or 0
            pendiente = total - monto_pagado
            if pendiente > 0.01:
                por_pagar_list.append({
                    'cfdi_id': cfdi.get('id'),
                    'uuid': cfdi.get('uuid', '')[:8] + '...' if cfdi.get('uuid') else '',
                    'emisor': cfdi.get('emisor_nombre', ''),
                    'receptor': cfdi.get('receptor_nombre', ''),
                    'fecha': cfdi.get('fecha_emision'),
                    'total': total,
                    'pagado': monto_pagado,
                    'pendiente': pendiente,
                    'moneda': moneda
                })
                if moneda == 'USD':
                    total_por_pagar_usd += pendiente
                else:
                    total_por_pagar_mxn += pendiente
    
    # ===== SECTION 2: FROM BANK RECONCILIATIONS (SOURCE OF TRUTH) =====
    # Get all reconciled bank transactions
    reconciled_txns = await db.bank_transactions.find({
        'company_id': company_id,
        'conciliado': True
    }, {'_id': 0}).to_list(10000)
    
    # Get reconciliation details
    all_reconciliations = await db.reconciliations.find({
        'company_id': company_id
    }, {'_id': 0}).to_list(10000)
    
    recon_by_txn = {r.get('bank_transaction_id'): r for r in all_reconciliations}
    
    # Get bank accounts for reference
    bank_accounts = await db.bank_accounts.find({'company_id': company_id}, {'_id': 0}).to_list(100)
    account_map = {a['id']: a for a in bank_accounts}
    
    # Cobrado (deposits = créditos conciliados)
    cobrado_list = []
    total_cobrado_mxn = 0
    total_cobrado_usd = 0
    cobrado_con_cfdi_count = 0
    cobrado_sin_cfdi_count = 0
    
    # Pagado (withdrawals = débitos conciliados)
    pagado_list = []
    total_pagado_mxn = 0
    total_pagado_usd = 0
    pagado_con_cfdi_count = 0
    pagado_sin_cfdi_count = 0
    
    for txn in reconciled_txns:
        monto = txn.get('monto', 0) or 0
        moneda = txn.get('moneda', 'MXN')
        tipo_mov = txn.get('tipo_movimiento', '')
        
        # Get account info
        account = account_map.get(txn.get('bank_account_id'), {})
        banco = account.get('banco', '')
        cuenta_nombre = account.get('nombre', '')
        
        # Get reconciliation info
        recon = recon_by_txn.get(txn.get('id'), {})
        cfdi_id = recon.get('cfdi_id')
        tipo_conciliacion = recon.get('tipo_conciliacion', 'sin_uuid')
        
        item = {
            'id': txn.get('id'),
            'fecha': txn.get('fecha_movimiento'),
            'descripcion': txn.get('descripcion', '')[:80],
            'referencia': txn.get('referencia', ''),
            'monto': monto,
            'moneda': moneda,
            'banco': banco,
            'cuenta': cuenta_nombre,
            'cfdi_id': cfdi_id,
            'tipo_conciliacion': tipo_conciliacion,
            'tiene_cfdi': cfdi_id is not None
        }
        
        if tipo_mov == 'credito':
            # Deposit = Cobrado
            cobrado_list.append(item)
            if moneda == 'USD':
                total_cobrado_usd += monto
            else:
                total_cobrado_mxn += monto
            
            if cfdi_id:
                cobrado_con_cfdi_count += 1
            else:
                cobrado_sin_cfdi_count += 1
        else:
            # Withdrawal = Pagado
            pagado_list.append(item)
            if moneda == 'USD':
                total_pagado_usd += monto
            else:
                total_pagado_mxn += monto
            
            if cfdi_id:
                pagado_con_cfdi_count += 1
            else:
                pagado_sin_cfdi_count += 1
    
    # Sort by date descending
    cobrado_list.sort(key=lambda x: x.get('fecha', ''), reverse=True)
    pagado_list.sort(key=lambda x: x.get('fecha', ''), reverse=True)
    
    # ===== SECTION 3: PROJECTIONS =====
    projections = await db.manual_projections.find({
        'company_id': company_id,
        'activo': True
    }, {'_id': 0}).to_list(500)
    
    proyeccion_cobros = []
    proyeccion_pagos = []
    total_proyeccion_cobros_mxn = 0
    total_proyeccion_pagos_mxn = 0
    
    for proj in projections:
        monto = proj.get('monto', 0) or 0
        moneda = proj.get('moneda', 'MXN')
        tipo = proj.get('tipo', 'egreso')
        
        item = {
            'id': proj.get('id'),
            'nombre': proj.get('nombre', ''),
            'monto': monto,
            'moneda': moneda,
            'semana': proj.get('semana'),
            'mes': proj.get('mes'),
            'recurrente': proj.get('recurrente', False),
            'categoria': proj.get('categoria', '')
        }
        
        monto_mxn = convert_to_mxn(monto, moneda)
        
        if tipo == 'ingreso':
            proyeccion_cobros.append(item)
            total_proyeccion_cobros_mxn += monto_mxn
        else:
            proyeccion_pagos.append(item)
            total_proyeccion_pagos_mxn += monto_mxn
    
    # ===== CALCULATE VARIANCE =====
    total_real_cobros = total_cobrado_mxn + convert_to_mxn(total_cobrado_usd, 'USD')
    total_real_pagos = total_pagado_mxn + convert_to_mxn(total_pagado_usd, 'USD')
    
    varianza_cobros = total_real_cobros - total_proyeccion_cobros_mxn
    varianza_pagos = total_real_pagos - total_proyeccion_pagos_mxn
    
    return {
        # Section 1: Por Cobrar / Por Pagar (from CFDI/SAT - PENDING)
        'cfdi_por_cobrar': {
            'items': por_cobrar_list[:50],
            'total_count': len(por_cobrar_list),
            'total_mxn': round(total_por_cobrar_mxn, 2),
            'total_usd': round(total_por_cobrar_usd, 2),
            'total_equiv_mxn': round(total_por_cobrar_mxn + convert_to_mxn(total_por_cobrar_usd, 'USD'), 2)
        },
        'cfdi_por_pagar': {
            'items': por_pagar_list[:50],
            'total_count': len(por_pagar_list),
            'total_mxn': round(total_por_pagar_mxn, 2),
            'total_usd': round(total_por_pagar_usd, 2),
            'total_equiv_mxn': round(total_por_pagar_mxn + convert_to_mxn(total_por_pagar_usd, 'USD'), 2)
        },
        
        # Section 2: Cobrado / Pagado (from RECONCILED bank transactions - SOURCE OF TRUTH)
        'cobrado': {
            'items': cobrado_list[:100],
            'total_count': len(cobrado_list),
            'total_mxn': round(total_cobrado_mxn, 2),
            'total_usd': round(total_cobrado_usd, 2),
            'total_equiv_mxn': round(total_cobrado_mxn + convert_to_mxn(total_cobrado_usd, 'USD'), 2),
            'con_cfdi': cobrado_con_cfdi_count,
            'sin_cfdi': cobrado_sin_cfdi_count
        },
        'pagado': {
            'items': pagado_list[:100],
            'total_count': len(pagado_list),
            'total_mxn': round(total_pagado_mxn, 2),
            'total_usd': round(total_pagado_usd, 2),
            'total_equiv_mxn': round(total_pagado_mxn + convert_to_mxn(total_pagado_usd, 'USD'), 2),
            'con_cfdi': pagado_con_cfdi_count,
            'sin_cfdi': pagado_sin_cfdi_count
        },
        
        # Section 3: Proyecciones
        'proyeccion_cobros': {
            'items': proyeccion_cobros[:50],
            'total_count': len(proyeccion_cobros),
            'total_equiv_mxn': round(total_proyeccion_cobros_mxn, 2)
        },
        'proyeccion_pagos': {
            'items': proyeccion_pagos[:50],
            'total_count': len(proyeccion_pagos),
            'total_equiv_mxn': round(total_proyeccion_pagos_mxn, 2)
        },
        
        # Section 4: Variance Summary
        'varianza': {
            'cobros_real_vs_proyectado': round(varianza_cobros, 2),
            'cobros_pct': round((varianza_cobros / total_proyeccion_cobros_mxn * 100), 1) if total_proyeccion_cobros_mxn > 0 else 0,
            'pagos_real_vs_proyectado': round(varianza_pagos, 2),
            'pagos_pct': round((varianza_pagos / total_proyeccion_pagos_mxn * 100), 1) if total_proyeccion_pagos_mxn > 0 else 0,
            'flujo_neto_real': round(total_real_cobros - total_real_pagos, 2),
            'flujo_neto_proyectado': round(total_proyeccion_cobros_mxn - total_proyeccion_pagos_mxn, 2)
        },
        
        'tc_usd': usd_to_mxn
    }

# PUT /payments/{id}, POST /payments/{id}/complete, DELETE /payments/{id}, DELETE /payments/bulk/all
# moved to routes/payments.py

# DELETE /reconciliations/bulk/all moved to routes/reconciliations.py

# ==================== CATEGORIES/SUBCATEGORIES ENDPOINTS MOVED TO routes/categories.py ====================
# The following endpoints are now handled by routes/categories.py:
# - GET /categories
# - POST /categories
# - PUT /categories/{category_id}
# - DELETE /categories/{category_id}
# - POST /subcategories
# - DELETE /subcategories/{subcategory_id}


# ===== CATEGORIZACIÓN AUTOMÁTICA CON IA =====
from ai_categorization_service import categorize_cfdi_with_ai, batch_categorize_cfdis

