import json
import csv
import io
from typing import Dict, Any, List
from datetime import datetime
from lxml import etree
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

class AccountingExportService:
    """
    Servicio de exportación a formatos contables
    Soporta: COI, XML Fiscal, Alegra
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    async def export_to_coi(
        self,
        company_id: str,
        fecha_inicio: datetime,
        fecha_fin: datetime
    ) -> str:
        """
        Exporta a formato COI (Contabilidad)
        Formato usado por sistemas contables mexicanos
        """
        
        transactions = await self.db.transactions.find({
            'company_id': company_id,
            'fecha_transaccion': {
                '$gte': fecha_inicio.isoformat(),
                '$lte': fecha_fin.isoformat()
            },
            'es_real': True
        }).to_list(10000)
        
        company = await self.db.companies.find_one({'id': company_id}, {'_id': 0})
        
        # Formato COI: CSV con estructura específica
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header COI
        writer.writerow([
            'RFC',
            'Razón Social',
            'Fecha',
            'Tipo Póliza',
            'Número Póliza',
            'Cuenta',
            'SubCuenta',
            'Concepto',
            'Cargo',
            'Abono',
            'Referencia'
        ])
        
        poliza_num = 1
        for txn in transactions:
            fecha = datetime.fromisoformat(txn['fecha_transaccion']) if isinstance(txn['fecha_transaccion'], str) else txn['fecha_transaccion']
            
            if txn['tipo_transaccion'] == 'ingreso':
                # Cuenta de bancos (cargo) y cuenta de ingresos (abono)
                writer.writerow([
                    company.get('rfc', ''),
                    company.get('nombre', ''),
                    fecha.strftime('%Y-%m-%d'),
                    'I',  # Ingreso
                    f'ING-{poliza_num:06d}',
                    '1020',  # Bancos
                    '001',
                    txn['concepto'],
                    f"{txn['monto']:.2f}",
                    '0.00',
                    txn.get('referencia', '')
                ])
                writer.writerow([
                    company.get('rfc', ''),
                    company.get('nombre', ''),
                    fecha.strftime('%Y-%m-%d'),
                    'I',
                    f'ING-{poliza_num:06d}',
                    '4010',  # Ingresos
                    '001',
                    txn['concepto'],
                    '0.00',
                    f"{txn['monto']:.2f}",
                    txn.get('referencia', '')
                ])
            else:
                # Cuenta de gastos (cargo) y cuenta de bancos (abono)
                writer.writerow([
                    company.get('rfc', ''),
                    company.get('nombre', ''),
                    fecha.strftime('%Y-%m-%d'),
                    'E',  # Egreso
                    f'EGR-{poliza_num:06d}',
                    '5010',  # Gastos
                    '001',
                    txn['concepto'],
                    f"{txn['monto']:.2f}",
                    '0.00',
                    txn.get('referencia', '')
                ])
                writer.writerow([
                    company.get('rfc', ''),
                    company.get('nombre', ''),
                    fecha.strftime('%Y-%m-%d'),
                    'E',
                    f'EGR-{poliza_num:06d}',
                    '1020',  # Bancos
                    '001',
                    txn['concepto'],
                    '0.00',
                    f"{txn['monto']:.2f}",
                    txn.get('referencia', '')
                ])
            
            poliza_num += 1
        
        return output.getvalue()
    
    async def export_to_xml_fiscal(
        self,
        company_id: str,
        fecha_inicio: datetime,
        fecha_fin: datetime
    ) -> str:
        """
        Exporta a XML Fiscal según estándar SAT
        Balanza de comprobación
        """
        
        transactions = await self.db.transactions.find({
            'company_id': company_id,
            'fecha_transaccion': {
                '$gte': fecha_inicio.isoformat(),
                '$lte': fecha_fin.isoformat()
            },
            'es_real': True
        }).to_list(10000)
        
        company = await self.db.companies.find_one({'id': company_id}, {'_id': 0})
        
        # Crear XML según anexo 24 SAT (Balanza de Comprobación)
        root = etree.Element('BalanzaComprobacion')
        root.set('Version', '1.3')
        root.set('RFC', company.get('rfc', ''))
        root.set('Mes', str(fecha_inicio.month).zfill(2))
        root.set('Anio', str(fecha_inicio.year))
        root.set('TipoEnvio', 'N')  # Normal
        
        # Agregar cuentas
        cuentas = {}
        
        for txn in transactions:
            if txn['tipo_transaccion'] == 'ingreso':
                # Bancos
                if '1020' not in cuentas:
                    cuentas['1020'] = {'debe': 0, 'haber': 0}
                cuentas['1020']['debe'] += txn['monto']
                
                # Ingresos
                if '4010' not in cuentas:
                    cuentas['4010'] = {'debe': 0, 'haber': 0}
                cuentas['4010']['haber'] += txn['monto']
            else:
                # Gastos
                if '5010' not in cuentas:
                    cuentas['5010'] = {'debe': 0, 'haber': 0}
                cuentas['5010']['debe'] += txn['monto']
                
                # Bancos
                if '1020' not in cuentas:
                    cuentas['1020'] = {'debe': 0, 'haber': 0}
                cuentas['1020']['haber'] += txn['monto']
        
        cuentas_element = etree.SubElement(root, 'Ctas')
        
        for codigo, movimientos in sorted(cuentas.items()):
            cuenta = etree.SubElement(cuentas_element, 'Cuenta')
            cuenta.set('NumCta', codigo)
            cuenta.set('Desc', self._get_cuenta_nombre(codigo))
            cuenta.set('Nivel', '1')
            cuenta.set('Natur', 'D' if codigo.startswith(('1', '5')) else 'A')
            cuenta.set('SaldoIni', '0.00')
            cuenta.set('Debe', f"{movimientos['debe']:.2f}")
            cuenta.set('Haber', f"{movimientos['haber']:.2f}")
            saldo_final = movimientos['debe'] - movimientos['haber']
            cuenta.set('SaldoFin', f"{saldo_final:.2f}")
        
        return etree.tostring(root, encoding='unicode', pretty_print=True)
    
    def _get_cuenta_nombre(self, codigo: str) -> str:
        """Obtiene nombre de cuenta por código"""
        nombres = {
            '1020': 'Bancos',
            '4010': 'Ingresos por servicios',
            '5010': 'Gastos de operación'
        }
        return nombres.get(codigo, 'Cuenta contable')
    
    async def export_to_alegra(
        self,
        company_id: str,
        fecha_inicio: datetime,
        fecha_fin: datetime
    ) -> str:
        """
        Exporta a formato Alegra (JSON)
        Alegra es un software contable popular en Latinoamérica
        """
        
        transactions = await self.db.transactions.find({
            'company_id': company_id,
            'fecha_transaccion': {
                '$gte': fecha_inicio.isoformat(),
                '$lte': fecha_fin.isoformat()
            },
            'es_real': True
        }).to_list(10000)
        
        company = await self.db.companies.find_one({'id': company_id}, {'_id': 0})
        bank_accounts = await self.db.bank_accounts.find(
            {'company_id': company_id},
            {'_id': 0}
        ).to_list(100)
        
        # Crear diccionario de cuentas bancarias
        bank_dict = {acc['id']: acc for acc in bank_accounts}
        
        # Formato JSON de Alegra
        alegra_data = {
            'metadata': {
                'company': {
                    'name': company.get('nombre', ''),
                    'identification': company.get('rfc', ''),
                    'currency': company.get('moneda_base', 'MXN')
                },
                'export_date': datetime.now().isoformat(),
                'period_start': fecha_inicio.isoformat(),
                'period_end': fecha_fin.isoformat(),
                'format': 'alegra_v1'
            },
            'journal_entries': []
        }
        
        for idx, txn in enumerate(transactions, start=1):
            fecha = datetime.fromisoformat(txn['fecha_transaccion']) if isinstance(txn['fecha_transaccion'], str) else txn['fecha_transaccion']
            bank_acc = bank_dict.get(txn.get('bank_account_id'))
            
            entry = {
                'number': idx,
                'date': fecha.strftime('%Y-%m-%d'),
                'description': txn['concepto'],
                'reference': txn.get('referencia', ''),
                'items': []
            }
            
            if txn['tipo_transaccion'] == 'ingreso':
                # Cargo a Bancos
                entry['items'].append({
                    'account': {
                        'code': '1105',
                        'name': f"Bancos - {bank_acc.get('nombre', 'Principal') if bank_acc else 'Principal'}",
                        'type': 'asset'
                    },
                    'debit': txn['monto'],
                    'credit': 0,
                    'description': txn['concepto']
                })
                
                # Abono a Ingresos
                entry['items'].append({
                    'account': {
                        'code': '4135',
                        'name': 'Ingresos por servicios',
                        'type': 'income'
                    },
                    'debit': 0,
                    'credit': txn['monto'],
                    'description': txn['concepto']
                })
            else:
                # Cargo a Gastos
                entry['items'].append({
                    'account': {
                        'code': '5195',
                        'name': 'Gastos diversos',
                        'type': 'expense'
                    },
                    'debit': txn['monto'],
                    'credit': 0,
                    'description': txn['concepto']
                })
                
                # Abono a Bancos
                entry['items'].append({
                    'account': {
                        'code': '1105',
                        'name': f"Bancos - {bank_acc.get('nombre', 'Principal') if bank_acc else 'Principal'}",
                        'type': 'asset'
                    },
                    'debit': 0,
                    'credit': txn['monto'],
                    'description': txn['concepto']
                })
            
            alegra_data['journal_entries'].append(entry)
        
        return json.dumps(alegra_data, indent=2, ensure_ascii=False)
    
    async def export_cashflow_report(
        self,
        company_id: str,
        formato: str = 'excel'
    ) -> str:
        """
        Exporta reporte de cashflow completo (13 semanas)
        Formatos: excel, pdf, json
        """
        
        weeks = await self.db.cashflow_weeks.find(
            {'company_id': company_id}
        ).sort('fecha_inicio', 1).to_list(13)
        
        company = await self.db.companies.find_one({'id': company_id}, {'_id': 0})
        
        cashflow_data = []
        for week in weeks:
            transactions = await self.db.transactions.find({
                'company_id': company_id,
                'cashflow_week_id': week['id']
            }).to_list(1000)
            
            ingresos_reales = sum(t['monto'] for t in transactions if t['tipo_transaccion'] == 'ingreso' and t['es_real'])
            egresos_reales = sum(t['monto'] for t in transactions if t['tipo_transaccion'] == 'egreso' and t['es_real'])
            ingresos_proy = sum(t['monto'] for t in transactions if t['tipo_transaccion'] == 'ingreso' and t['es_proyeccion'])
            egresos_proy = sum(t['monto'] for t in transactions if t['tipo_transaccion'] == 'egreso' and t['es_proyeccion'])
            
            cashflow_data.append({
                'semana': week['numero_semana'],
                'fecha_inicio': week['fecha_inicio'],
                'fecha_fin': week['fecha_fin'],
                'saldo_inicial': week.get('saldo_inicial', 0),
                'ingresos_reales': ingresos_reales,
                'egresos_reales': egresos_reales,
                'ingresos_proyectados': ingresos_proy,
                'egresos_proyectados': egresos_proy,
                'flujo_neto_real': ingresos_reales - egresos_reales,
                'flujo_neto_proyectado': ingresos_proy - egresos_proy
            })
        
        if formato == 'json':
            return json.dumps({
                'company': company.get('nombre'),
                'export_date': datetime.now().isoformat(),
                'cashflow_weeks': cashflow_data
            }, indent=2, ensure_ascii=False)
        
        elif formato == 'excel':
            # CSV para Excel
            output = io.StringIO()
            writer = csv.writer(output)
            
            writer.writerow(['REPORTE DE FLUJO DE EFECTIVO - 13 SEMANAS ROLLING'])
            writer.writerow([f'Empresa: {company.get("nombre")}'])
            writer.writerow([f'Fecha: {datetime.now().strftime("%Y-%m-%d %H:%M")}'])
            writer.writerow([])
            
            writer.writerow([
                'Semana',
                'Fecha Inicio',
                'Fecha Fin',
                'Saldo Inicial',
                'Ingresos Reales',
                'Egresos Reales',
                'Ingresos Proyectados',
                'Egresos Proyectados',
                'Flujo Neto Real',
                'Flujo Neto Proyectado'
            ])
            
            for data in cashflow_data:
                writer.writerow([
                    data['semana'],
                    data['fecha_inicio'],
                    data['fecha_fin'],
                    f"{data['saldo_inicial']:.2f}",
                    f"{data['ingresos_reales']:.2f}",
                    f"{data['egresos_reales']:.2f}",
                    f"{data['ingresos_proyectados']:.2f}",
                    f"{data['egresos_proyectados']:.2f}",
                    f"{data['flujo_neto_real']:.2f}",
                    f"{data['flujo_neto_proyectado']:.2f}"
                ])
            
            return output.getvalue()
        
        return json.dumps(cashflow_data, indent=2, ensure_ascii=False)
