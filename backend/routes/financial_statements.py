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
from services.ai_financial_analysis import generate_financial_analysis

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
            },
            'ronic': {
                'value': safe_pct(nopat, capital_invertido) if capital_invertido > 0 else 0,
                'label': 'RONIC',
                'formula': 'NOPAT / Capital Invertido Nuevo',
                'interpretation': 'Retorno sobre nuevo capital invertido'
            },
            'gmroi': {
                'value': safe_div(utilidad_bruta, inventarios) if inventarios > 0 else 0,
                'label': 'GMROI',
                'formula': 'Utilidad Bruta / Inventarios',
                'interpretation': 'Retorno de margen bruto sobre inventario'
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
            },
            'nwc_to_revenue': {
                'value': safe_pct((activo_circulante - pasivo_circulante), ingresos) if ingresos > 0 else 0,
                'label': 'NWC / Ingresos',
                'formula': 'Capital de Trabajo / Ingresos',
                'interpretation': 'Capital de trabajo como % de ingresos'
            },
            'capex_to_revenue': {
                'value': 0,  # Requiere datos de CapEx del flujo de efectivo
                'label': 'CapEx / Ingresos',
                'formula': 'CapEx / Ingresos',
                'interpretation': 'Inversión en activos como % de ingresos'
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
            'cash_runway': {
                'value': safe_div(efectivo, (income.get('gastos_venta', 0) + income.get('gastos_administracion', 0) + income.get('gastos_generales', 0))) if (income.get('gastos_venta', 0) + income.get('gastos_administracion', 0) + income.get('gastos_generales', 0)) > 0 else 999,
                'label': 'Cash Runway',
                'formula': 'Efectivo / Gastos Operativos Mensuales',
                'interpretation': 'Meses de operación con efectivo actual'
            },
            'cash_efficiency': {
                'value': safe_pct(utilidad_neta, efectivo) if efectivo > 0 else 0,
                'label': 'Eficiencia de Efectivo',
                'formula': 'Utilidad Neta / Efectivo',
                'interpretation': 'Retorno sobre efectivo disponible'
            },
            'cash_cycle': {
                'value': safe_div(cuentas_por_cobrar * 30, ingresos) + safe_div(inventarios * 30, costo_ventas if costo_ventas > 0 else 1) - safe_div(cuentas_por_pagar * 30, costo_ventas if costo_ventas > 0 else 1),
                'label': 'Ciclo de Efectivo',
                'formula': 'DSO + DIO - DPO',
                'interpretation': 'Días del ciclo de conversión de efectivo'
            },
            'working_capital': {
                'value': activo_circulante - pasivo_circulante,
                'label': 'Capital de Trabajo',
                'formula': 'Activo Circulante - Pasivo Circulante',
                'interpretation': 'Recursos disponibles para operar'
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
                'value': safe_div(deuda_total, ebitda) if ebitda > 0 else safe_div(pasivo_total - capital_contable, ebitda),
                'label': 'Deuda / EBITDA',
                'formula': 'Deuda Total / EBITDA',
                'interpretation': 'Años para pagar deuda con EBITDA'
            },
            'net_debt_to_ebitda': {
                'value': safe_div(deuda_total - efectivo, ebitda) if ebitda > 0 else 0,
                'label': 'Deuda Neta / EBITDA',
                'formula': '(Deuda Total - Efectivo) / EBITDA',
                'interpretation': 'Años para pagar deuda neta con EBITDA'
            },
            'interest_coverage': {
                'value': safe_div(ebitda, intereses) if intereses > 0 else 999,
                'label': 'Cobertura de Intereses',
                'formula': 'EBITDA / Intereses',
                'interpretation': 'Veces que se pueden pagar los intereses'
            },
            'financial_leverage': {
                'value': safe_div(activo_total, capital_contable),
                'label': 'Apalancamiento Financiero',
                'formula': 'Activos Totales / Capital Contable',
                'interpretation': 'Multiplicador del capital'
            },
            'liability_ratio': {
                'value': safe_div(pasivo_total, capital_contable),
                'label': 'Razón de Pasivo',
                'formula': 'Pasivo Total / Capital Contable',
                'interpretation': 'Proporción pasivo vs capital'
            },
            'debt_ratio': {
                'value': safe_pct(deuda_total, activo_total),
                'label': 'Razón de Deuda',
                'formula': 'Deuda Total / Activos Totales',
                'interpretation': 'Porcentaje de activos financiados con deuda'
            },
            'cost_of_debt': {
                'value': safe_pct(intereses, deuda_total) if deuda_total > 0 else 0,
                'label': 'Costo de Deuda',
                'formula': 'Intereses / Deuda Total',
                'interpretation': 'Tasa efectiva de interés'
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


@router.get("/trends")
async def get_financial_trends(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    limit: int = Query(12, description="Número de períodos a incluir")
):
    """Get trends data for all available periods"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get all periods sorted descending
    pipeline = [
        {'$match': {'company_id': company_id}},
        {'$group': {
            '_id': '$periodo',
            'tipos': {'$addToSet': '$tipo'},
            'updated_at': {'$max': '$updated_at'}
        }},
        {'$sort': {'_id': -1}},
        {'$limit': limit}
    ]
    
    period_results = await db.financial_statements.aggregate(pipeline).to_list(limit)
    
    # Sort ascending for chronological order
    period_results.sort(key=lambda x: x['_id'])
    
    trends_data = []
    
    for period_info in period_results:
        periodo = period_info['_id']
        
        # Get income statement
        income_stmt = await db.financial_statements.find_one({
            'company_id': company_id,
            'tipo': 'estado_resultados',
            'periodo': periodo
        })
        
        # Get balance sheet
        balance_sheet = await db.financial_statements.find_one({
            'company_id': company_id,
            'tipo': 'balance_general',
            'periodo': periodo
        })
        
        if not income_stmt and not balance_sheet:
            continue
        
        income_data = income_stmt.get('datos', {}) if income_stmt else {}
        balance_data = balance_sheet.get('datos', {}) if balance_sheet else {}
        
        metrics = calculate_financial_metrics(income_data, balance_data)
        
        trends_data.append({
            'periodo': periodo,
            'has_income_statement': income_stmt is not None,
            'has_balance_sheet': balance_sheet is not None,
            'metrics': metrics,
            'income_statement': income_data,
            'balance_sheet': balance_data
        })
    
    return {
        "periods_count": len(trends_data),
        "data": trends_data
    }


@router.get("/aggregated")
async def get_aggregated_metrics(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    period_type: str = Query(..., description="Tipo de período: monthly, quarterly, annual"),
    period_value: str = Query(..., description="Valor del período: 2024-01, Q1-2024, 2024, last_month, last_quarter, last_year")
):
    """Get aggregated financial metrics for a specific period type"""
    company_id = await get_active_company_id(request, current_user)
    
    # Determine which months to aggregate
    months_to_aggregate = []
    
    if period_type == "monthly":
        # Single month: 2024-01
        months_to_aggregate = [period_value]
        
    elif period_type == "quarterly":
        # Quarter: Q1-2024, Q2-2024, etc.
        if period_value.startswith("Q"):
            parts = period_value.split("-")
            quarter = int(parts[0][1])  # Q1 -> 1
            year = parts[1]
            quarter_months = {
                1: ["01", "02", "03"],
                2: ["04", "05", "06"],
                3: ["07", "08", "09"],
                4: ["10", "11", "12"]
            }
            months_to_aggregate = [f"{year}-{m}" for m in quarter_months.get(quarter, [])]
        elif period_value == "last_quarter":
            # Calculate last complete quarter
            from datetime import datetime
            now = datetime.now()
            current_quarter = (now.month - 1) // 3 + 1
            last_quarter = current_quarter - 1 if current_quarter > 1 else 4
            year = now.year if current_quarter > 1 else now.year - 1
            quarter_months = {
                1: ["01", "02", "03"],
                2: ["04", "05", "06"],
                3: ["07", "08", "09"],
                4: ["10", "11", "12"]
            }
            months_to_aggregate = [f"{year}-{m}" for m in quarter_months[last_quarter]]
            
    elif period_type == "annual":
        # Annual: 2024
        if period_value == "last_year":
            from datetime import datetime
            year = str(datetime.now().year - 1)
        else:
            year = period_value
        months_to_aggregate = [f"{year}-{str(m).zfill(2)}" for m in range(1, 13)]
        
    elif period_type == "last_month":
        from datetime import datetime
        now = datetime.now()
        last_month = now.month - 1 if now.month > 1 else 12
        year = now.year if now.month > 1 else now.year - 1
        months_to_aggregate = [f"{year}-{str(last_month).zfill(2)}"]
    
    # Fetch all data for the periods
    aggregated_income = {
        'ingresos': 0, 'costo_ventas': 0, 'utilidad_bruta': 0,
        'gastos_venta': 0, 'gastos_administracion': 0, 'gastos_generales': 0,
        'utilidad_operativa': 0, 'otros_ingresos': 0, 'gastos_financieros': 0,
        'otros_gastos': 0, 'utilidad_antes_impuestos': 0, 'impuestos': 0,
        'utilidad_neta': 0, 'depreciacion': 0, 'amortizacion': 0, 'intereses': 0, 'ebitda': 0
    }
    
    # For balance sheet, we take the latest period
    latest_balance = None
    periods_found = []
    
    for periodo in months_to_aggregate:
        # Get income statement
        income_stmt = await db.financial_statements.find_one({
            'company_id': company_id,
            'tipo': 'estado_resultados',
            'periodo': periodo
        })
        
        if income_stmt:
            periods_found.append(periodo)
            data = income_stmt.get('datos', {})
            for key in aggregated_income:
                if key in data:
                    aggregated_income[key] += data.get(key, 0)
        
        # Get balance sheet (keep latest)
        balance_sheet = await db.financial_statements.find_one({
            'company_id': company_id,
            'tipo': 'balance_general',
            'periodo': periodo
        })
        
        if balance_sheet:
            latest_balance = balance_sheet.get('datos', {})
    
    if not periods_found:
        raise HTTPException(status_code=404, detail=f"No hay datos financieros para el período solicitado")
    
    # Calculate aggregated EBITDA
    aggregated_income['ebitda'] = (
        aggregated_income['utilidad_operativa'] + 
        aggregated_income['depreciacion'] + 
        aggregated_income['amortizacion']
    )
    
    # Calculate metrics with aggregated data
    balance_data = latest_balance or {}
    metrics = calculate_financial_metrics(aggregated_income, balance_data)
    
    # Generate period label
    period_labels = {
        'es': {
            'monthly': 'Mensual',
            'quarterly': 'Trimestral', 
            'annual': 'Anual'
        }
    }
    
    return {
        "period_type": period_type,
        "period_value": period_value,
        "periods_included": periods_found,
        "periods_count": len(periods_found),
        "has_income_statement": len(periods_found) > 0,
        "has_balance_sheet": latest_balance is not None,
        "metrics": metrics,
        "income_statement": aggregated_income,
        "balance_sheet": balance_data
    }


@router.get("/ai-analysis")
async def get_ai_financial_analysis(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    period_type: str = Query(..., description="Tipo de período: monthly, quarterly, annual"),
    period_value: str = Query(..., description="Valor del período"),
    language: str = Query("es", description="Language: es, en, pt")
):
    """Get AI-generated financial analysis for a specific period"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get company info
    company = await db.companies.find_one({'id': company_id}, {'_id': 0})
    company_name = company.get('nombre', 'Empresa') if company else 'Empresa'
    
    # Get aggregated data for the period
    # Determine which months to aggregate
    months_to_aggregate = []
    
    if period_type == "monthly":
        months_to_aggregate = [period_value]
    elif period_type == "quarterly":
        if period_value.startswith("Q"):
            parts = period_value.split("-")
            quarter = int(parts[0][1])
            year = parts[1]
            quarter_months = {
                1: ["01", "02", "03"],
                2: ["04", "05", "06"],
                3: ["07", "08", "09"],
                4: ["10", "11", "12"]
            }
            months_to_aggregate = [f"{year}-{m}" for m in quarter_months.get(quarter, [])]
    elif period_type == "annual":
        year = period_value
        months_to_aggregate = [f"{year}-{str(m).zfill(2)}" for m in range(1, 13)]
    
    # Fetch and aggregate data
    aggregated_income = {
        'ingresos': 0, 'costo_ventas': 0, 'utilidad_bruta': 0,
        'gastos_venta': 0, 'gastos_administracion': 0, 'gastos_generales': 0,
        'utilidad_operativa': 0, 'otros_ingresos': 0, 'gastos_financieros': 0,
        'otros_gastos': 0, 'utilidad_antes_impuestos': 0, 'impuestos': 0,
        'utilidad_neta': 0, 'depreciacion': 0, 'amortizacion': 0, 'intereses': 0, 'ebitda': 0
    }
    
    latest_balance = None
    periods_found = []
    
    for periodo in months_to_aggregate:
        income_stmt = await db.financial_statements.find_one({
            'company_id': company_id,
            'tipo': 'estado_resultados',
            'periodo': periodo
        })
        
        if income_stmt:
            periods_found.append(periodo)
            data = income_stmt.get('datos', {})
            for key in aggregated_income:
                if key in data:
                    aggregated_income[key] += data.get(key, 0)
        
        balance_sheet = await db.financial_statements.find_one({
            'company_id': company_id,
            'tipo': 'balance_general',
            'periodo': periodo
        })
        
        if balance_sheet:
            latest_balance = balance_sheet.get('datos', {})
    
    if not periods_found:
        raise HTTPException(status_code=404, detail="No hay datos financieros para el período solicitado")
    
    # Calculate EBITDA
    aggregated_income['ebitda'] = (
        aggregated_income['utilidad_operativa'] + 
        aggregated_income['depreciacion'] + 
        aggregated_income['amortizacion']
    )
    
    # Calculate metrics
    balance_data = latest_balance or {}
    metrics = calculate_financial_metrics(aggregated_income, balance_data)
    
    # Generate AI analysis
    period_label = f"{period_type}: {period_value}"
    if len(periods_found) > 1:
        period_label = f"{period_value} ({', '.join(periods_found)})"
    
    analysis = await generate_financial_analysis(
        metrics=metrics,
        income_statement=aggregated_income,
        balance_sheet=balance_data,
        company_name=company_name,
        period=period_label,
        language=language
    )
    
    return {
        "period_type": period_type,
        "period_value": period_value,
        "periods_included": periods_found,
        "company_name": company_name,
        "analysis": analysis
    }


@router.get("/available-periods")
async def get_available_periods_detailed(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Get detailed list of available periods for selection UI"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get all periods
    pipeline = [
        {'$match': {'company_id': company_id, 'tipo': 'estado_resultados'}},
        {'$group': {'_id': '$periodo'}},
        {'$sort': {'_id': -1}}
    ]
    
    results = await db.financial_statements.aggregate(pipeline).to_list(100)
    available_months = [r['_id'] for r in results]
    
    # Build response with different period types
    month_names_es = {
        '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
        '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
        '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
    }
    
    # Specific months
    specific_months = []
    for m in available_months:
        year, month = m.split('-')
        specific_months.append({
            'value': m,
            'label': f"{month_names_es.get(month, month)} {year}",
            'type': 'monthly'
        })
    
    # Quarters (only if we have data for all months in the quarter)
    quarters = []
    years = sorted(set([m.split('-')[0] for m in available_months]), reverse=True)
    
    for year in years:
        for q in range(4, 0, -1):
            quarter_months = {
                1: ['01', '02', '03'],
                2: ['04', '05', '06'],
                3: ['07', '08', '09'],
                4: ['10', '11', '12']
            }
            months_in_quarter = [f"{year}-{m}" for m in quarter_months[q]]
            months_available = [m for m in months_in_quarter if m in available_months]
            
            if months_available:
                quarters.append({
                    'value': f"Q{q}-{year}",
                    'label': f"Q{q} {year}",
                    'type': 'quarterly',
                    'months_available': len(months_available),
                    'months_total': 3
                })
    
    # Annual
    annual = []
    for year in years:
        months_in_year = [m for m in available_months if m.startswith(year)]
        if months_in_year:
            annual.append({
                'value': year,
                'label': f"Año {year}",
                'type': 'annual',
                'months_available': len(months_in_year)
            })
    
    # Generic periods
    generic = [
        {'value': 'last_month', 'label': 'Último Mes', 'type': 'generic'},
        {'value': 'last_quarter', 'label': 'Último Trimestre', 'type': 'generic'},
        {'value': 'last_year', 'label': 'Último Año', 'type': 'generic'}
    ]
    
    return {
        "specific_months": specific_months,
        "quarters": quarters,
        "annual": annual,
        "generic": generic,
        "raw_periods": available_months
    }


@router.get("/sankey/{periodo}")
async def get_sankey_data(
    request: Request,
    periodo: str,
    current_user: Dict = Depends(get_current_user)
):
    """Get data formatted for Sankey diagram of income statement"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get income statement
    income_stmt = await db.financial_statements.find_one({
        'company_id': company_id,
        'tipo': 'estado_resultados',
        'periodo': periodo
    })
    
    if not income_stmt:
        raise HTTPException(status_code=404, detail=f"No hay estado de resultados para {periodo}")
    
    data = income_stmt.get('datos', {})
    
    ingresos = abs(data.get('ingresos', 0))
    costo_ventas = abs(data.get('costo_ventas', 0))
    utilidad_bruta = abs(data.get('utilidad_bruta', 0))
    gastos_venta = abs(data.get('gastos_venta', 0))
    gastos_admin = abs(data.get('gastos_administracion', 0))
    gastos_generales = abs(data.get('gastos_generales', 0))
    otros_gastos = abs(data.get('otros_gastos', 0))
    gastos_financieros = abs(data.get('gastos_financieros', 0))
    utilidad_operativa = abs(data.get('utilidad_operativa', 0))
    impuestos = abs(data.get('impuestos', 0))
    utilidad_neta = abs(data.get('utilidad_neta', 0))
    otros_ingresos = abs(data.get('otros_ingresos', 0))
    
    # Total de gastos operativos
    total_gastos_operativos = gastos_venta + gastos_admin + gastos_generales
    
    # Calcular otros gastos no operativos
    total_otros_gastos = otros_gastos + gastos_financieros
    
    # Build Sankey nodes
    nodes = [
        {"name": "Ingresos"},           # 0
        {"name": "Costo de Ventas"},    # 1
        {"name": "Utilidad Bruta"},     # 2
        {"name": "Gastos de Venta"},    # 3
        {"name": "Gastos Admin"},       # 4
        {"name": "Gastos Generales"},   # 5
        {"name": "Utilidad Operativa"}, # 6
        {"name": "Otros Gastos"},       # 7
        {"name": "Impuestos"},          # 8
        {"name": "Utilidad Neta"},      # 9
    ]
    
    # Build Sankey links
    links = []
    
    # Ingresos -> Costo de Ventas
    if costo_ventas > 0:
        links.append({"source": 0, "target": 1, "value": costo_ventas, "color": "#ef4444"})
    
    # Ingresos -> Utilidad Bruta
    if utilidad_bruta > 0:
        links.append({"source": 0, "target": 2, "value": utilidad_bruta, "color": "#22c55e"})
    
    # Utilidad Bruta -> Gastos de Venta
    if gastos_venta > 0:
        links.append({"source": 2, "target": 3, "value": gastos_venta, "color": "#f97316"})
    
    # Utilidad Bruta -> Gastos Admin
    if gastos_admin > 0:
        links.append({"source": 2, "target": 4, "value": gastos_admin, "color": "#f97316"})
    
    # Utilidad Bruta -> Gastos Generales
    if gastos_generales > 0:
        links.append({"source": 2, "target": 5, "value": gastos_generales, "color": "#f97316"})
    
    # Utilidad Bruta -> Utilidad Operativa
    if utilidad_operativa > 0:
        links.append({"source": 2, "target": 6, "value": utilidad_operativa, "color": "#22c55e"})
    
    # Utilidad Operativa -> Otros Gastos
    if total_otros_gastos > 0:
        links.append({"source": 6, "target": 7, "value": total_otros_gastos, "color": "#ef4444"})
    
    # Utilidad Operativa -> Impuestos
    if impuestos > 0:
        links.append({"source": 6, "target": 8, "value": impuestos, "color": "#a855f7"})
    
    # Utilidad Operativa -> Utilidad Neta
    if utilidad_neta > 0:
        links.append({"source": 6, "target": 9, "value": utilidad_neta, "color": "#10b981"})
    
    return {
        "periodo": periodo,
        "nodes": nodes,
        "links": links,
        "summary": {
            "ingresos": ingresos,
            "costo_ventas": costo_ventas,
            "utilidad_bruta": utilidad_bruta,
            "gastos_operativos": total_gastos_operativos,
            "utilidad_operativa": utilidad_operativa,
            "otros_gastos": total_otros_gastos,
            "impuestos": impuestos,
            "utilidad_neta": utilidad_neta
        }
    }
