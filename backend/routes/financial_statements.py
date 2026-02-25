"""
Financial Statements Module
Handles import and processing of Income Statement and Balance Sheet from Alegra Excel exports
"""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Query
from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging
import pandas as pd
import io
import re

from database import db
from utils.auth import get_current_user
from utils.helpers import get_active_company_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/financial-statements", tags=["Financial Statements"])


def parse_alegra_income_statement(df: pd.DataFrame) -> Dict:
    """Parse Alegra Income Statement Excel format"""
    result = {
        'ingresos': 0,
        'costo_ventas': 0,
        'utilidad_bruta': 0,
        'gastos_venta': 0,
        'gastos_administracion': 0,
        'gastos_generales': 0,
        'utilidad_operativa': 0,
        'otros_ingresos': 0,
        'gastos_financieros': 0,
        'otros_gastos': 0,
        'utilidad_antes_impuestos': 0,
        'impuestos': 0,
        'utilidad_neta': 0,
        'depreciacion': 0,  # For EBITDA calculation
        'amortizacion': 0,
        'intereses': 0,
        'raw_data': []
    }
    
    # Find the column with values (usually the first numeric column after account code)
    value_col = None
    for col in df.columns:
        if df[col].dtype in ['float64', 'int64'] or 'Ene' in str(col) or '2024' in str(col) or '2025' in str(col) or '2026' in str(col):
            # Check if it has numeric values
            try:
                test_vals = pd.to_numeric(df[col], errors='coerce')
                if test_vals.notna().any():
                    value_col = col
                    break
            except:
                continue
    
    if value_col is None:
        # Try second column
        if len(df.columns) > 1:
            value_col = df.columns[1]
    
    # Process each row
    for idx, row in df.iterrows():
        account_code = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
        account_name = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else account_code
        
        try:
            value = float(row[value_col]) if pd.notna(row[value_col]) else 0
        except:
            value = 0
        
        # Map accounts to categories based on code patterns
        code_clean = account_code.replace('-', '').replace(' ', '')
        
        # Store raw data
        result['raw_data'].append({
            'codigo': account_code,
            'cuenta': account_name,
            'valor': value
        })
        
        # Map to standard categories
        if '400' in code_clean or 'Ingreso' in account_name or 'Venta' in account_name:
            if 'Utilidad' not in account_name and value > 0:
                result['ingresos'] += value
        
        elif '500' in code_clean or 'Costo' in account_name:
            result['costo_ventas'] += abs(value)
        
        elif 'Utilidad bruta' in account_name:
            result['utilidad_bruta'] = value
        
        elif '601' in code_clean or 'Gasto' in account_name and 'venta' in account_name.lower():
            result['gastos_venta'] += abs(value)
        
        elif '602' in code_clean or 'administraci' in account_name.lower():
            result['gastos_administracion'] += abs(value)
        
        elif '603' in code_clean or 'general' in account_name.lower():
            result['gastos_generales'] += abs(value)
        
        elif 'Utilidad operativa' in account_name:
            result['utilidad_operativa'] = value
        
        elif '404' in code_clean or 'Otros ingresos' in account_name or 'financiero' in account_name.lower() and 'ingreso' in account_name.lower():
            result['otros_ingresos'] += value
        
        elif '604' in code_clean or 'Gasto' in account_name and 'financiero' in account_name.lower():
            result['gastos_financieros'] += abs(value)
            result['intereses'] += abs(value)
        
        elif '605' in code_clean or 'Otros gastos' in account_name:
            result['otros_gastos'] += abs(value)
        
        elif 'Utilidad antes de impuestos' in account_name:
            result['utilidad_antes_impuestos'] = value
        
        elif '606' in code_clean or 'impuesto' in account_name.lower():
            result['impuestos'] += abs(value)
        
        elif 'Utilidad neta' in account_name:
            result['utilidad_neta'] = value
        
        elif 'deprecia' in account_name.lower():
            result['depreciacion'] += abs(value)
        
        elif 'amortiza' in account_name.lower():
            result['amortizacion'] += abs(value)
    
    # Calculate EBITDA if not directly available
    result['ebitda'] = result['utilidad_operativa'] + result['depreciacion'] + result['amortizacion']
    
    return result


def parse_alegra_balance_sheet(df: pd.DataFrame) -> Dict:
    """Parse Alegra Balance Sheet Excel format"""
    result = {
        # Activos
        'activo_circulante': 0,
        'efectivo': 0,
        'cuentas_por_cobrar': 0,
        'inventarios': 0,
        'otros_activos_circulantes': 0,
        'activo_fijo': 0,
        'activo_total': 0,
        
        # Pasivos
        'pasivo_circulante': 0,
        'cuentas_por_pagar': 0,
        'deuda_corto_plazo': 0,
        'otros_pasivos_circulantes': 0,
        'pasivo_largo_plazo': 0,
        'deuda_largo_plazo': 0,
        'pasivo_total': 0,
        
        # Capital
        'capital_social': 0,
        'utilidades_retenidas': 0,
        'capital_contable': 0,
        
        'raw_data': []
    }
    
    # Find the value column
    value_col = None
    for col in df.columns:
        col_str = str(col)
        if 'Ene' in col_str or '2024' in col_str or '2025' in col_str or '2026' in col_str:
            value_col = col
            break
    
    if value_col is None and len(df.columns) > 2:
        value_col = df.columns[2]
    
    # Process each row
    for idx, row in df.iterrows():
        account_code = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
        account_name = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else account_code
        
        try:
            value = float(row[value_col]) if value_col and pd.notna(row[value_col]) else 0
        except:
            value = 0
        
        # Store raw data
        result['raw_data'].append({
            'codigo': account_code,
            'cuenta': account_name,
            'valor': value
        })
        
        account_lower = account_name.lower()
        code_clean = account_code.replace('-', '').replace(' ', '')
        
        # ACTIVOS
        if 'Total activos' in account_name:
            result['activo_total'] = value
        
        elif 'Activo a corto plazo' in account_name or '100-00-000' in code_clean:
            result['activo_circulante'] = value
        
        elif '101' in code_clean or 'efectivo' in account_lower or 'banco' in account_lower or 'caja' in account_lower:
            result['efectivo'] += value
        
        elif '103' in code_clean or 'cuenta' in account_lower and 'cobrar' in account_lower:
            result['cuentas_por_cobrar'] += value
        
        elif '110' in code_clean or 'inventario' in account_lower:
            result['inventarios'] += value
        
        elif '150' in code_clean or 'activo fijo' in account_lower or 'propiedad' in account_lower:
            result['activo_fijo'] = value
        
        # PASIVOS
        elif 'Total pasivos' in account_name:
            result['pasivo_total'] = value
        
        elif 'Pasivo a corto plazo' in account_name or '200-01-000' in code_clean:
            result['pasivo_circulante'] = value
        
        elif '201' in code_clean or 'cuenta' in account_lower and 'pagar' in account_lower and 'proveedor' in account_lower:
            result['cuentas_por_pagar'] += value
        
        elif '204' in code_clean or 'obligacion' in account_lower and 'financier' in account_lower and 'corto' in account_lower:
            result['deuda_corto_plazo'] += value
        
        elif 'Pasivo' in account_name and 'largo plazo' in account_lower:
            result['pasivo_largo_plazo'] = value
        
        elif '250' in code_clean or 'obligacion' in account_lower and 'financier' in account_lower and 'largo' in account_lower:
            result['deuda_largo_plazo'] += value
        
        # CAPITAL
        elif 'Total capital contable' in account_name:
            result['capital_contable'] = value
        
        elif '301' in code_clean or 'capital social' in account_lower:
            result['capital_social'] += value
        
        elif '302' in code_clean or '303' in code_clean or 'utilidad' in account_lower and ('ejercicio' in account_lower or 'anterior' in account_lower):
            result['utilidades_retenidas'] += value
    
    # Calculate totals if not found
    if result['activo_total'] == 0:
        result['activo_total'] = result['activo_circulante'] + result['activo_fijo']
    
    if result['pasivo_total'] == 0:
        result['pasivo_total'] = result['pasivo_circulante'] + result['pasivo_largo_plazo']
    
    # Calculate other circulantes
    result['otros_activos_circulantes'] = result['activo_circulante'] - result['efectivo'] - result['cuentas_por_cobrar'] - result['inventarios']
    result['otros_pasivos_circulantes'] = result['pasivo_circulante'] - result['cuentas_por_pagar'] - result['deuda_corto_plazo']
    
    return result


def calculate_financial_metrics(income: Dict, balance: Dict) -> Dict:
    """Calculate all financial metrics from Income Statement and Balance Sheet"""
    
    # Avoid division by zero
    def safe_div(a, b, default=0):
        return (a / b) if b != 0 else default
    
    def safe_pct(a, b, default=0):
        return (a / b * 100) if b != 0 else default
    
    ingresos = income.get('ingresos', 0)
    utilidad_bruta = income.get('utilidad_bruta', 0)
    ebitda = income.get('ebitda', 0)
    utilidad_operativa = income.get('utilidad_operativa', 0)
    utilidad_neta = income.get('utilidad_neta', 0)
    costo_ventas = income.get('costo_ventas', 0)
    intereses = income.get('intereses', 0)
    impuestos = income.get('impuestos', 0)
    depreciacion = income.get('depreciacion', 0)
    
    activo_total = balance.get('activo_total', 0)
    activo_circulante = balance.get('activo_circulante', 0)
    efectivo = balance.get('efectivo', 0)
    cuentas_por_cobrar = balance.get('cuentas_por_cobrar', 0)
    inventarios = balance.get('inventarios', 0)
    activo_fijo = balance.get('activo_fijo', 0)
    
    pasivo_total = balance.get('pasivo_total', 0)
    pasivo_circulante = balance.get('pasivo_circulante', 0)
    cuentas_por_pagar = balance.get('cuentas_por_pagar', 0)
    deuda_corto_plazo = balance.get('deuda_corto_plazo', 0)
    pasivo_largo_plazo = balance.get('pasivo_largo_plazo', 0)
    deuda_largo_plazo = balance.get('deuda_largo_plazo', 0)
    
    capital_contable = balance.get('capital_contable', 0)
    
    # Deuda total
    deuda_total = deuda_corto_plazo + deuda_largo_plazo
    
    # Capital invertido = Deuda + Capital
    capital_invertido = deuda_total + capital_contable
    
    # NOPAT (Net Operating Profit After Tax)
    tax_rate = safe_div(impuestos, income.get('utilidad_antes_impuestos', 0))
    nopat = utilidad_operativa * (1 - tax_rate)
    
    # Calculate metrics
    metrics = {
        # === MÁRGENES ===
        'margins': {
            'gross_margin': {
                'value': safe_pct(utilidad_bruta, ingresos),
                'label': 'Margen Bruto',
                'formula': 'Utilidad Bruta / Ingresos',
                'interpretation': 'Porcentaje de ingresos que queda después de costos directos'
            },
            'ebitda_margin': {
                'value': safe_pct(ebitda, ingresos),
                'label': 'Margen EBITDA',
                'formula': 'EBITDA / Ingresos',
                'interpretation': 'Rentabilidad operativa antes de intereses, impuestos, depreciación y amortización'
            },
            'operating_margin': {
                'value': safe_pct(utilidad_operativa, ingresos),
                'label': 'Margen Operativo',
                'formula': 'Utilidad Operativa / Ingresos',
                'interpretation': 'Porcentaje de ingresos que queda después de gastos operativos'
            },
            'net_margin': {
                'value': safe_pct(utilidad_neta, ingresos),
                'label': 'Margen Neto',
                'formula': 'Utilidad Neta / Ingresos',
                'interpretation': 'Porcentaje de ingresos que se convierte en utilidad'
            },
            'nopat_margin': {
                'value': safe_pct(nopat, ingresos),
                'label': 'Margen NOPAT',
                'formula': 'NOPAT / Ingresos',
                'interpretation': 'Utilidad operativa después de impuestos'
            }
        },
        
        # === RETORNO ===
        'returns': {
            'roic': {
                'value': safe_pct(nopat, capital_invertido),
                'label': 'ROIC',
                'formula': 'NOPAT / Capital Invertido',
                'interpretation': 'Retorno sobre capital invertido (deuda + equity)'
            },
            'roe': {
                'value': safe_pct(utilidad_neta, capital_contable),
                'label': 'ROE',
                'formula': 'Utilidad Neta / Capital Contable',
                'interpretation': 'Retorno sobre el capital de los accionistas'
            },
            'roce': {
                'value': safe_pct(utilidad_operativa, (activo_total - pasivo_circulante)),
                'label': 'ROCE',
                'formula': 'EBIT / (Activos - Pasivo Circulante)',
                'interpretation': 'Retorno sobre capital empleado'
            },
            'roa': {
                'value': safe_pct(utilidad_neta, activo_total),
                'label': 'ROA',
                'formula': 'Utilidad Neta / Activos Totales',
                'interpretation': 'Retorno sobre activos totales'
            }
        },
        
        # === EFICIENCIA ===
        'efficiency': {
            'asset_turnover': {
                'value': safe_div(ingresos, activo_total),
                'label': 'Rotación de Activos',
                'formula': 'Ingresos / Activos Totales',
                'interpretation': 'Veces que los activos generan ingresos'
            },
            'receivables_turnover': {
                'value': safe_div(ingresos, cuentas_por_cobrar),
                'label': 'Rotación de CxC',
                'formula': 'Ingresos / Cuentas por Cobrar',
                'interpretation': 'Veces que se cobran las cuentas por cobrar'
            },
            'inventory_turnover': {
                'value': safe_div(costo_ventas, inventarios),
                'label': 'Rotación de Inventarios',
                'formula': 'Costo de Ventas / Inventarios',
                'interpretation': 'Veces que se rota el inventario'
            },
            'payables_turnover': {
                'value': safe_div(costo_ventas, cuentas_por_pagar),
                'label': 'Rotación de CxP',
                'formula': 'Costo de Ventas / Cuentas por Pagar',
                'interpretation': 'Veces que se pagan las cuentas por pagar'
            },
            'ic_turnover': {
                'value': safe_div(ingresos, capital_invertido),
                'label': 'Rotación de Capital Invertido',
                'formula': 'Ingresos / Capital Invertido',
                'interpretation': 'Eficiencia del capital invertido'
            },
            'dso': {
                'value': safe_div(cuentas_por_cobrar * 365, ingresos),
                'label': 'DSO (Días de Cobro)',
                'formula': '(CxC × 365) / Ingresos',
                'interpretation': 'Días promedio para cobrar'
            },
            'dpo': {
                'value': safe_div(cuentas_por_pagar * 365, costo_ventas),
                'label': 'DPO (Días de Pago)',
                'formula': '(CxP × 365) / Costo de Ventas',
                'interpretation': 'Días promedio para pagar'
            },
            'dio': {
                'value': safe_div(inventarios * 365, costo_ventas),
                'label': 'DIO (Días de Inventario)',
                'formula': '(Inventarios × 365) / Costo de Ventas',
                'interpretation': 'Días promedio de inventario'
            }
        },
        
        # === LIQUIDEZ ===
        'liquidity': {
            'current_ratio': {
                'value': safe_div(activo_circulante, pasivo_circulante),
                'label': 'Razón Circulante',
                'formula': 'Activo Circulante / Pasivo Circulante',
                'interpretation': 'Capacidad de pagar deudas corto plazo con activos circulantes'
            },
            'quick_ratio': {
                'value': safe_div((activo_circulante - inventarios), pasivo_circulante),
                'label': 'Prueba Ácida',
                'formula': '(Activo Circulante - Inventarios) / Pasivo Circulante',
                'interpretation': 'Capacidad de pago sin depender de inventarios'
            },
            'cash_ratio': {
                'value': safe_div(efectivo, pasivo_circulante),
                'label': 'Razón de Efectivo',
                'formula': 'Efectivo / Pasivo Circulante',
                'interpretation': 'Capacidad de pago inmediato con efectivo'
            },
            'working_capital': {
                'value': activo_circulante - pasivo_circulante,
                'label': 'Capital de Trabajo',
                'formula': 'Activo Circulante - Pasivo Circulante',
                'interpretation': 'Recursos disponibles para operar'
            },
            'cash_conversion_cycle': {
                'value': safe_div(cuentas_por_cobrar * 365, ingresos) + safe_div(inventarios * 365, costo_ventas) - safe_div(cuentas_por_pagar * 365, costo_ventas),
                'label': 'Ciclo de Conversión de Efectivo',
                'formula': 'DSO + DIO - DPO',
                'interpretation': 'Días para convertir inversión en efectivo'
            }
        },
        
        # === SOLVENCIA ===
        'solvency': {
            'debt_to_equity': {
                'value': safe_div(deuda_total, capital_contable),
                'label': 'Deuda / Capital',
                'formula': 'Deuda Total / Capital Contable',
                'interpretation': 'Proporción de financiamiento con deuda vs equity'
            },
            'debt_to_assets': {
                'value': safe_pct(pasivo_total, activo_total),
                'label': 'Deuda / Activos',
                'formula': 'Pasivo Total / Activos Totales',
                'interpretation': 'Porcentaje de activos financiados con deuda'
            },
            'debt_to_ebitda': {
                'value': safe_div(deuda_total, ebitda),
                'label': 'Deuda / EBITDA',
                'formula': 'Deuda Total / EBITDA',
                'interpretation': 'Años para pagar deuda con EBITDA'
            },
            'interest_coverage': {
                'value': safe_div(utilidad_operativa, intereses),
                'label': 'Cobertura de Intereses',
                'formula': 'EBIT / Intereses',
                'interpretation': 'Veces que se pueden pagar los intereses'
            },
            'equity_ratio': {
                'value': safe_pct(capital_contable, activo_total),
                'label': 'Razón de Capital',
                'formula': 'Capital Contable / Activos Totales',
                'interpretation': 'Porcentaje de activos financiados con capital propio'
            }
        },
        
        # === VALORES ABSOLUTOS ===
        'absolute_values': {
            'ingresos': ingresos,
            'costo_ventas': costo_ventas,
            'utilidad_bruta': utilidad_bruta,
            'ebitda': ebitda,
            'utilidad_operativa': utilidad_operativa,
            'utilidad_neta': utilidad_neta,
            'nopat': nopat,
            'activo_total': activo_total,
            'activo_circulante': activo_circulante,
            'efectivo': efectivo,
            'cuentas_por_cobrar': cuentas_por_cobrar,
            'inventarios': inventarios,
            'pasivo_total': pasivo_total,
            'pasivo_circulante': pasivo_circulante,
            'cuentas_por_pagar': cuentas_por_pagar,
            'deuda_total': deuda_total,
            'capital_contable': capital_contable,
            'capital_invertido': capital_invertido
        }
    }
    
    return metrics


@router.post("/upload/income-statement")
async def upload_income_statement(
    request: Request,
    file: UploadFile = File(...),
    periodo: str = Query(..., description="Período en formato YYYY-MM"),
    current_user: Dict = Depends(get_current_user)
):
    """Upload and process Income Statement Excel from Alegra"""
    company_id = await get_active_company_id(request, current_user)
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos Excel (.xlsx, .xls)")
    
    try:
        content = await file.read()
        df = pd.read_excel(io.BytesIO(content))
        
        # Parse the income statement
        parsed = parse_alegra_income_statement(df)
        
        # Save to database
        doc = {
            'company_id': company_id,
            'tipo': 'estado_resultados',
            'periodo': periodo,
            'año': int(periodo.split('-')[0]),
            'mes': int(periodo.split('-')[1]),
            'datos': parsed,
            'archivo_original': file.filename,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Check if exists for this period
        existing = await db.financial_statements.find_one({
            'company_id': company_id,
            'tipo': 'estado_resultados',
            'periodo': periodo
        })
        
        if existing:
            await db.financial_statements.update_one(
                {'_id': existing['_id']},
                {'$set': doc}
            )
            action = 'actualizado'
        else:
            await db.financial_statements.insert_one(doc)
            action = 'creado'
        
        return {
            "success": True,
            "message": f"Estado de Resultados {action} para {periodo}",
            "data": parsed
        }
        
    except Exception as e:
        logger.error(f"Error processing income statement: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error procesando archivo: {str(e)}")


@router.post("/upload/balance-sheet")
async def upload_balance_sheet(
    request: Request,
    file: UploadFile = File(...),
    periodo: str = Query(..., description="Período en formato YYYY-MM"),
    current_user: Dict = Depends(get_current_user)
):
    """Upload and process Balance Sheet Excel from Alegra"""
    company_id = await get_active_company_id(request, current_user)
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos Excel (.xlsx, .xls)")
    
    try:
        content = await file.read()
        df = pd.read_excel(io.BytesIO(content))
        
        # Parse the balance sheet
        parsed = parse_alegra_balance_sheet(df)
        
        # Save to database
        doc = {
            'company_id': company_id,
            'tipo': 'balance_general',
            'periodo': periodo,
            'año': int(periodo.split('-')[0]),
            'mes': int(periodo.split('-')[1]),
            'datos': parsed,
            'archivo_original': file.filename,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Check if exists for this period
        existing = await db.financial_statements.find_one({
            'company_id': company_id,
            'tipo': 'balance_general',
            'periodo': periodo
        })
        
        if existing:
            await db.financial_statements.update_one(
                {'_id': existing['_id']},
                {'$set': doc}
            )
            action = 'actualizado'
        else:
            await db.financial_statements.insert_one(doc)
            action = 'creado'
        
        return {
            "success": True,
            "message": f"Balance General {action} para {periodo}",
            "data": parsed
        }
        
    except Exception as e:
        logger.error(f"Error processing balance sheet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error procesando archivo: {str(e)}")


@router.get("/metrics/{periodo}")
async def get_financial_metrics(
    request: Request,
    periodo: str,
    current_user: Dict = Depends(get_current_user)
):
    """Get calculated financial metrics for a specific period"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get income statement for period
    income_stmt = await db.financial_statements.find_one({
        'company_id': company_id,
        'tipo': 'estado_resultados',
        'periodo': periodo
    }, {'_id': 0})
    
    # Get balance sheet for period
    balance_sheet = await db.financial_statements.find_one({
        'company_id': company_id,
        'tipo': 'balance_general',
        'periodo': periodo
    }, {'_id': 0})
    
    if not income_stmt and not balance_sheet:
        raise HTTPException(status_code=404, detail=f"No hay estados financieros para {periodo}")
    
    # Calculate metrics
    income_data = income_stmt.get('datos', {}) if income_stmt else {}
    balance_data = balance_sheet.get('datos', {}) if balance_sheet else {}
    
    metrics = calculate_financial_metrics(income_data, balance_data)
    
    return {
        "periodo": periodo,
        "has_income_statement": income_stmt is not None,
        "has_balance_sheet": balance_sheet is not None,
        "metrics": metrics,
        "income_statement": income_data,
        "balance_sheet": balance_data
    }


@router.get("/periods")
async def get_available_periods(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Get list of periods with financial statements"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get all distinct periods
    pipeline = [
        {'$match': {'company_id': company_id}},
        {'$group': {
            '_id': '$periodo',
            'tipos': {'$addToSet': '$tipo'},
            'updated_at': {'$max': '$updated_at'}
        }},
        {'$sort': {'_id': -1}}
    ]
    
    results = await db.financial_statements.aggregate(pipeline).to_list(100)
    
    periods = []
    for r in results:
        periods.append({
            'periodo': r['_id'],
            'has_income_statement': 'estado_resultados' in r['tipos'],
            'has_balance_sheet': 'balance_general' in r['tipos'],
            'updated_at': r['updated_at']
        })
    
    return periods


@router.delete("/{periodo}")
async def delete_financial_statements(
    request: Request,
    periodo: str,
    tipo: Optional[str] = Query(None, description="Tipo: estado_resultados, balance_general, o vacío para ambos"),
    current_user: Dict = Depends(get_current_user)
):
    """Delete financial statements for a period"""
    company_id = await get_active_company_id(request, current_user)
    
    query = {'company_id': company_id, 'periodo': periodo}
    if tipo:
        query['tipo'] = tipo
    
    result = await db.financial_statements.delete_many(query)
    
    return {
        "success": True,
        "deleted": result.deleted_count,
        "message": f"Se eliminaron {result.deleted_count} registros para {periodo}"
    }
