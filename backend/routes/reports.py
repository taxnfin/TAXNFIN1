"""Reports, dashboard and audit log routes"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id
from services.fx import get_fx_rate_by_date
from models.enums import UserRole
from models.audit import AuditLog

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/audit-logs", response_model=List[AuditLog])
async def list_audit_logs(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    limit: int = Query(100, le=1000),
    skip: int = Query(0, ge=0),
    entidad: Optional[str] = Query(None, description="Filter by entity type (cfdi, payment, etc)"),
    accion: Optional[str] = Query(None, description="Filter by action (e.g. fx_corrected_to_dof)"),
    user_id: Optional[str] = Query(None, description="Filter by user id/email"),
    fecha_desde: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    fecha_hasta: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
):
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    company_id = await get_active_company_id(request, current_user)
    query: Dict[str, Any] = {'company_id': company_id}
    if entidad:
        query['entidad'] = entidad
    if accion:
        query['accion'] = accion
    if user_id:
        query['user_id'] = user_id
    if fecha_desde or fecha_hasta:
        ts: Dict[str, Any] = {}
        if fecha_desde:
            ts['$gte'] = fecha_desde + 'T00:00:00'
        if fecha_hasta:
            ts['$lte'] = fecha_hasta + 'T23:59:59'
        query['timestamp'] = ts
    
    logs = await db.audit_logs.find(query, {'_id': 0}).sort('timestamp', -1).skip(skip).limit(limit).to_list(limit)
    
    for log in logs:
        if isinstance(log.get('timestamp'), str):
            log['timestamp'] = datetime.fromisoformat(log['timestamp'])
    return logs


@router.get("/audit-logs/distinct")
async def audit_logs_distinct(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Return distinct values of entidad/accion/user_id for the company.
    Used to populate filter dropdowns in the Bitácora UI."""
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    company_id = await get_active_company_id(request, current_user)
    base = {'company_id': company_id}
    return {
        'entidades': sorted([v for v in await db.audit_logs.distinct('entidad', base) if v]),
        'acciones': sorted([v for v in await db.audit_logs.distinct('accion', base) if v]),
        'usuarios': sorted([v for v in await db.audit_logs.distinct('user_id', base) if v]),
    }

@router.get("/reports/dashboard")
async def get_dashboard_report(
    request: Request, 
    current_user: Dict = Depends(get_current_user),
    moneda_vista: str = Query('MXN', description='Moneda para mostrar datos'),
    bank_account_id: str = Query(None, description='Filtrar por cuenta bancaria específica'),
    fecha_desde: str = Query(None, description='Fecha inicio del rango (YYYY-MM-DD)'),
    fecha_hasta: str = Query(None, description='Fecha fin del rango (YYYY-MM-DD)')
):
    company_id = await get_active_company_id(request, current_user)
    
    # Get FX rates for conversion
    fx_rates = await db.fx_rates.find(
        {'company_id': company_id},
        {'_id': 0, 'moneda_origen': 1, 'moneda_destino': 1, 'tasa': 1}
    ).sort('fecha_vigencia', -1).to_list(100)
    
    # Build FX rates map (moneda -> MXN rate)
    fx_map = {'MXN': 1.0}
    for rate in fx_rates:
        if rate.get('moneda_destino') == 'MXN':
            fx_map[rate['moneda_origen']] = rate['tasa']
        elif rate.get('moneda_origen') == 'MXN':
            fx_map[rate['moneda_destino']] = 1 / rate['tasa']
    
    # Also check for rates stored by the forex sync service
    synced_rates = await db.fx_rates.find(
        {'company_id': company_id, 'fuente': {'$in': ['banxico', 'openexchange', 'fallback']}},
        {'_id': 0, 'moneda_origen': 1, 'tasa': 1, 'fuente': 1}
    ).sort('updated_at', -1).to_list(20)
    
    for rate in synced_rates:
        currency = rate.get('moneda_origen')
        if currency and currency not in fx_map:
            fx_map[currency] = rate['tasa']
    
    # Default rates for common currencies if not configured
    default_fx_rates = {
        'USD': 17.50,
        'EUR': 19.00,
        'GBP': 22.00,
        'JPY': 0.12,
        'CHF': 19.50,
        'CAD': 12.80,
        'CNY': 2.45
    }
    for currency, rate in default_fx_rates.items():
        if currency not in fx_map:
            fx_map[currency] = rate
    
    # Conversion factor from MXN to target currency
    target_rate = fx_map.get(moneda_vista, 1.0)
    def convert_to_target(mxn_amount):
        if moneda_vista == 'MXN':
            return mxn_amount
        return mxn_amount / target_rate
    
    # Get bank accounts
    bank_query = {'company_id': company_id}
    if bank_account_id:
        bank_query['id'] = bank_account_id
    
    bank_accounts = await db.bank_accounts.find(bank_query, {'_id': 0}).to_list(100)
    
    # Calculate saldos with conversion
    saldo_inicial_mxn = 0.0
    cash_pool_by_currency = {}
    accounts_detail = []
    
    for acc in bank_accounts:
        saldo = acc.get('saldo_inicial', 0)
        moneda = acc.get('moneda', 'MXN')
        tasa = fx_map.get(moneda, 1.0)
        saldo_mxn = saldo * tasa
        saldo_target = convert_to_target(saldo_mxn)
        
        # Cash pooling by currency
        if moneda not in cash_pool_by_currency:
            cash_pool_by_currency[moneda] = {'total': 0, 'cuentas': 0}
        cash_pool_by_currency[moneda]['total'] += saldo
        cash_pool_by_currency[moneda]['cuentas'] += 1
        
        acc['saldo_mxn'] = saldo_mxn
        acc['saldo_target'] = saldo_target
        acc['tasa_conversion'] = tasa
        
        # Risk indicators
        acc['riesgo_ocioso'] = saldo > 500000  # More than 500k idle
        acc['riesgo_bajo_saldo'] = saldo < 10000  # Less than 10k
        
        accounts_detail.append(acc)
        saldo_inicial_mxn += saldo_mxn
    
    saldo_inicial_target = convert_to_target(saldo_inicial_mxn)
    
    # Build date filter for cashflow weeks
    weeks_query = {'company_id': company_id}
    
    # Parse date filters if provided (convert YYYY-MM-DD to datetime for comparison)
    if fecha_desde:
        try:
            from datetime import datetime
            fecha_desde_dt = datetime.fromisoformat(fecha_desde + 'T00:00:00+00:00')
            weeks_query['fecha_inicio'] = {'$gte': fecha_desde_dt.isoformat()}
        except:
            pass  # Ignore invalid date format
    
    if fecha_hasta:
        try:
            from datetime import datetime
            fecha_hasta_dt = datetime.fromisoformat(fecha_hasta + 'T23:59:59+00:00')
            if 'fecha_fin' not in weeks_query:
                weeks_query['fecha_fin'] = {}
            weeks_query['fecha_fin'] = {'$lte': fecha_hasta_dt.isoformat()}
        except:
            pass  # Ignore invalid date format
    
    # Get cashflow weeks with date filter
    weeks = await db.cashflow_weeks.find(
        weeks_query,
        {'_id': 0}
    ).sort('fecha_inicio', 1).limit(52).to_list(52)  # Up to 1 year of weeks
    
    running_balance_mxn = saldo_inicial_mxn
    previous_flujo_neto = 0
    
    for idx, week in enumerate(weeks):
        txn_query = {'company_id': company_id, 'cashflow_week_id': week['id']}
        if bank_account_id:
            txn_query['bank_account_id'] = bank_account_id
        
        transactions = await db.transactions.find(txn_query, {'_id': 0}).to_list(1000)
        
        total_ingresos_mxn = sum(t['monto'] for t in transactions if t['tipo_transaccion'] == 'ingreso')
        total_egresos_mxn = sum(t['monto'] for t in transactions if t['tipo_transaccion'] == 'egreso')
        flujo_neto_mxn = total_ingresos_mxn - total_egresos_mxn
        
        week['saldo_inicial_mxn'] = running_balance_mxn
        week['saldo_inicial'] = convert_to_target(running_balance_mxn)
        week['total_ingresos_mxn'] = total_ingresos_mxn
        week['total_ingresos'] = convert_to_target(total_ingresos_mxn)
        week['total_egresos_mxn'] = total_egresos_mxn
        week['total_egresos'] = convert_to_target(total_egresos_mxn)
        week['flujo_neto_mxn'] = flujo_neto_mxn
        week['flujo_neto'] = convert_to_target(flujo_neto_mxn)
        week['saldo_final_mxn'] = running_balance_mxn + flujo_neto_mxn
        week['saldo_final'] = convert_to_target(week['saldo_final_mxn'])
        
        # Variance calculation (vs previous week)
        if idx > 0:
            week['varianza_flujo'] = flujo_neto_mxn - previous_flujo_neto
            week['varianza_pct'] = (week['varianza_flujo'] / abs(previous_flujo_neto) * 100) if previous_flujo_neto != 0 else 0
        else:
            week['varianza_flujo'] = 0
            week['varianza_pct'] = 0
        
        previous_flujo_neto = flujo_neto_mxn
        running_balance_mxn = week['saldo_final_mxn']
    
    # Calculate trends and risk indicators
    if len(weeks) >= 4:
        recent_flows = [w['flujo_neto_mxn'] for w in weeks[-4:]]
        trend_direction = 'up' if recent_flows[-1] > recent_flows[0] else 'down' if recent_flows[-1] < recent_flows[0] else 'stable'
        avg_flow = sum(recent_flows) / len(recent_flows)
    else:
        trend_direction = 'stable'
        avg_flow = 0
    
    # Risk indicators
    saldo_final_proyectado = weeks[-1]['saldo_final_mxn'] if weeks else saldo_inicial_mxn
    risk_indicators = {
        'liquidez_critica': saldo_final_proyectado < 50000,
        'tendencia_negativa': trend_direction == 'down' and avg_flow < 0,
        'saldos_ociosos': sum(1 for acc in accounts_detail if acc.get('riesgo_ocioso', False)),
        'cuentas_bajo_saldo': sum(1 for acc in accounts_detail if acc.get('riesgo_bajo_saldo', False)),
        'semanas_con_deficit': sum(1 for w in weeks if w.get('flujo_neto_mxn', 0) < 0)
    }
    
    # KPIs
    total_transactions = await db.transactions.count_documents({'company_id': company_id})
    total_cfdis = await db.cfdis.count_documents({'company_id': company_id})
    total_reconciliations = await db.reconciliations.count_documents({'company_id': company_id})
    total_customers = await db.customers.count_documents({'company_id': company_id})
    total_vendors = await db.vendors.count_documents({'company_id': company_id})
    
    return {
        'moneda_vista': moneda_vista,
        'cashflow_weeks': weeks,
        'saldo_inicial_bancos': saldo_inicial_target,
        'saldo_inicial_bancos_mxn': saldo_inicial_mxn,
        'saldo_final_proyectado': convert_to_target(saldo_final_proyectado),
        'saldo_final_proyectado_mxn': saldo_final_proyectado,
        'bank_accounts': accounts_detail,
        'fx_rates_used': fx_map,
        'cash_pool': cash_pool_by_currency,
        'trend': {
            'direction': trend_direction,
            'avg_flow_4w': convert_to_target(avg_flow),
            'avg_flow_4w_mxn': avg_flow
        },
        'risk_indicators': risk_indicators,
        'kpis': {
            'total_transactions': total_transactions,
            'total_cfdis': total_cfdis,
            'total_reconciliations': total_reconciliations,
            'total_customers': total_customers,
            'total_vendors': total_vendors
        }
    }


@router.get("/reports/dashboard-from-payments")
async def get_dashboard_from_payments(
    request: Request, 
    current_user: Dict = Depends(get_current_user),
    moneda_vista: str = Query('MXN', description='Moneda para mostrar datos'),
    bank_account_id: Optional[str] = Query(None, description='Filtrar por cuenta bancaria específica')
):
    """
    Dashboard alternativo que genera datos directamente desde pagos reales.
    Usa la misma lógica que CashflowProjections para consistencia.
    """
    from datetime import datetime, timedelta
    
    company_id = await get_active_company_id(request, current_user)
    
    # Get FX rates
    fx_rates = await db.fx_rates.find({'company_id': company_id}, {'_id': 0}).to_list(100)
    fx_map = {'MXN': 1.0, 'USD': 17.5, 'EUR': 20.0}
    for rate in fx_rates:
        if rate.get('moneda_destino') == 'MXN' and rate.get('tasa'):
            fx_map[rate['moneda_origen']] = rate['tasa']
    
    def convert_to_mxn(amount, currency):
        return amount * fx_map.get(currency, 1)
    
    def convert_from_mxn(amount_mxn, target_currency):
        """Convert MXN to target currency"""
        if target_currency == 'MXN':
            return amount_mxn
        rate = fx_map.get(target_currency, 1)
        return amount_mxn / rate if rate else amount_mxn
    
    def to_display_currency(amount_mxn):
        """Convert MXN amount to display currency"""
        return convert_from_mxn(amount_mxn, moneda_vista)
    
    # Get bank account balances - use saldo_inicial like bank-accounts/summary does
    accounts_query = {'company_id': company_id}
    if bank_account_id:
        accounts_query['id'] = bank_account_id
    
    accounts = await db.bank_accounts.find(accounts_query, {'_id': 0}).to_list(50)
    
    # Calculate initial balance using fecha_saldo for FX rate
    saldo_bancos_mxn = 0
    selected_account_moneda = 'MXN'
    selected_account_saldo = 0
    
    for acc in accounts:
        saldo = acc.get('saldo_inicial', 0) or 0
        moneda = acc.get('moneda', 'MXN')
        fecha_saldo = acc.get('fecha_saldo')
        
        # Use the FX rate from fecha_saldo date
        if fecha_saldo and moneda != 'MXN':
            if isinstance(fecha_saldo, str):
                fecha_saldo = datetime.fromisoformat(fecha_saldo.replace('Z', '+00:00').split('+')[0])
            rate = await get_fx_rate_by_date(company_id, moneda, fecha_saldo)
        else:
            rate = fx_map.get(moneda, 1) if moneda != 'MXN' else 1
        
        saldo_mxn = saldo * rate if moneda != 'MXN' else saldo
        saldo_bancos_mxn += saldo_mxn
        
        if bank_account_id and acc.get('id') == bank_account_id:
            selected_account_moneda = moneda
            selected_account_saldo = saldo
    
    # Get all bank transactions
    bank_txns_query = {'company_id': company_id}
    if bank_account_id:
        bank_txns_query['bank_account_id'] = bank_account_id
    
    bank_txns = await db.bank_transactions.find(bank_txns_query, {'_id': 0}).to_list(5000)
    reconciled_ids = set(t['id'] for t in bank_txns if t.get('conciliado') == True)
    bank_txn_to_account = {t['id']: t.get('bank_account_id') for t in bank_txns}
    
    all_payments = await db.payments.find({'company_id': company_id, 'estatus': 'completado'}, {'_id': 0}).to_list(5000)
    
    # Filter to valid payments (reconciled or without bank_transaction_id)
    payments = [p for p in all_payments if not p.get('bank_transaction_id') or p.get('bank_transaction_id') in reconciled_ids]
    
    # If filtering by bank account, only include payments for that account
    if bank_account_id:
        payments = [p for p in payments if p.get('bank_transaction_id') and bank_txn_to_account.get(p['bank_transaction_id']) == bank_account_id]
    
    # Get categories for USD operations
    categories = await db.categories.find({'company_id': company_id}, {'_id': 0}).to_list(100)
    compra_usd_id = next((c['id'] for c in categories if 'compra' in c.get('nombre', '').lower() and 'usd' in c.get('nombre', '').lower()), None)
    venta_usd_id = next((c['id'] for c in categories if 'venta' in c.get('nombre', '').lower() and 'usd' in c.get('nombre', '').lower()), None)
    
    # Generate 13 weeks (4 past, current, 8 future)
    today = datetime.now()
    # Find Monday of current week
    days_since_monday = today.weekday()
    current_monday = today - timedelta(days=days_since_monday)
    start_monday = current_monday - timedelta(weeks=4)
    
    weeks_data = []
    running_balance = saldo_bancos_mxn
    
    for i in range(13):
        week_start = start_monday + timedelta(weeks=i)
        week_end = week_start + timedelta(days=7)
        is_past = week_end <= today
        is_current = week_start <= today < week_end
        
        # Filter payments for this week
        week_payments = [p for p in payments if p.get('fecha_pago')]
        week_payments = [p for p in week_payments if week_start <= datetime.fromisoformat(p['fecha_pago'].replace('Z', '+00:00').split('+')[0]) < week_end]
        
        # Calculate totals excluding USD operations
        ingresos = 0
        egresos = 0
        venta_usd = 0
        compra_usd = 0
        
        for p in week_payments:
            monto_mxn = convert_to_mxn(p.get('monto', 0), p.get('moneda', 'MXN'))
            cat_id = p.get('category_id')
            
            if cat_id == venta_usd_id:
                venta_usd += monto_mxn
            elif cat_id == compra_usd_id:
                compra_usd += monto_mxn
            elif p.get('tipo') == 'cobro':
                ingresos += monto_mxn
            else:
                egresos += monto_mxn
        
        flujo_neto = ingresos - egresos + venta_usd - compra_usd
        saldo_final = running_balance + flujo_neto if is_past or is_current else running_balance
        
        weeks_data.append({
            'week_num': i + 1,
            'week_label': f"S{i + 1}",
            'date_label': week_start.strftime('%d %b'),
            'fecha_inicio': week_start.isoformat(),
            'fecha_fin': week_end.isoformat(),
            'is_past': is_past,
            'is_current': is_current,
            'ingresos': round(ingresos, 2),
            'egresos': round(egresos, 2),
            'venta_usd': round(venta_usd, 2),
            'compra_usd': round(compra_usd, 2),
            'flujo_neto': round(flujo_neto, 2),
            'saldo_inicial': round(running_balance, 2),
            'saldo_final': round(saldo_final, 2),
            'num_payments': len(week_payments)
        })
        
        if is_past or is_current:
            running_balance = saldo_final
    
    # Calculate varianza (change vs previous week) for each week
    for i, week in enumerate(weeks_data):
        if i == 0:
            week['varianza'] = 0
            week['varianza_pct'] = 0
        else:
            prev_week = weeks_data[i - 1]
            week['varianza'] = round(week['flujo_neto'] - prev_week['flujo_neto'], 2)
            if prev_week['flujo_neto'] != 0:
                week['varianza_pct'] = round((week['varianza'] / abs(prev_week['flujo_neto'])) * 100, 1)
            else:
                week['varianza_pct'] = 0
    
    # Calculate KPIs
    past_weeks = [w for w in weeks_data if w['is_past'] or w['is_current']]
    total_ingresos = sum(w['ingresos'] + w['venta_usd'] for w in past_weeks)
    total_egresos = sum(w['egresos'] + w['compra_usd'] for w in past_weeks)
    
    burn_rate = total_egresos / len(past_weeks) if past_weeks else 0
    runway_weeks = running_balance / burn_rate if burn_rate > 0 else float('inf')
    
    # Find critical week (first week with negative balance)
    critical_week = None
    for w in weeks_data:
        if w['saldo_final'] < 0:
            critical_week = w['week_label']
            break
    
    # Build cash pool by currency
    cash_pool = {}
    for acc in accounts:
        moneda = acc.get('moneda', 'MXN')
        saldo = acc.get('saldo_inicial', 0) or 0
        if moneda not in cash_pool:
            cash_pool[moneda] = {'total': 0, 'cuentas': 0}
        cash_pool[moneda]['total'] += saldo
        cash_pool[moneda]['cuentas'] += 1
    
    # Calculate movements per account for current month
    # Group payments by bank account to calculate saldo_final
    account_movements = {}
    for p in payments:
        bank_txn_id = p.get('bank_transaction_id')
        if bank_txn_id:
            acc_id = bank_txn_to_account.get(bank_txn_id)
            if acc_id:
                if acc_id not in account_movements:
                    account_movements[acc_id] = {'ingresos': 0, 'egresos': 0, 'count': 0}
                if p.get('tipo') == 'cobro':
                    account_movements[acc_id]['ingresos'] += p.get('monto', 0)
                else:
                    account_movements[acc_id]['egresos'] += p.get('monto', 0)
                account_movements[acc_id]['count'] += 1
    
    # Build bank accounts detail with calculated saldo_final
    bank_accounts_detail = []
    for acc in accounts:
        saldo_inicial = acc.get('saldo_inicial', 0) or 0
        moneda = acc.get('moneda', 'MXN')
        acc_id = acc.get('id')
        
        # Get movements for this account
        movements = account_movements.get(acc_id, {'ingresos': 0, 'egresos': 0, 'count': 0})
        
        # Calculate saldo_final = saldo_inicial + ingresos - egresos
        saldo_final = saldo_inicial + movements['ingresos'] - movements['egresos']
        
        saldo_inicial_mxn = convert_to_mxn(saldo_inicial, moneda)
        saldo_final_mxn = convert_to_mxn(saldo_final, moneda)
        
        bank_accounts_detail.append({
            'id': acc_id,
            'nombre': acc.get('nombre'),
            'banco': acc.get('banco'),
            'numero_cuenta': acc.get('numero_cuenta'),
            'moneda': moneda,
            'saldo_inicial': saldo_inicial,
            'saldo_final': round(saldo_final, 2),
            'saldo_inicial_mxn': saldo_inicial_mxn,
            'saldo_final_mxn': saldo_final_mxn,
            'saldo_display': round(to_display_currency(saldo_final_mxn), 2),
            'ingresos': round(movements['ingresos'], 2),
            'egresos': round(movements['egresos'], 2),
            'num_movimientos': movements['count'],
            'riesgo': 'bajo' if saldo_final_mxn > 50000 else 'medio' if saldo_final_mxn > 10000 else 'alto'
        })
    
    # Convert weeks data to display currency
    for week in weeks_data:
        week['ingresos_display'] = round(to_display_currency(week['ingresos']), 2)
        week['egresos_display'] = round(to_display_currency(week['egresos']), 2)
        week['flujo_neto_display'] = round(to_display_currency(week['flujo_neto']), 2)
        week['saldo_inicial_display'] = round(to_display_currency(week['saldo_inicial']), 2)
        week['saldo_final_display'] = round(to_display_currency(week['saldo_final']), 2)
        week['varianza_display'] = round(to_display_currency(week.get('varianza', 0)), 2)
    
    # Get FX rate for display
    fx_rate_display = fx_map.get(moneda_vista, 1) if moneda_vista != 'MXN' else 1
    
    # Build response with account filter info
    response = {
        'moneda_vista': moneda_vista,
        'fx_rate': fx_rate_display,
        'saldo_bancos': round(to_display_currency(saldo_bancos_mxn), 2),
        'saldo_proyectado': round(to_display_currency(running_balance), 2),
        'total_ingresos': round(to_display_currency(total_ingresos), 2),
        'total_egresos': round(to_display_currency(total_egresos), 2),
        'burn_rate': round(to_display_currency(burn_rate), 2),
        'runway_weeks': round(runway_weeks, 1) if runway_weeks != float('inf') else None,
        'critical_week': critical_week,
        'cobranza_vs_pagos': round((total_ingresos / total_egresos * 100), 1) if total_egresos > 0 else 100,
        'weeks': weeks_data,
        'cash_pool': cash_pool,
        'bank_accounts': bank_accounts_detail,
        'kpis': {
            'total_payments': len(payments),
            'total_cfdis': await db.cfdis.count_documents({'company_id': company_id}),
            'total_customers': await db.customers.count_documents({'company_id': company_id}),
            'total_vendors': await db.vendors.count_documents({'company_id': company_id})
        }
    }
    
    # Add filtered account info if filtering by specific account
    if bank_account_id and len(accounts) > 0:
        acc = accounts[0]
        response['filtered_account'] = {
            'id': acc.get('id'),
            'nombre': acc.get('nombre'),
            'banco': acc.get('banco'),
            'moneda': acc.get('moneda'),
            'saldo_inicial': acc.get('saldo_inicial', 0) or 0,
            'saldo_inicial_display': round(to_display_currency(convert_to_mxn(acc.get('saldo_inicial', 0) or 0, acc.get('moneda', 'MXN'))), 2),
            'num_movements': len(payments)
        }
    
    return response


# ================== ENDPOINTS AVANZADOS - FASE 2 ==================

# Importar servicios avanzados
from advanced_services import PredictiveAnalysisService, AutoReconciliationService, AlertService
from integration_services import SATScraperService, BankAPIService, SATCredentialManager

# ===== AN\u00c1LISIS PREDICTIVO CON IA =====


# ===== PDF MEJORADO - Reporte Ejecutivo con Gráficas =====
from fastapi import Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import io

class PDFMejoradoRequest(BaseModel):
    empresa: str = "Mi Empresa"
    rfc: str = ""
    periodo: str = ""
    ingresos: float = 0
    costo_ventas: float = 0
    utilidad_bruta: float = 0
    gastos_op: float = 0
    ebitda: float = 0
    utilidad_neta: float = 0
    activo_total: float = 0
    activo_circ: float = 0
    activo_fijo: float = 0
    pasivo_total: float = 0
    pasivo_circ: float = 0
    pasivo_lp: float = 0
    capital: float = 0
    margen_bruto: float = 0
    margen_ebitda: float = 0
    margen_op: float = 0
    margen_neto: float = 0
    roic: float = 0
    roe: float = 0
    roa: float = 0
    roce: float = 0
    razon_circ: float = 0
    prueba_acida: float = 0
    razon_ef: float = 0
    capital_trabajo: float = 0
    cash_runway: float = 0
    dso: float = 0
    dpo: float = 0
    dio: float = 0
    ccc: float = 0
    deuda_capital: float = 0
    deuda_activos: float = 0
    deuda_ebitda: float = 0
    cobertura: float = 0
    apalancamiento: float = 0


@router.post("/reports/pdf-mejorado")
async def generate_pdf_mejorado(
    request: Request,
    data: PDFMejoradoRequest,
    current_user: Dict = Depends(get_current_user),
):
    """
    Genera el Reporte Ejecutivo Mejorado con gráficas y análisis profundo.
    Devuelve un PDF binario para descarga directa.
    """
    try:
        from services.pdf_generator import build_pdf_mejorado

        pdf_buffer = build_pdf_mejorado(data.dict())

        empresa_safe = data.empresa.replace(" ", "_").replace("/", "-")
        filename = f"Reporte_Ejecutivo_{empresa_safe}_{data.periodo}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    except Exception as e:
        logger.error(f"Error generando PDF Mejorado: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {str(e)}")
