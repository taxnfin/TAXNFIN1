import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
import uuid
import copy
import logging

logger = logging.getLogger(__name__)

class ScenarioAnalysisService:
    """
    Servicio de análisis de escenarios 'qué pasaría si'
    Permite simular diferentes estrategias financieras y ver su impacto
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    async def create_scenario(
        self,
        company_id: str,
        nombre: str,
        descripcion: str,
        modificaciones: List[Dict[str, Any]],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Crea un nuevo escenario de simulación
        
        Args:
            company_id: ID de la empresa
            nombre: Nombre del escenario
            descripcion: Descripción del escenario
            modificaciones: Lista de cambios a aplicar
            user_id: Usuario que crea el escenario
            
        Modificaciones formato:
        [
            {
                'tipo': 'adelantar_pago',
                'transaction_id': 'xxx',
                'nueva_fecha': '2026-01-15',
                'razon': 'Aprovechar descuento pronto pago'
            },
            {
                'tipo': 'retrasar_cobro',
                'transaction_id': 'yyy',
                'nueva_fecha': '2026-02-01',
                'razon': 'Cliente solicita extensión'
            },
            {
                'tipo': 'ajustar_monto',
                'transaction_id': 'zzz',
                'nuevo_monto': 75000,
                'razon': 'Negociación de descuento'
            },
            {
                'tipo': 'eliminar_transaccion',
                'transaction_id': 'aaa',
                'razon': 'Cancelar compra'
            },
            {
                'tipo': 'agregar_transaccion',
                'concepto': 'Préstamo bancario',
                'monto': 500000,
                'tipo_transaccion': 'ingreso',
                'fecha_transaccion': '2026-01-20',
                'razon': 'Inyección de capital'
            }
        ]
        """
        
        # Crear snapshot del estado actual
        baseline = await self._create_baseline_snapshot(company_id)
        
        # Aplicar modificaciones y calcular nuevo estado
        simulated_state = await self._apply_modifications(
            company_id,
            baseline,
            modificaciones
        )
        
        # Comparar resultados
        comparison = self._compare_scenarios(baseline, simulated_state)
        
        # Guardar escenario
        scenario = {
            'id': str(uuid.uuid4()),
            'company_id': company_id,
            'nombre': nombre,
            'descripcion': descripcion,
            'modificaciones': modificaciones,
            'baseline': baseline,
            'simulated_state': simulated_state,
            'comparison': comparison,
            'created_by': user_id,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'activo': True
        }
        
        await self.db.scenarios.insert_one(scenario)
        
        return {
            'status': 'success',
            'scenario_id': scenario['id'],
            'nombre': nombre,
            'comparison': comparison
        }
    
    async def _create_baseline_snapshot(self, company_id: str) -> Dict[str, Any]:
        """Crea snapshot del estado actual del cashflow"""
        
        weeks = await self.db.cashflow_weeks.find(
            {'company_id': company_id}
        ).sort('fecha_inicio', 1).to_list(13)
        
        transactions = await self.db.transactions.find(
            {'company_id': company_id}
        ).to_list(1000)
        
        # Calcular flujo por semana
        weekly_flow = []
        for week in weeks:
            week_txns = [t for t in transactions if t['cashflow_week_id'] == week['id']]
            
            ingresos = sum(t['monto'] for t in week_txns if t['tipo_transaccion'] == 'ingreso')
            egresos = sum(t['monto'] for t in week_txns if t['tipo_transaccion'] == 'egreso')
            flujo_neto = ingresos - egresos
            
            weekly_flow.append({
                'semana': week['numero_semana'],
                'fecha_inicio': week['fecha_inicio'],
                'ingresos': ingresos,
                'egresos': egresos,
                'flujo_neto': flujo_neto
            })
        
        # Calcular saldo acumulado
        saldo_acumulado = 0
        for week_data in weekly_flow:
            saldo_acumulado += week_data['flujo_neto']
            week_data['saldo_acumulado'] = saldo_acumulado
        
        return {
            'weekly_flow': weekly_flow,
            'total_ingresos': sum(w['ingresos'] for w in weekly_flow),
            'total_egresos': sum(w['egresos'] for w in weekly_flow),
            'flujo_neto_total': sum(w['flujo_neto'] for w in weekly_flow),
            'saldo_final': saldo_acumulado
        }
    
    async def _apply_modifications(
        self,
        company_id: str,
        baseline: Dict[str, Any],
        modificaciones: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Aplica modificaciones al baseline y calcula nuevo estado"""
        
        # Obtener todas las transacciones
        transactions = await self.db.transactions.find(
            {'company_id': company_id}
        ).to_list(1000)
        
        # Clonar transacciones para simulación
        simulated_txns = copy.deepcopy(transactions)
        
        # Aplicar cada modificación
        for mod in modificaciones:
            if mod['tipo'] == 'adelantar_pago' or mod['tipo'] == 'retrasar_cobro':
                # Cambiar fecha de transacción
                for txn in simulated_txns:
                    if txn['id'] == mod['transaction_id']:
                        txn['fecha_transaccion'] = mod['nueva_fecha']
                        # Recalcular cashflow_week_id
                        nueva_fecha = datetime.fromisoformat(mod['nueva_fecha']) if isinstance(mod['nueva_fecha'], str) else mod['nueva_fecha']
                        txn['_modificado'] = True
                        txn['_razon'] = mod.get('razon', '')
                        break
            
            elif mod['tipo'] == 'ajustar_monto':
                # Cambiar monto de transacción
                for txn in simulated_txns:
                    if txn['id'] == mod['transaction_id']:
                        txn['_monto_original'] = txn['monto']
                        txn['monto'] = mod['nuevo_monto']
                        txn['_modificado'] = True
                        txn['_razon'] = mod.get('razon', '')
                        break
            
            elif mod['tipo'] == 'eliminar_transaccion':
                # Marcar transacción como eliminada
                for txn in simulated_txns:
                    if txn['id'] == mod['transaction_id']:
                        txn['_eliminado'] = True
                        txn['_razon'] = mod.get('razon', '')
                        break
            
            elif mod['tipo'] == 'agregar_transaccion':
                # Agregar nueva transacción simulada
                nueva_txn = {
                    'id': f"sim_{str(uuid.uuid4())}",
                    'company_id': company_id,
                    'concepto': mod['concepto'],
                    'monto': mod['monto'],
                    'tipo_transaccion': mod['tipo_transaccion'],
                    'fecha_transaccion': mod['fecha_transaccion'],
                    'cashflow_week_id': 'calculated',
                    '_agregado': True,
                    '_razon': mod.get('razon', '')
                }
                simulated_txns.append(nueva_txn)
        
        # Recalcular flujo con transacciones modificadas
        weeks = await self.db.cashflow_weeks.find(
            {'company_id': company_id}
        ).sort('fecha_inicio', 1).to_list(13)
        
        weekly_flow = []
        for week in weeks:
            # Filtrar transacciones para esta semana
            fecha_inicio = datetime.fromisoformat(week['fecha_inicio']) if isinstance(week['fecha_inicio'], str) else week['fecha_inicio']
            fecha_fin = datetime.fromisoformat(week['fecha_fin']) if isinstance(week['fecha_fin'], str) else week['fecha_fin']
            
            week_txns = []
            for t in simulated_txns:
                if t.get('_eliminado'):
                    continue
                
                fecha_txn = datetime.fromisoformat(t['fecha_transaccion']) if isinstance(t['fecha_transaccion'], str) else t['fecha_transaccion']
                if fecha_inicio <= fecha_txn <= fecha_fin:
                    week_txns.append(t)
            
            ingresos = sum(t['monto'] for t in week_txns if t['tipo_transaccion'] == 'ingreso')
            egresos = sum(t['monto'] for t in week_txns if t['tipo_transaccion'] == 'egreso')
            flujo_neto = ingresos - egresos
            
            weekly_flow.append({
                'semana': week['numero_semana'],
                'fecha_inicio': week['fecha_inicio'],
                'ingresos': ingresos,
                'egresos': egresos,
                'flujo_neto': flujo_neto
            })
        
        # Calcular saldo acumulado
        saldo_acumulado = 0
        for week_data in weekly_flow:
            saldo_acumulado += week_data['flujo_neto']
            week_data['saldo_acumulado'] = saldo_acumulado
        
        return {
            'weekly_flow': weekly_flow,
            'total_ingresos': sum(w['ingresos'] for w in weekly_flow),
            'total_egresos': sum(w['egresos'] for w in weekly_flow),
            'flujo_neto_total': sum(w['flujo_neto'] for w in weekly_flow),
            'saldo_final': saldo_acumulado,
            'modificaciones_aplicadas': len(modificaciones)
        }
    
    def _compare_scenarios(self, baseline: Dict[str, Any], simulated: Dict[str, Any]) -> Dict[str, Any]:
        """Compara baseline vs escenario simulado"""
        
        diff_ingresos = simulated['total_ingresos'] - baseline['total_ingresos']
        diff_egresos = simulated['total_egresos'] - baseline['total_egresos']
        diff_flujo_neto = simulated['flujo_neto_total'] - baseline['flujo_neto_total']
        diff_saldo_final = simulated['saldo_final'] - baseline['saldo_final']
        
        # Identificar semanas críticas
        semanas_criticas_baseline = [w for w in baseline['weekly_flow'] if w['saldo_acumulado'] < 0]
        semanas_criticas_simulado = [w for w in simulated['weekly_flow'] if w['saldo_acumulado'] < 0]
        
        mejora = diff_flujo_neto > 0
        resuelve_crisis = len(semanas_criticas_simulado) < len(semanas_criticas_baseline)
        
        return {
            'diferencia_ingresos': round(diff_ingresos, 2),
            'diferencia_egresos': round(diff_egresos, 2),
            'diferencia_flujo_neto': round(diff_flujo_neto, 2),
            'diferencia_saldo_final': round(diff_saldo_final, 2),
            'porcentaje_mejora': round((diff_flujo_neto / baseline['flujo_neto_total'] * 100) if baseline['flujo_neto_total'] != 0 else 0, 2),
            'mejora_liquidez': mejora,
            'resuelve_crisis_liquidez': resuelve_crisis,
            'semanas_criticas_evitadas': len(semanas_criticas_baseline) - len(semanas_criticas_simulado),
            'baseline_semanas_criticas': len(semanas_criticas_baseline),
            'simulado_semanas_criticas': len(semanas_criticas_simulado),
            'recomendacion': self._generate_recommendation(mejora, resuelve_crisis, diff_flujo_neto)
        }
    
    def _generate_recommendation(self, mejora: bool, resuelve_crisis: bool, diff: float) -> str:
        """Genera recomendación basada en resultados"""
        
        if resuelve_crisis:
            return "🟢 ALTAMENTE RECOMENDADO: Este escenario resuelve crisis de liquidez"
        elif mejora and diff > 50000:
            return "🟢 RECOMENDADO: Mejora significativa en flujo de efectivo"
        elif mejora:
            return "🟡 CONSIDERAR: Mejora moderada en flujo de efectivo"
        elif diff > -20000:
            return "🟡 NEUTRAL: Impacto mínimo en flujo de efectivo"
        else:
            return "🔴 NO RECOMENDADO: Deteriora flujo de efectivo"
    
    async def list_scenarios(self, company_id: str) -> List[Dict[str, Any]]:
        """Lista todos los escenarios de una empresa"""
        
        scenarios = await self.db.scenarios.find(
            {'company_id': company_id, 'activo': True},
            {'_id': 0, 'baseline': 0, 'simulated_state': 0}
        ).sort('created_at', -1).to_list(100)
        
        return scenarios
    
    async def get_scenario_detail(self, scenario_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene detalle completo de un escenario"""
        
        scenario = await self.db.scenarios.find_one(
            {'id': scenario_id, 'company_id': company_id, 'activo': True},
            {'_id': 0}
        )
        
        return scenario
    
    async def compare_multiple_scenarios(
        self,
        company_id: str,
        scenario_ids: List[str]
    ) -> Dict[str, Any]:
        """Compara múltiples escenarios lado a lado"""
        
        scenarios = []
        for scenario_id in scenario_ids:
            scenario = await self.get_scenario_detail(scenario_id, company_id)
            if scenario:
                scenarios.append({
                    'id': scenario['id'],
                    'nombre': scenario['nombre'],
                    'flujo_neto_total': scenario['simulated_state']['flujo_neto_total'],
                    'saldo_final': scenario['simulated_state']['saldo_final'],
                    'mejora': scenario['comparison']['mejora_liquidez'],
                    'recomendacion': scenario['comparison']['recomendacion']
                })
        
        # Ordenar por mejor resultado
        scenarios.sort(key=lambda x: x['flujo_neto_total'], reverse=True)
        
        return {
            'status': 'success',
            'scenarios_compared': len(scenarios),
            'best_scenario': scenarios[0] if scenarios else None,
            'all_scenarios': scenarios
        }
