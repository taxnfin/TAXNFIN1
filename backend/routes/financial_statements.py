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

from core.database import db
from core.auth import get_current_user, get_active_company_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/financial-statements", tags=["Financial Statements"])


def parse_alegra_income_statement(df: pd.DataFrame) -> Dict:
    """Parse Alegra Income Statement Excel format
    
    Alegra format:
    - Row 0-4: Header (company name, RFC, period, currency)
    - Row 5: Column headers (Código, Cuenta contable, Mes/Año, %, ...)
    - Row 6+: Data rows with code in col 0, name in col 1, value in col 2
    - Special rows without code contain totals (Utilidad bruta, Utilidad operativa, Utilidad neta)
    """
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
        'depreciacion': 0,
        'amortizacion': 0,
        'intereses': 0,
        'raw_data': []
    }
    
    # Find header row and value column
    header_row = None
    value_col_idx = 2  # Default: column index 2 (third column)
    
    for idx, row in df.iterrows():
        cell0 = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
        if 'Código' in cell0 or 'codigo' in cell0.lower():
            header_row = idx
            # Find the value column (first column with year/month data)
            for col_idx in range(2, len(row)):
                col_val = str(row.iloc[col_idx]) if pd.notna(row.iloc[col_idx]) else ''
                if any(month in col_val for month in ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']) or any(str(yr) in col_val for yr in range(2020, 2030)):
                    value_col_idx = col_idx
                    break
            break
    
    if header_row is None:
        header_row = 5  # Default for Alegra
    
    # Process data rows (after header)
    for idx, row in df.iterrows():
        if idx <= header_row:
            continue
            
        codigo = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
        cuenta = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''
        
        try:
            valor = float(row.iloc[value_col_idx]) if pd.notna(row.iloc[value_col_idx]) else 0
        except (ValueError, TypeError):
            valor = 0
        
        # Skip rows without meaningful data
        if not cuenta and not codigo:
            continue
        
        # Store raw data for debugging
        if cuenta or codigo:
            result['raw_data'].append({
                'codigo': codigo,
                'cuenta': cuenta,
                'valor': valor
            })
        
        cuenta_lower = cuenta.lower().strip()
        codigo_clean = codigo.replace('-', '').replace(' ', '')
        
        # === TOTALES (filas sin código, solo nombre) ===
        if not codigo or codigo == 'nan':
            if cuenta_lower == 'utilidad bruta':
                result['utilidad_bruta'] = valor
            elif cuenta_lower == 'utilidad operativa':
                result['utilidad_operativa'] = valor
            elif cuenta_lower == 'utilidad neta':
                result['utilidad_neta'] = valor
            elif 'utilidad antes de impuestos' in cuenta_lower:
                result['utilidad_antes_impuestos'] = valor
            continue
        
        # === INGRESOS (400-xx-xxx) ===
        if codigo_clean.startswith('400') or codigo_clean.startswith('401'):
            # Solo tomar el total principal de ingresos
            if codigo_clean == '40001000' or codigo == '400-01-000':
                result['ingresos'] = abs(valor)
        
        # === COSTOS DE VENTAS (500-xx-xxx) ===
        elif codigo_clean.startswith('500') or codigo_clean.startswith('501'):
            # Solo tomar el total principal de costos
            if codigo_clean == '50001000' or codigo == '500-01-000':
                result['costo_ventas'] = abs(valor)
        
        # === GASTOS DE VENTA (601-xx-xxx) ===
        elif codigo_clean.startswith('601'):
            if codigo_clean == '60100000' or codigo == '601-00-000':
                result['gastos_venta'] = abs(valor)
        
        # === GASTOS DE ADMINISTRACIÓN (602-xx-xxx) ===
        elif codigo_clean.startswith('602'):
            if codigo_clean == '60200000' or codigo == '602-00-000':
                result['gastos_administracion'] = abs(valor)
        
        # === GASTOS GENERALES (603-xx-xxx) ===
        elif codigo_clean.startswith('603'):
            if codigo_clean == '60300000' or codigo == '603-00-000':
                result['gastos_generales'] = abs(valor)
        
        # === OTROS INGRESOS (404-xx-xxx) ===
        elif codigo_clean.startswith('404'):
            if codigo_clean == '40400000' or codigo == '404-00-000':
                result['otros_ingresos'] = abs(valor)
        
        # === GASTOS FINANCIEROS (604-xx-xxx) ===
        elif codigo_clean.startswith('604'):
            if codigo_clean == '60400000' or codigo == '604-00-000':
                result['gastos_financieros'] = abs(valor)
                result['intereses'] = abs(valor)
        
        # === OTROS GASTOS (605-xx-xxx) ===
        elif codigo_clean.startswith('605'):
            if codigo_clean == '60500000' or codigo == '605-00-000':
                result['otros_gastos'] = abs(valor)
        
        # === IMPUESTOS (606-xx-xxx) ===
        elif codigo_clean.startswith('606'):
            if codigo_clean == '60600000' or codigo == '606-00-000':
                result['impuestos'] = abs(valor)
        
        # === DEPRECIACIÓN Y AMORTIZACIÓN ===
        if 'deprecia' in cuenta_lower:
            result['depreciacion'] += abs(valor)
        elif 'amortiza' in cuenta_lower:
            result['amortizacion'] += abs(valor)
    
    # Calculate EBITDA (Utilidad operativa + Depreciación + Amortización)
    result['ebitda'] = result['utilidad_operativa'] + result['depreciacion'] + result['amortizacion']
    
    # Si no se encontró utilidad bruta como total, calcularla
    if result['utilidad_bruta'] == 0 and result['ingresos'] > 0:
        result['utilidad_bruta'] = result['ingresos'] - result['costo_ventas']
    
    return result


def parse_alegra_balance_sheet(df: pd.DataFrame) -> Dict:
    """Parse Alegra Balance Sheet Excel format
    
    Alegra format:
    - Row 0-5: Header (title, company name, RFC, period, currency)
    - Row 6: Column headers (Código, Cuenta contable, Fecha, %, ...)
    - Row 7+: Data rows
    - Special rows without code contain totals (Total activos, Total pasivos, Total capital contable)
    """
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
    
    # Find header row and value column
    header_row = None
    value_col_idx = 2  # Default: column index 2 (third column)
    
    for idx, row in df.iterrows():
        cell0 = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
        if 'Código' in cell0 or 'codigo' in cell0.lower():
            header_row = idx
            # Find the value column (first column with date/year data)
            for col_idx in range(2, len(row)):
                col_val = str(row.iloc[col_idx]) if pd.notna(row.iloc[col_idx]) else ''
                if any(month in col_val for month in ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']) or any(str(yr) in col_val for yr in range(2020, 2030)):
                    value_col_idx = col_idx
                    break
            break
    
    if header_row is None:
        header_row = 6  # Default for Alegra Balance
    
    # Process data rows (after header)
    for idx, row in df.iterrows():
        if idx <= header_row:
            continue
            
        codigo = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
        cuenta = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''
        
        try:
            valor = float(row.iloc[value_col_idx]) if pd.notna(row.iloc[value_col_idx]) else 0
        except (ValueError, TypeError):
            valor = 0
        
        # Skip rows without meaningful data
        if not cuenta and not codigo:
            continue
        
        # Store raw data
        if cuenta or codigo:
            result['raw_data'].append({
                'codigo': codigo,
                'cuenta': cuenta,
                'valor': valor
            })
        
        cuenta_lower = cuenta.lower().strip()
        codigo_clean = codigo.replace('-', '').replace(' ', '')
        
        # === TOTALES (filas sin código, solo nombre) ===
        if not codigo or codigo == 'nan':
            if cuenta_lower == 'total activos':
                result['activo_total'] = abs(valor)
            elif cuenta_lower == 'total pasivos':
                result['pasivo_total'] = abs(valor)
            elif cuenta_lower == 'total capital contable':
                result['capital_contable'] = abs(valor)
            continue
        
        # === ACTIVOS CIRCULANTES (100-xx-xxx) ===
        if codigo == '100-01-000' or codigo_clean == '10001000':
            result['activo_circulante'] = abs(valor)
        
        # Efectivo y equivalentes (101-xx-xxx)
        elif codigo == '101-00-000' or codigo_clean == '10100000':
            result['efectivo'] = abs(valor)
        
        # Cuentas por cobrar (103-xx-xxx)
        elif codigo == '103-00-000' or codigo_clean == '10300000':
            result['cuentas_por_cobrar'] = abs(valor)
        
        # Inventarios (110-xx-xxx)
        elif codigo == '110-00-000' or codigo_clean == '11000000':
            result['inventarios'] = abs(valor)
        
        # === ACTIVOS FIJOS / LARGO PLAZO (150-xx-xxx, 100-02-000) ===
        elif codigo == '100-02-000' or codigo_clean == '10002000':
            result['activo_fijo'] = abs(valor)
        elif codigo == '150-00-000' or codigo_clean == '15000000':
            result['activo_fijo'] = abs(valor)
        
        # === PASIVOS CIRCULANTES (200-xx-xxx) ===
        elif codigo == '200-01-000' or codigo_clean == '20001000':
            result['pasivo_circulante'] = abs(valor)
        
        # Cuentas por pagar proveedores (201-xx-xxx)
        elif codigo == '201-00-000' or codigo_clean == '20100000':
            result['cuentas_por_pagar'] = abs(valor)
        
        # Deuda corto plazo / Obligaciones financieras (204-xx-xxx)
        elif codigo == '204-00-000' or codigo_clean == '20400000':
            result['deuda_corto_plazo'] = abs(valor)
        
        # === PASIVOS LARGO PLAZO (200-02-000, 250-xx-xxx) ===
        elif codigo == '200-02-000' or codigo_clean == '20002000':
            result['pasivo_largo_plazo'] = abs(valor)
        elif codigo == '250-00-000' or codigo_clean == '25000000':
            result['deuda_largo_plazo'] = abs(valor)
        
        # === CAPITAL (300-xx-xxx) ===
        elif codigo == '301-00-000' or codigo_clean == '30100000':
            result['capital_social'] = abs(valor)
        
        elif codigo == '302-00-000' or codigo_clean == '30200000' or codigo == '303-00-000' or codigo_clean == '30300000':
            result['utilidades_retenidas'] += abs(valor)
    
    # Calculate totals if not found from headers
    if result['activo_total'] == 0:
        result['activo_total'] = result['activo_circulante'] + result['activo_fijo']
    
    if result['pasivo_total'] == 0:
        result['pasivo_total'] = result['pasivo_circulante'] + result['pasivo_largo_plazo']
    
    # Calculate other circulantes
    result['otros_activos_circulantes'] = max(0, result['activo_circulante'] - result['efectivo'] - result['cuentas_por_cobrar'] - result['inventarios'])
    result['otros_pasivos_circulantes'] = max(0, result['pasivo_circulante'] - result['cuentas_por_pagar'] - result['deuda_corto_plazo'])
    
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
                'value': safe_div(cuentas_por_cobrar * 30, ingresos),  # 30 días para datos mensuales
                'label': 'DSO (Días de Cobro)',
                'formula': '(CxC × 30) / Ingresos mensuales',
                'interpretation': 'Días promedio para cobrar'
            },
            'dpo': {
                'value': safe_div(cuentas_por_pagar * 30, costo_ventas) if costo_ventas > 0 else 0,  # 30 días para datos mensuales
                'label': 'DPO (Días de Pago)',
                'formula': '(CxP × 30) / Costo de Ventas mensual',
                'interpretation': 'Días promedio para pagar'
            },
            'dio': {
                'value': safe_div(inventarios * 30, costo_ventas) if costo_ventas > 0 else 0,  # 30 días para datos mensuales
                'label': 'DIO (Días de Inventario)',
                'formula': '(Inventarios × 30) / Costo de Ventas mensual',
                'interpretation': 'Días promedio de inventario'
            },
            'cash_conversion_cycle': {
                'value': safe_div(cuentas_por_cobrar * 30, ingresos) + safe_div(inventarios * 30, costo_ventas if costo_ventas > 0 else 1) - safe_div(cuentas_por_pagar * 30, costo_ventas if costo_ventas > 0 else 1),
                'label': 'Ciclo de Conversión de Efectivo',
                'formula': 'DSO + DIO - DPO',
                'interpretation': 'Días para convertir inversión en efectivo'
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
