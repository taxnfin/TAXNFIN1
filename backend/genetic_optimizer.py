import random
import numpy as np
from deap import base, creator, tools, algorithms
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
import asyncio
import logging
import uuid
import copy

logger = logging.getLogger(__name__)

class GeneticOptimizer:
    """
    Optimizador de Cashflow con Algoritmos Genéticos
    Encuentra automáticamente la mejor combinación de modificaciones para maximizar liquidez
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._setup_genetic_algorithm()
    
    def _setup_genetic_algorithm(self):
        """Configura el framework DEAP para algoritmos genéticos"""
        
        # Limpiar configuración previa si existe
        if hasattr(creator, "FitnessMulti"):
            del creator.FitnessMulti
        if hasattr(creator, "Individual"):
            del creator.Individual
        
        # Definir función de fitness (multi-objetivo)
        # Objetivos: 1) Maximizar flujo neto, 2) Minimizar semanas críticas, 3) Minimizar costos
        creator.create("FitnessMulti", base.Fitness, weights=(1.0, 1.0, 1.0))
        creator.create("Individual", list, fitness=creator.FitnessMulti)
        
        self.toolbox = base.Toolbox()
    
    async def optimize_cashflow(
        self,
        company_id: str,
        objetivos: Dict[str, Any],
        restricciones: Dict[str, Any],
        parametros: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta optimización genética del cashflow
        
        Args:
            company_id: ID de la empresa
            objetivos: {"maximizar_liquidez": True, "minimizar_costos": True, "evitar_crisis": True}
            restricciones: {"max_retraso_dias": 30, "max_adelanto_dias": 15, "min_saldo": 50000}
            parametros: {"generaciones": 50, "poblacion": 100, "prob_mutacion": 0.2}
        
        Returns:
            Dict con mejores soluciones encontradas
        """
        
        # Parámetros por defecto
        if parametros is None:
            parametros = {}
        
        generaciones = parametros.get('generaciones', 50)
        poblacion_size = parametros.get('poblacion', 100)
        prob_crossover = parametros.get('prob_crossover', 0.7)
        prob_mutacion = parametros.get('prob_mutacion', 0.2)
        
        # Obtener datos de la empresa
        transactions = await self.db.transactions.find(
            {'company_id': company_id, 'es_proyeccion': True}
        ).to_list(1000)
        
        if len(transactions) < 5:
            return {
                'status': 'insufficient_data',
                'message': 'Se necesitan al menos 5 transacciones proyectadas para optimizar'
            }
        
        # Obtener baseline actual
        baseline = await self._calculate_baseline(company_id)
        
        # Configurar operadores genéticos
        self._configure_genetic_operators(
            transactions,
            restricciones,
            company_id,
            baseline
        )
        
        # Crear población inicial
        poblacion = self.toolbox.population(n=poblacion_size)
        
        # Evaluar población inicial
        fitnesses = await self._evaluate_population(poblacion, company_id, baseline, objetivos)
        for ind, fit in zip(poblacion, fitnesses):
            ind.fitness.values = fit
        
        # Estadísticas
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", np.mean, axis=0)
        stats.register("std", np.std, axis=0)
        stats.register("min", np.min, axis=0)
        stats.register("max", np.max, axis=0)
        
        # Hall of fame (mejores individuos)
        hof = tools.HallOfFame(10)
        
        # Log de evolución
        logbook = tools.Logbook()
        logbook.header = ['gen', 'nevals'] + stats.fields
        
        # Evolucionar
        for gen in range(generaciones):
            # Seleccionar próxima generación
            offspring = self.toolbox.select(poblacion, len(poblacion))
            offspring = list(map(self.toolbox.clone, offspring))
            
            # Aplicar crossover
            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < prob_crossover:
                    self.toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values
            
            # Aplicar mutación
            for mutant in offspring:
                if random.random() < prob_mutacion:
                    self.toolbox.mutate(mutant)
                    del mutant.fitness.values
            
            # Evaluar individuos con fitness inválido
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = await self._evaluate_population(invalid_ind, company_id, baseline, objetivos)
            for ind, fit in zip(invalid_ind, fitnesses):
                ind.fitness.values = fit
            
            # Reemplazar población
            poblacion[:] = offspring
            
            # Actualizar hall of fame
            hof.update(poblacion)
            
            # Registrar estadísticas
            record = stats.compile(poblacion)
            logbook.record(gen=gen, nevals=len(invalid_ind), **record)
            
            # Log progreso cada 10 generaciones
            if gen % 10 == 0:
                logger.info(f"Generación {gen}: Mejor fitness = {hof[0].fitness.values}")
        
        # Decodificar mejores soluciones
        best_solutions = []
        for idx, individual in enumerate(hof[:5]):
            decoded = self._decode_individual(individual, transactions)
            result = await self._evaluate_scenario(decoded, company_id, baseline)
            
            # Convert numpy arrays to Python lists
            fitness_values = tuple(float(x) for x in individual.fitness.values)
            
            best_solutions.append({
                'rank': idx + 1,
                'fitness': fitness_values,
                'modificaciones': decoded,
                'resultado': result,
                'mejora_flujo_neto': result['flujo_neto_total'] - baseline['flujo_neto_total'],
                'semanas_criticas_resueltas': len([w for w in baseline['weekly_flow'] if w['saldo_acumulado'] < 0]) - len([w for w in result['weekly_flow'] if w['saldo_acumulado'] < 0])
            })
        
        # Guardar optimización en base de datos
        # Convert numpy types to Python types for MongoDB
        def convert_numpy_types(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
                return int(obj)
            elif isinstance(obj, (np.float64, np.float32, np.float16)):
                return float(obj)
            elif isinstance(obj, dict):
                return {k: convert_numpy_types(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_numpy_types(x) for x in obj]
            return obj
        
        stats_evolution = convert_numpy_types(dict(logbook[-1]))
        
        optimization = {
            'id': str(uuid.uuid4()),
            'company_id': company_id,
            'tipo': 'genetic_algorithm',
            'parametros': parametros,
            'objetivos': objetivos,
            'restricciones': restricciones,
            'generaciones_ejecutadas': generaciones,
            'mejor_solucion': convert_numpy_types(best_solutions[0]),
            'top_5_soluciones': convert_numpy_types(best_solutions),
            'estadisticas_evolucion': stats_evolution,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'estado': 'completado'
        }
        
        await self.db.optimizations.insert_one(optimization)
        
        return {
            'status': 'success',
            'optimization_id': optimization['id'],
            'generaciones': generaciones,
            'mejor_solucion': convert_numpy_types(best_solutions[0]),
            'top_5_soluciones': convert_numpy_types(best_solutions),
            'mejora_vs_baseline': {
                'flujo_neto': float(best_solutions[0]['mejora_flujo_neto']),
                'semanas_criticas_resueltas': int(best_solutions[0]['semanas_criticas_resueltas'])
            }
        }
    
    def _configure_genetic_operators(
        self,
        transactions: List[Dict],
        restricciones: Dict[str, Any],
        company_id: str,
        baseline: Dict[str, Any]
    ):
        """Configura operadores genéticos: cruce, mutación, selección"""
        
        # Genes: cada transacción puede ser modificada
        # Gen format: [transaction_idx, accion, valor]
        # Acciones: 0=no_cambio, 1=adelantar, 2=retrasar, 3=ajustar_monto
        
        num_transactions = len(transactions)
        max_modifications = min(10, num_transactions)  # Máximo 10 modificaciones
        
        def create_individual():
            """Crea un individuo aleatorio"""
            num_mods = random.randint(1, max_modifications)
            individual = []
            
            selected_indices = random.sample(range(num_transactions), num_mods)
            for idx in selected_indices:
                accion = random.randint(1, 3)  # 1=adelantar, 2=retrasar, 3=ajustar
                
                if accion == 1:  # Adelantar
                    dias = random.randint(1, restricciones.get('max_adelanto_dias', 15))
                    individual.append([idx, accion, -dias])
                elif accion == 2:  # Retrasar
                    dias = random.randint(1, restricciones.get('max_retraso_dias', 30))
                    individual.append([idx, accion, dias])
                else:  # Ajustar monto
                    factor = random.uniform(0.7, 1.3)  # -30% a +30%
                    individual.append([idx, accion, factor])
            
            return creator.Individual(individual)
        
        def mutate(individual):
            """Mutación: cambia aleatoriamente un gen"""
            if len(individual) == 0:
                return individual,
            
            # Mutar un gen aleatorio
            idx = random.randint(0, len(individual) - 1)
            gene = individual[idx]
            
            # Cambiar acción o valor
            if random.random() < 0.5:
                # Cambiar acción
                gene[1] = random.randint(1, 3)
            
            # Cambiar valor según acción
            if gene[1] == 1:  # Adelantar
                gene[2] = -random.randint(1, restricciones.get('max_adelanto_dias', 15))
            elif gene[1] == 2:  # Retrasar
                gene[2] = random.randint(1, restricciones.get('max_retraso_dias', 30))
            else:  # Ajustar monto
                gene[2] = random.uniform(0.7, 1.3)
            
            return individual,
        
        def crossover(ind1, ind2):
            """Cruce: intercambia genes entre dos individuos"""
            if len(ind1) == 0 or len(ind2) == 0:
                return ind1, ind2
            
            # Punto de cruce
            point1 = random.randint(1, len(ind1))
            point2 = random.randint(1, len(ind2))
            
            # Intercambiar
            ind1[point1:], ind2[point2:] = ind2[point2:], ind1[point1:]
            
            return ind1, ind2
        
        # Registrar operadores
        self.toolbox.register("individual", create_individual)
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)
        self.toolbox.register("mate", crossover)
        self.toolbox.register("mutate", mutate)
        self.toolbox.register("select", tools.selNSGA2)  # Selección multi-objetivo
    
    async def _evaluate_population(
        self,
        population: List,
        company_id: str,
        baseline: Dict[str, Any],
        objetivos: Dict[str, Any]
    ) -> List[Tuple[float, float, float]]:
        """Evalúa fitness de toda la población"""
        
        transactions = await self.db.transactions.find(
            {'company_id': company_id, 'es_proyeccion': True}
        ).to_list(1000)
        
        fitnesses = []
        for individual in population:
            fitness = await self._evaluate_individual(
                individual,
                transactions,
                company_id,
                baseline,
                objetivos
            )
            fitnesses.append(fitness)
        
        return fitnesses
    
    async def _evaluate_individual(
        self,
        individual: List,
        transactions: List[Dict],
        company_id: str,
        baseline: Dict[str, Any],
        objetivos: Dict[str, Any]
    ) -> Tuple[float, float, float]:
        """Evalúa un individuo (escenario) y retorna fitness multi-objetivo"""
        
        # Decodificar individuo a modificaciones
        modificaciones = self._decode_individual(individual, transactions)
        
        # Calcular resultado
        result = await self._evaluate_scenario(modificaciones, company_id, baseline)
        
        # Calcular fitness según objetivos
        fitness1 = result['flujo_neto_total']  # Maximizar flujo neto
        
        # Penalizar semanas críticas
        semanas_criticas = len([w for w in result['weekly_flow'] if w['saldo_acumulado'] < 0])
        fitness2 = -semanas_criticas * 10000  # Penalización fuerte
        
        # Minimizar "costo" de modificaciones
        costo_modificaciones = self._calculate_modification_cost(modificaciones)
        fitness3 = -costo_modificaciones
        
        return (fitness1, fitness2, fitness3)
    
    def _decode_individual(self, individual: List, transactions: List[Dict]) -> List[Dict[str, Any]]:
        """Decodifica un individuo (genoma) a modificaciones legibles"""
        
        modificaciones = []
        for gene in individual:
            if len(gene) < 3:
                continue
            
            txn_idx, accion, valor = gene
            
            if txn_idx >= len(transactions):
                continue
            
            txn = transactions[txn_idx]
            
            if accion == 1:  # Adelantar
                fecha_actual = datetime.fromisoformat(txn['fecha_transaccion']) if isinstance(txn['fecha_transaccion'], str) else txn['fecha_transaccion']
                nueva_fecha = fecha_actual + timedelta(days=valor)  # valor es negativo
                modificaciones.append({
                    'tipo': 'adelantar_pago' if txn['tipo_transaccion'] == 'egreso' else 'adelantar_cobro',
                    'transaction_id': txn['id'],
                    'nueva_fecha': nueva_fecha.isoformat(),
                    'razon': f'Optimización genética: adelantar {abs(valor)} días'
                })
            elif accion == 2:  # Retrasar
                fecha_actual = datetime.fromisoformat(txn['fecha_transaccion']) if isinstance(txn['fecha_transaccion'], str) else txn['fecha_transaccion']
                nueva_fecha = fecha_actual + timedelta(days=valor)
                modificaciones.append({
                    'tipo': 'retrasar_pago' if txn['tipo_transaccion'] == 'egreso' else 'retrasar_cobro',
                    'transaction_id': txn['id'],
                    'nueva_fecha': nueva_fecha.isoformat(),
                    'razon': f'Optimización genética: retrasar {valor} días'
                })
            elif accion == 3:  # Ajustar monto
                nuevo_monto = txn['monto'] * valor
                modificaciones.append({
                    'tipo': 'ajustar_monto',
                    'transaction_id': txn['id'],
                    'nuevo_monto': nuevo_monto,
                    'razon': f'Optimización genética: ajustar a {valor:.2%} del original'
                })
        
        return modificaciones
    
    async def _evaluate_scenario(
        self,
        modificaciones: List[Dict[str, Any]],
        company_id: str,
        baseline: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evalúa un escenario aplicando modificaciones"""
        
        # Obtener todas las transacciones
        transactions = await self.db.transactions.find(
            {'company_id': company_id}
        ).to_list(1000)
        
        # Clonar y aplicar modificaciones
        simulated_txns = copy.deepcopy(transactions)
        
        for mod in modificaciones:
            for txn in simulated_txns:
                if txn['id'] == mod.get('transaction_id'):
                    if 'nueva_fecha' in mod:
                        txn['fecha_transaccion'] = mod['nueva_fecha']
                    if 'nuevo_monto' in mod:
                        txn['monto'] = mod['nuevo_monto']
                    break
        
        # Recalcular flujo
        weeks = await self.db.cashflow_weeks.find(
            {'company_id': company_id}
        ).sort('fecha_inicio', 1).to_list(13)
        
        weekly_flow = []
        for week in weeks:
            fecha_inicio = datetime.fromisoformat(week['fecha_inicio']) if isinstance(week['fecha_inicio'], str) else week['fecha_inicio']
            fecha_fin = datetime.fromisoformat(week['fecha_fin']) if isinstance(week['fecha_fin'], str) else week['fecha_fin']
            
            # Normalize to UTC-aware
            if fecha_inicio.tzinfo is None:
                fecha_inicio = fecha_inicio.replace(tzinfo=timezone.utc)
            if fecha_fin.tzinfo is None:
                fecha_fin = fecha_fin.replace(tzinfo=timezone.utc)
            
            week_txns = []
            for t in simulated_txns:
                fecha_txn = datetime.fromisoformat(t['fecha_transaccion']) if isinstance(t['fecha_transaccion'], str) else t['fecha_transaccion']
                if fecha_txn.tzinfo is None:
                    fecha_txn = fecha_txn.replace(tzinfo=timezone.utc)
                if fecha_inicio <= fecha_txn <= fecha_fin:
                    week_txns.append(t)
            
            ingresos = sum(t['monto'] for t in week_txns if t['tipo_transaccion'] == 'ingreso')
            egresos = sum(t['monto'] for t in week_txns if t['tipo_transaccion'] == 'egreso')
            flujo_neto = ingresos - egresos
            
            weekly_flow.append({
                'semana': week['numero_semana'],
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
            'flujo_neto_total': sum(w['flujo_neto'] for w in weekly_flow)
        }
    
    def _calculate_modification_cost(self, modificaciones: List[Dict[str, Any]]) -> float:
        """Calcula el 'costo' de las modificaciones (complejidad operativa)"""
        
        costo = 0
        for mod in modificaciones:
            if 'nueva_fecha' in mod:
                # Costo de cambiar fechas (negociación)
                costo += 100
            if 'nuevo_monto' in mod:
                # Costo de ajustar montos (descuentos/penalizaciones)
                costo += 200
        
        return costo
    
    async def _calculate_baseline(self, company_id: str) -> Dict[str, Any]:
        """Calcula el estado actual del cashflow como baseline"""
        
        weeks = await self.db.cashflow_weeks.find(
            {'company_id': company_id}
        ).sort('fecha_inicio', 1).to_list(13)
        
        transactions = await self.db.transactions.find(
            {'company_id': company_id}
        ).to_list(1000)
        
        weekly_flow = []
        for week in weeks:
            week_txns = [t for t in transactions if t['cashflow_week_id'] == week['id']]
            
            ingresos = sum(t['monto'] for t in week_txns if t['tipo_transaccion'] == 'ingreso')
            egresos = sum(t['monto'] for t in week_txns if t['tipo_transaccion'] == 'egreso')
            flujo_neto = ingresos - egresos
            
            weekly_flow.append({
                'semana': week['numero_semana'],
                'ingresos': ingresos,
                'egresos': egresos,
                'flujo_neto': flujo_neto
            })
        
        saldo_acumulado = 0
        for week_data in weekly_flow:
            saldo_acumulado += week_data['flujo_neto']
            week_data['saldo_acumulado'] = saldo_acumulado
        
        return {
            'weekly_flow': weekly_flow,
            'flujo_neto_total': sum(w['flujo_neto'] for w in weekly_flow)
        }
    
    async def get_optimization_history(self, company_id: str) -> List[Dict[str, Any]]:
        """Obtiene histórico de optimizaciones"""
        
        optimizations = await self.db.optimizations.find(
            {'company_id': company_id},
            {'_id': 0}
        ).sort('created_at', -1).limit(20).to_list(20)
        
        return optimizations
