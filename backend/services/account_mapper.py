"""
Account Mapper Service
Maps trial balance data from accounting systems (CONTALink, Alegra, QuickBooks, etc.)
to TaxnFin's standard income statement and balance sheet format.

SAT Account Coding (Mexico):
  1xx = Activos (Assets)
  2xx = Pasivos (Liabilities)  
  3xx = Capital Contable (Equity)
  4xx = Ingresos (Revenue)
  5xx = Costos (Cost of Sales)
  6xx = Gastos Operativos (Operating Expenses)
  7xx = Otros Ingresos/Gastos (Other Income/Expenses)
  8xx = Cuentas de Orden
"""
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


# SAT account code prefix → category mapping
INCOME_MAPPING = {
    '401': 'ingresos',
    '402': 'ingresos',
    '403': 'ingresos',
    '501': 'costo_ventas',
    '502': 'costo_ventas',
    '503': 'costo_ventas',
    '601': 'gastos_venta',
    '602': 'gastos_administracion',
    '603': 'gastos_generales',
    '604': 'gastos_administracion',
    '701': 'otros_ingresos',
    '702': 'gastos_financieros',
    '703': 'otros_gastos',
    '704': 'otros_gastos',
}

# Higher-level fallback mapping (2-digit prefix)
INCOME_MAPPING_2 = {
    '40': 'ingresos',
    '41': 'ingresos',
    '50': 'costo_ventas',
    '51': 'costo_ventas',
    '60': 'gastos_administracion',
    '61': 'gastos_venta',
    '62': 'gastos_generales',
    '70': 'otros_ingresos',
    '71': 'gastos_financieros',
    '72': 'otros_gastos',
}

BALANCE_MAPPING = {
    '101': 'efectivo',
    '102': 'bancos',
    '103': 'inversiones_temporales',
    '105': 'cuentas_por_cobrar',
    '106': 'cuentas_por_cobrar',
    '108': 'inventarios',
    '110': 'pagos_anticipados',
    '115': 'iva_acreditable',
    '120': 'terrenos',
    '121': 'edificios',
    '122': 'maquinaria',
    '123': 'equipo_transporte',
    '124': 'equipo_computo',
    '125': 'mobiliario',
    '126': 'depreciacion_acumulada',
    '130': 'activos_intangibles',
    '201': 'proveedores',
    '206': 'impuestos_por_pagar',
    '208': 'acreedores_diversos',
    '210': 'prestamos_bancarios_cp',
    '215': 'iva_trasladado',
    '250': 'prestamos_bancarios_lp',
    '251': 'deuda_largo_plazo',
    '301': 'capital_social',
    '302': 'reserva_legal',
    '304': 'resultados_acumulados',
    '305': 'resultado_ejercicio',
}

BALANCE_MAPPING_2 = {
    '10': 'activo_circulante_otro',
    '11': 'activo_circulante_otro',
    '12': 'activo_fijo',
    '13': 'activo_intangible',
    '14': 'activo_diferido',
    '20': 'pasivo_circulante',
    '21': 'pasivo_circulante',
    '22': 'pasivo_circulante',
    '25': 'pasivo_largo_plazo',
    '26': 'pasivo_largo_plazo',
    '30': 'capital_contable',
    '31': 'capital_contable',
}


def _get_net_amount(item: Dict) -> float:
    """Extract net amount from a trial balance item.
    For revenue accounts (4xx): credit - debit
    For expense accounts (5xx, 6xx, 7xx): debit - credit
    For asset accounts (1xx): debit - credit
    For liability/equity (2xx, 3xx): credit - debit
    """
    debit = float(item.get('debit', 0) or item.get('debe', 0) or item.get('cargos', 0) or 0)
    credit = float(item.get('credit', 0) or item.get('haber', 0) or item.get('abonos', 0) or 0)
    
    # Try saldo_final first
    saldo = item.get('saldo_final', item.get('balance', item.get('saldo', None)))
    if saldo is not None:
        try:
            return abs(float(saldo))
        except (ValueError, TypeError):
            pass
    
    code = str(item.get('account_code', item.get('codigo', item.get('account_number', '')))).strip()
    
    if code.startswith(('4', '2', '3')):
        return credit - debit  # Revenue, liabilities, equity: credit balance
    else:
        return debit - credit  # Assets, costs, expenses: debit balance


def map_trial_balance_to_statements(items: List[Dict]) -> Dict:
    """
    Map a trial balance from any accounting system to TaxnFin's standard format.
    
    Each item should have:
      - account_code / codigo: SAT account code
      - account_name / nombre / description: Account name
      - debit / debe / cargos: Debit amount
      - credit / haber / abonos: Credit amount
      - saldo_final / balance / saldo: Ending balance (optional)
    """
    income = {
        'ingresos': 0, 'costo_ventas': 0, 'utilidad_bruta': 0,
        'gastos_venta': 0, 'gastos_administracion': 0, 'gastos_generales': 0,
        'utilidad_operativa': 0, 'otros_ingresos': 0, 'gastos_financieros': 0,
        'otros_gastos': 0, 'utilidad_antes_impuestos': 0, 'impuestos': 0,
        'utilidad_neta': 0, 'depreciacion': 0, 'amortizacion': 0, 'intereses': 0,
        'raw_data': [],
    }
    
    balance = {
        'efectivo': 0, 'cuentas_por_cobrar': 0, 'inventarios': 0,
        'otros_activos_circulantes': 0, 'activo_circulante': 0,
        'activos_fijos_neto': 0, 'activos_intangibles': 0,
        'otros_activos': 0, 'activo_total': 0,
        'proveedores': 0, 'impuestos_por_pagar': 0,
        'prestamos_corto_plazo': 0, 'otros_pasivos_circulantes': 0,
        'pasivo_circulante': 0, 'deuda_largo_plazo': 0,
        'otros_pasivos_lp': 0, 'pasivo_total': 0,
        'capital_social': 0, 'resultados_acumulados': 0,
        'resultado_ejercicio': 0, 'capital_contable': 0,
        'raw_data': [],
    }
    
    for item in items:
        code = str(item.get('account_code', item.get('codigo', item.get('account_number', '')))).strip()
        name = str(item.get('account_name', item.get('nombre', item.get('description', '')))).strip()
        amount = _get_net_amount(item)
        
        if not code or amount == 0:
            continue
        
        # Normalize code (remove dots, dashes)
        code_clean = code.replace('.', '').replace('-', '').replace(' ', '')
        prefix3 = code_clean[:3]
        prefix2 = code_clean[:2]
        prefix1 = code_clean[:1]
        
        # Income statement accounts (4xx-7xx)
        if prefix1 in ('4', '5', '6', '7'):
            category = INCOME_MAPPING.get(prefix3) or INCOME_MAPPING_2.get(prefix2)
            
            if not category:
                # Fallback by first digit
                if prefix1 == '4': category = 'ingresos'
                elif prefix1 == '5': category = 'costo_ventas'
                elif prefix1 == '6': category = 'gastos_administracion'
                elif prefix1 == '7': category = 'otros_gastos'
            
            if category:
                income[category] = income.get(category, 0) + abs(amount)
                income['raw_data'].append({'code': code, 'name': name, 'amount': amount, 'category': category})
            
            # Detect depreciation / amortization / interest by name
            name_lower = name.lower()
            if any(w in name_lower for w in ['deprecia', 'depreciacion']):
                income['depreciacion'] += abs(amount)
            elif any(w in name_lower for w in ['amortiza', 'amortizacion']):
                income['amortizacion'] += abs(amount)
            elif any(w in name_lower for w in ['interes', 'intereses']):
                income['intereses'] += abs(amount)
        
        # Balance sheet accounts (1xx-3xx)
        elif prefix1 in ('1', '2', '3'):
            cat = BALANCE_MAPPING.get(prefix3) or BALANCE_MAPPING_2.get(prefix2)
            
            if cat in ('efectivo', 'bancos', 'inversiones_temporales'):
                balance['efectivo'] += abs(amount)
            elif cat == 'cuentas_por_cobrar':
                balance['cuentas_por_cobrar'] += abs(amount)
            elif cat == 'inventarios':
                balance['inventarios'] += abs(amount)
            elif cat in ('pagos_anticipados', 'iva_acreditable', 'activo_circulante_otro'):
                balance['otros_activos_circulantes'] += abs(amount)
            elif cat in ('terrenos', 'edificios', 'maquinaria', 'equipo_transporte', 'equipo_computo', 'mobiliario', 'activo_fijo'):
                balance['activos_fijos_neto'] += abs(amount)
            elif cat == 'depreciacion_acumulada':
                balance['activos_fijos_neto'] -= abs(amount)
            elif cat in ('activos_intangibles', 'activo_intangible', 'activo_diferido'):
                balance['activos_intangibles'] += abs(amount)
            elif cat in ('proveedores',):
                balance['proveedores'] += abs(amount)
            elif cat in ('impuestos_por_pagar', 'iva_trasladado'):
                balance['impuestos_por_pagar'] += abs(amount)
            elif cat in ('prestamos_bancarios_cp', 'acreedores_diversos', 'pasivo_circulante'):
                if prefix2 in ('20', '21', '22'):
                    balance['otros_pasivos_circulantes'] += abs(amount)
                else:
                    balance['prestamos_corto_plazo'] += abs(amount)
            elif cat in ('prestamos_bancarios_lp', 'deuda_largo_plazo', 'pasivo_largo_plazo'):
                balance['deuda_largo_plazo'] += abs(amount)
            elif cat == 'capital_social':
                balance['capital_social'] += abs(amount)
            elif cat in ('resultados_acumulados', 'reserva_legal'):
                balance['resultados_acumulados'] += abs(amount)
            elif cat == 'resultado_ejercicio':
                balance['resultado_ejercicio'] += abs(amount)
            elif cat == 'capital_contable':
                balance['capital_contable'] += abs(amount)
            else:
                # Fallback by first digit
                if prefix1 == '1':
                    if prefix2 in ('10', '11'):
                        balance['otros_activos_circulantes'] += abs(amount)
                    else:
                        balance['otros_activos'] += abs(amount)
                elif prefix1 == '2':
                    if prefix2 in ('20', '21', '22'):
                        balance['otros_pasivos_circulantes'] += abs(amount)
                    else:
                        balance['otros_pasivos_lp'] += abs(amount)
                elif prefix1 == '3':
                    balance['capital_contable'] += abs(amount)
            
            balance['raw_data'].append({'code': code, 'name': name, 'amount': amount, 'category': cat or 'unmapped'})
    
    # Calculate computed fields for income statement
    income['utilidad_bruta'] = income['ingresos'] - income['costo_ventas']
    total_gastos_op = income['gastos_venta'] + income['gastos_administracion'] + income['gastos_generales']
    income['utilidad_operativa'] = income['utilidad_bruta'] - total_gastos_op
    income['utilidad_antes_impuestos'] = (
        income['utilidad_operativa'] + income['otros_ingresos'] 
        - income['gastos_financieros'] - income['otros_gastos']
    )
    # Estimate taxes if not explicit (30% standard Mexico)
    if income['impuestos'] == 0 and income['utilidad_antes_impuestos'] > 0:
        income['impuestos'] = income['utilidad_antes_impuestos'] * 0.30
    income['utilidad_neta'] = income['utilidad_antes_impuestos'] - income['impuestos']
    income['ebitda'] = income['utilidad_operativa'] + income['depreciacion'] + income['amortizacion']
    
    # Calculate computed fields for balance sheet
    balance['activo_circulante'] = (
        balance['efectivo'] + balance['cuentas_por_cobrar'] + 
        balance['inventarios'] + balance['otros_activos_circulantes']
    )
    balance['activo_total'] = (
        balance['activo_circulante'] + balance['activos_fijos_neto'] + 
        balance['activos_intangibles'] + balance['otros_activos']
    )
    balance['pasivo_circulante'] = (
        balance['proveedores'] + balance['impuestos_por_pagar'] + 
        balance['prestamos_corto_plazo'] + balance['otros_pasivos_circulantes']
    )
    balance['pasivo_total'] = (
        balance['pasivo_circulante'] + balance['deuda_largo_plazo'] + balance['otros_pasivos_lp']
    )
    if balance['capital_contable'] == 0:
        balance['capital_contable'] = (
            balance['capital_social'] + balance['resultados_acumulados'] + balance['resultado_ejercicio']
        )
    
    has_income = income['ingresos'] > 0 or income['costo_ventas'] > 0
    has_balance = balance['activo_total'] > 0 or balance['pasivo_total'] > 0
    
    return {
        'income': income if has_income else None,
        'balance': balance if has_balance else None,
    }
