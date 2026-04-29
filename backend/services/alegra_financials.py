"""
Alegra Financial Statement Generator
Takes synced Alegra invoices/bills/payments and generates income statement and balance sheet.
"""
import logging
from typing import Dict, List, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def generate_alegra_financial_statements(db, company_id: str, periodo: str) -> Dict:
    """Generate financial statements from Alegra synced data for a given period (YYYY-MM).
    
    Uses:
    - CFDIs with source=alegra or uuid starting with ALEGRA-INV (invoices = ingresos)
    - CFDIs with source=alegra or uuid starting with ALEGRA-BILL (bills = egresos)
    - Payments synced from Alegra
    """
    year = int(periodo.split('-')[0])
    month = int(periodo.split('-')[1])
    
    # Date range for the period
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year}-12-31"
    else:
        end_date = f"{year}-{month+1:02d}-01"
    
    # Get all Alegra invoices (ingresos) for this period
    invoices = await db.cfdis.find({
        'company_id': company_id,
        '$or': [
            {'uuid': {'$regex': '^ALEGRA-INV-'}},
            {'source': 'alegra', 'tipo_cfdi': 'ingreso'}
        ],
        'fecha_emision': {'$gte': start_date, '$lt': end_date}
    }, {'_id': 0}).to_list(5000)
    
    # Get all Alegra bills (egresos) for this period
    bills = await db.cfdis.find({
        'company_id': company_id,
        '$or': [
            {'uuid': {'$regex': '^ALEGRA-BILL-'}},
            {'source': 'alegra', 'tipo_cfdi': 'egreso'}
        ],
        'fecha_emision': {'$gte': start_date, '$lt': end_date}
    }, {'_id': 0}).to_list(5000)
    
    # Get bank accounts for balance
    bank_accounts = await db.bank_accounts.find(
        {'company_id': company_id, 'activo': True},
        {'_id': 0}
    ).to_list(20)
    
    # Calculate totals
    total_ingresos = sum(float(inv.get('total', 0)) for inv in invoices)
    total_iva_cobrado = sum(float(inv.get('iva_trasladado', 0)) for inv in invoices)
    total_subtotal_ingresos = sum(float(inv.get('subtotal', 0)) for inv in invoices)
    
    total_egresos = sum(float(bill.get('total', 0)) for bill in bills)
    total_iva_pagado = sum(float(bill.get('iva_trasladado', 0)) for bill in bills)
    total_subtotal_egresos = sum(float(bill.get('subtotal', 0)) for bill in bills)
    
    # Categorize expenses
    gastos_by_category = {}
    for bill in bills:
        cat_id = bill.get('category_id', 'uncategorized')
        gastos_by_category[cat_id] = gastos_by_category.get(cat_id, 0) + float(bill.get('subtotal', 0))
    
    # Estimate cost of sales vs operating expenses
    # Heuristic: if category is "costo" or no category, it's cost of sales
    # Otherwise it's operating expenses
    categories = await db.categories.find(
        {'company_id': company_id, 'tipo': 'egreso'},
        {'_id': 0}
    ).to_list(50)
    cat_map = {c['id']: c.get('nombre', '').lower() for c in categories}
    
    costo_ventas = 0
    gastos_operativos = 0
    gastos_financieros = 0
    
    for cat_id, amount in gastos_by_category.items():
        cat_name = cat_map.get(cat_id, '')
        if any(w in cat_name for w in ['costo', 'mercancia', 'materia prima', 'produccion', 'inventario']):
            costo_ventas += amount
        elif any(w in cat_name for w in ['interes', 'financiero', 'banco', 'comision bancaria']):
            gastos_financieros += amount
        else:
            gastos_operativos += amount
    
    # If no categorization, split 60/40 (cost of sales / operating)
    if costo_ventas == 0 and gastos_operativos == 0 and total_subtotal_egresos > 0:
        costo_ventas = total_subtotal_egresos * 0.6
        gastos_operativos = total_subtotal_egresos * 0.4
    
    # Build income statement
    utilidad_bruta = total_subtotal_ingresos - costo_ventas
    utilidad_operativa = utilidad_bruta - gastos_operativos
    utilidad_antes_impuestos = utilidad_operativa - gastos_financieros
    impuestos = max(0, utilidad_antes_impuestos * 0.30) if utilidad_antes_impuestos > 0 else 0
    utilidad_neta = utilidad_antes_impuestos - impuestos
    
    income = {
        'ingresos': total_subtotal_ingresos,
        'costo_ventas': costo_ventas,
        'utilidad_bruta': utilidad_bruta,
        'gastos_venta': gastos_operativos * 0.4,
        'gastos_administracion': gastos_operativos * 0.5,
        'gastos_generales': gastos_operativos * 0.1,
        'utilidad_operativa': utilidad_operativa,
        'otros_ingresos': 0,
        'gastos_financieros': gastos_financieros,
        'otros_gastos': 0,
        'utilidad_antes_impuestos': utilidad_antes_impuestos,
        'impuestos': impuestos,
        'utilidad_neta': utilidad_neta,
        'depreciacion': 0,
        'amortizacion': 0,
        'intereses': gastos_financieros,
        'ebitda': utilidad_operativa,
        'raw_data': [],
        'source': 'alegra',
        'invoices_count': len(invoices),
        'bills_count': len(bills),
    }
    
    # Build simplified balance sheet from available data
    total_efectivo = sum(float(ba.get('saldo_inicial', 0)) for ba in bank_accounts)
    
    # CxC = invoices not fully paid
    cxc = sum(float(inv.get('total', 0)) - float(inv.get('monto_cobrado', 0)) for inv in invoices if float(inv.get('monto_cobrado', 0)) < float(inv.get('total', 0)))
    
    # CxP = bills not fully paid
    cxp = sum(float(bill.get('total', 0)) - float(bill.get('monto_pagado', 0)) for bill in bills if float(bill.get('monto_pagado', 0)) < float(bill.get('total', 0)))
    
    balance = {
        'efectivo': total_efectivo,
        'cuentas_por_cobrar': cxc,
        'inventarios': 0,
        'otros_activos_circulantes': total_iva_pagado,
        'activo_circulante': total_efectivo + cxc + total_iva_pagado,
        'activos_fijos_neto': 0,
        'activos_intangibles': 0,
        'otros_activos': 0,
        'activo_total': total_efectivo + cxc + total_iva_pagado,
        'proveedores': cxp,
        'impuestos_por_pagar': total_iva_cobrado,
        'prestamos_corto_plazo': 0,
        'otros_pasivos_circulantes': 0,
        'pasivo_circulante': cxp + total_iva_cobrado,
        'deuda_largo_plazo': 0,
        'otros_pasivos_lp': 0,
        'pasivo_total': cxp + total_iva_cobrado,
        'capital_social': 0,
        'resultados_acumulados': 0,
        'resultado_ejercicio': utilidad_neta,
        'capital_contable': (total_efectivo + cxc + total_iva_pagado) - (cxp + total_iva_cobrado),
        'raw_data': [],
        'source': 'alegra',
    }
    
    has_data = len(invoices) > 0 or len(bills) > 0
    
    if has_data:
        # Save income statement
        await db.financial_statements.update_one(
            {'company_id': company_id, 'tipo': 'estado_resultados', 'periodo': periodo},
            {'$set': {
                'company_id': company_id,
                'tipo': 'estado_resultados',
                'periodo': periodo,
                'año': year,
                'mes': month,
                'datos': income,
                'archivo_original': f'Alegra auto-sync {periodo} ({len(invoices)} facturas, {len(bills)} gastos)',
                'source': 'alegra',
                'updated_at': datetime.now(timezone.utc).isoformat(),
            },
            '$setOnInsert': {'created_at': datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        
        # Save balance sheet
        await db.financial_statements.update_one(
            {'company_id': company_id, 'tipo': 'balance_general', 'periodo': periodo},
            {'$set': {
                'company_id': company_id,
                'tipo': 'balance_general',
                'periodo': periodo,
                'año': year,
                'mes': month,
                'datos': balance,
                'archivo_original': f'Alegra auto-sync {periodo}',
                'source': 'alegra',
                'updated_at': datetime.now(timezone.utc).isoformat(),
            },
            '$setOnInsert': {'created_at': datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
    
    return {
        'status': 'success' if has_data else 'no_data',
        'periodo': periodo,
        'invoices_processed': len(invoices),
        'bills_processed': len(bills),
        'ingresos': total_subtotal_ingresos,
        'egresos': total_subtotal_egresos,
        'utilidad_neta': utilidad_neta,
    }
