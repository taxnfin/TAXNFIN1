import asyncio
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import resend
import logging
from emergentintegrations.llm.chat import LlmChat, UserMessage
from motor.motor_asyncio import AsyncIOMotorDatabase
from twilio.rest import Client

logger = logging.getLogger(__name__)

class PredictiveAnalysisService:
    """Servicio de análisis predictivo de flujo de efectivo usando ML y LLM"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.llm_api_key = os.environ.get('EMERGENT_LLM_KEY', '')
        
    async def analyze_cashflow_trends(self, company_id: str, weeks_history: int = 13) -> Dict[str, Any]:
        """Analiza tendencias históricas de cashflow"""
        
        # Obtener transacciones históricas
        transactions = await self.db.transactions.find({
            'company_id': company_id,
            'es_real': True
        }).sort('fecha_transaccion', -1).to_list(1000)
        
        if len(transactions) < 10:
            return {
                'status': 'insufficient_data',
                'message': 'Se necesitan al menos 10 transacciones reales para análisis predictivo',
                'predictions': []
            }
        
        # Preparar datos para ML
        ingresos_semanales = []
        egresos_semanales = []
        
        # Agrupar por semana
        weeks_data = {}
        for txn in transactions:
            fecha = datetime.fromisoformat(txn['fecha_transaccion']) if isinstance(txn['fecha_transaccion'], str) else txn['fecha_transaccion']
            week_key = fecha.isocalendar()[1]
            year = fecha.year
            key = f"{year}-W{week_key}"
            
            if key not in weeks_data:
                weeks_data[key] = {'ingresos': 0, 'egresos': 0}
            
            if txn['tipo_transaccion'] == 'ingreso':
                weeks_data[key]['ingresos'] += txn['monto']
            else:
                weeks_data[key]['egresos'] += txn['monto']
        
        # Convertir a arrays
        for week_data in weeks_data.values():
            ingresos_semanales.append(week_data['ingresos'])
            egresos_semanales.append(week_data['egresos'])
        
        # Análisis estadístico básico
        ingresos_promedio = np.mean(ingresos_semanales) if ingresos_semanales else 0
        egresos_promedio = np.mean(egresos_semanales) if egresos_semanales else 0
        flujo_neto_promedio = ingresos_promedio - egresos_promedio
        
        volatilidad_ingresos = np.std(ingresos_semanales) if len(ingresos_semanales) > 1 else 0
        volatilidad_egresos = np.std(egresos_semanales) if len(egresos_semanales) > 1 else 0
        
        # Predicciones simples (regresión lineal)
        predictions = []
        if len(ingresos_semanales) >= 4:
            X = np.arange(len(ingresos_semanales)).reshape(-1, 1)
            
            # Predecir ingresos
            model_ingresos = LinearRegression()
            model_ingresos.fit(X, ingresos_semanales)
            
            # Predecir egresos
            model_egresos = LinearRegression()
            model_egresos.fit(X, egresos_semanales)
            
            # Proyectar 8 semanas adelante
            for i in range(1, 9):
                future_x = np.array([[len(ingresos_semanales) + i]])
                pred_ingreso = max(0, model_ingresos.predict(future_x)[0])
                pred_egreso = max(0, model_egresos.predict(future_x)[0])
                pred_flujo_neto = pred_ingreso - pred_egreso
                
                predictions.append({
                    'semana_futura': i,
                    'ingresos_predichos': round(pred_ingreso, 2),
                    'egresos_predichos': round(pred_egreso, 2),
                    'flujo_neto_predicho': round(pred_flujo_neto, 2),
                    'confianza': 'media' if i <= 4 else 'baja'
                })
        
        return {
            'status': 'success',
            'analisis': {
                'ingresos_promedio_semanal': round(ingresos_promedio, 2),
                'egresos_promedio_semanal': round(egresos_promedio, 2),
                'flujo_neto_promedio': round(flujo_neto_promedio, 2),
                'volatilidad_ingresos': round(volatilidad_ingresos, 2),
                'volatilidad_egresos': round(volatilidad_egresos, 2),
                'semanas_analizadas': len(weeks_data)
            },
            'predictions': predictions
        }
    
    async def generate_ai_insights(self, company_id: str, analysis_data: Dict[str, Any]) -> str:
        """Genera insights inteligentes usando LLM"""
        
        if not self.llm_api_key:
            return "Análisis de IA no disponible. Configure EMERGENT_LLM_KEY."
        
        try:
            # Obtener contexto adicional
            company = await self.db.companies.find_one({'id': company_id}, {'_id': 0})
            
            chat = LlmChat(
                api_key=self.llm_api_key,
                session_id=f"cashflow-analysis-{company_id}",
                system_message="Eres un analista financiero experto especializado en flujo de efectivo empresarial en México. Proporciona insights accionables y estratégicos."
            ).with_model("openai", "gpt-5.2")
            
            prompt = f"""
Analiza el siguiente flujo de efectivo y proporciona insights estratégicos:

Empresa: {company.get('nombre', 'N/A')}
Moneda: {company.get('moneda_base', 'MXN')}

Datos históricos:
- Ingreso promedio semanal: ${analysis_data['analisis']['ingresos_promedio_semanal']:,.2f}
- Egreso promedio semanal: ${analysis_data['analisis']['egresos_promedio_semanal']:,.2f}
- Flujo neto promedio: ${analysis_data['analisis']['flujo_neto_promedio']:,.2f}
- Volatilidad ingresos: ${analysis_data['analisis']['volatilidad_ingresos']:,.2f}
- Volatilidad egresos: ${analysis_data['analisis']['volatilidad_egresos']:,.2f}

Predicciones próximas 8 semanas:
{self._format_predictions(analysis_data['predictions'])}

Proporciona:
1. Análisis de riesgos de liquidez (identifica semanas críticas)
2. Recomendaciones accionables para mejorar el flujo
3. Oportunidades de optimización
4. Alertas tempranas (si las hay)

Respuesta en español, máximo 300 palabras, formato markdown.
"""
            
            user_message = UserMessage(text=prompt)
            response = await chat.send_message(user_message)
            
            return response
            
        except Exception as e:
            logger.error(f"Error generando insights IA: {str(e)}")
            return f"Error generando análisis IA: {str(e)}"
    
    def _format_predictions(self, predictions: List[Dict]) -> str:
        """Formatea predicciones para el prompt"""
        lines = []
        for pred in predictions:
            lines.append(
                f"Semana +{pred['semana_futura']}: Ingreso ${pred['ingresos_predichos']:,.2f}, "
                f"Egreso ${pred['egresos_predichos']:,.2f}, "
                f"Flujo Neto ${pred['flujo_neto_predicho']:,.2f} ({pred['confianza']})"
            )
        return "\n".join(lines)


class AutoReconciliationService:
    """Servicio de conciliación automática inteligente"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    async def find_matches(self, bank_transaction_id: str, company_id: str) -> List[Dict[str, Any]]:
        """Encuentra coincidencias automáticas para un movimiento bancario"""
        
        # Obtener movimiento bancario
        bank_txn = await self.db.bank_transactions.find_one(
            {'id': bank_transaction_id, 'company_id': company_id},
            {'_id': 0}
        )
        
        if not bank_txn:
            return []
        
        # Buscar transacciones candidatas (no reales, cercanas en fecha y monto)
        fecha_banco = datetime.fromisoformat(bank_txn['fecha_movimiento']) if isinstance(bank_txn['fecha_movimiento'], str) else bank_txn['fecha_movimiento']
        fecha_inicio = fecha_banco - timedelta(days=7)
        fecha_fin = fecha_banco + timedelta(days=7)
        
        # Determinar tipo
        tipo_buscar = 'ingreso' if bank_txn['tipo_movimiento'] == 'credito' else 'egreso'
        
        candidatos = await self.db.transactions.find({
            'company_id': company_id,
            'es_real': False,
            'tipo_transaccion': tipo_buscar,
            'bank_account_id': bank_txn['bank_account_id']
        }).to_list(100)
        
        matches = []
        for candidato in candidatos:
            score = self._calculate_match_score(
                bank_txn,
                candidato
            )
            
            if score >= 60:  # Umbral mínimo 60%
                matches.append({
                    'transaction_id': candidato['id'],
                    'concepto': candidato['concepto'],
                    'monto': candidato['monto'],
                    'fecha': candidato['fecha_transaccion'],
                    'score': score,
                    'recomendacion': 'alta' if score >= 85 else 'media' if score >= 70 else 'baja'
                })
        
        # Ordenar por score descendente
        matches.sort(key=lambda x: x['score'], reverse=True)
        
        return matches[:5]  # Top 5 matches
    
    def _calculate_match_score(self, bank_txn: Dict, cashflow_txn: Dict) -> float:
        """Calcula score de coincidencia (0-100)"""
        score = 0.0
        
        # 1. Coincidencia de monto (40 puntos máximo)
        monto_diff = abs(bank_txn['monto'] - cashflow_txn['monto'])
        monto_pct = (monto_diff / bank_txn['monto']) * 100 if bank_txn['monto'] > 0 else 100
        
        if monto_pct == 0:
            score += 40
        elif monto_pct <= 1:
            score += 35
        elif monto_pct <= 5:
            score += 25
        elif monto_pct <= 10:
            score += 15
        
        # 2. Proximidad de fecha (30 puntos máximo)
        fecha_banco = datetime.fromisoformat(bank_txn['fecha_movimiento']) if isinstance(bank_txn['fecha_movimiento'], str) else bank_txn['fecha_movimiento']
        fecha_cashflow = datetime.fromisoformat(cashflow_txn['fecha_transaccion']) if isinstance(cashflow_txn['fecha_transaccion'], str) else cashflow_txn['fecha_transaccion']
        
        dias_diff = abs((fecha_banco - fecha_cashflow).days)
        
        if dias_diff == 0:
            score += 30
        elif dias_diff == 1:
            score += 25
        elif dias_diff <= 3:
            score += 20
        elif dias_diff <= 7:
            score += 10
        
        # 3. Similitud de texto (30 puntos máximo)
        texto_banco = bank_txn.get('descripcion', '').lower()
        texto_cashflow = cashflow_txn.get('concepto', '').lower()
        
        # Similitud básica por palabras clave
        palabras_banco = set(texto_banco.split())
        palabras_cashflow = set(texto_cashflow.split())
        
        if palabras_banco and palabras_cashflow:
            interseccion = len(palabras_banco & palabras_cashflow)
            union = len(palabras_banco | palabras_cashflow)
            similitud = (interseccion / union) * 100 if union > 0 else 0
            score += (similitud / 100) * 30
        
        # 4. Referencia exacta (bonus 20 puntos)
        if bank_txn.get('referencia') and cashflow_txn.get('referencia'):
            if bank_txn['referencia'] == cashflow_txn['referencia']:
                score += 20
        
        return min(100, score)
    
    async def auto_reconcile_batch(self, company_id: str, user_id: str, min_score: float = 85) -> Dict[str, Any]:
        """Concilia automáticamente movimientos con alta confianza"""
        
        # Obtener movimientos bancarios sin conciliar
        bank_txns = await self.db.bank_transactions.find({
            'company_id': company_id,
            'conciliado': False
        }).to_list(100)
        
        reconciled_count = 0
        skipped_count = 0
        
        for bank_txn in bank_txns:
            matches = await self.find_matches(bank_txn['id'], company_id)
            
            # Auto-conciliar solo si hay un match con score >= min_score
            if matches and matches[0]['score'] >= min_score:
                best_match = matches[0]
                
                # Crear conciliación
                from pydantic import BaseModel
                from datetime import datetime, timezone
                import uuid
                
                recon_id = str(uuid.uuid4())
                reconciliation = {
                    'id': recon_id,
                    'company_id': company_id,
                    'bank_transaction_id': bank_txn['id'],
                    'transaction_id': best_match['transaction_id'],
                    'cfdi_id': None,
                    'metodo_conciliacion': 'automatica',
                    'porcentaje_match': best_match['score'],
                    'fecha_conciliacion': datetime.now(timezone.utc).isoformat(),
                    'user_id': user_id,
                    'notas': f"Conciliación automática (score: {best_match['score']:.1f}%)",
                    'created_at': datetime.now(timezone.utc).isoformat()
                }
                
                await self.db.reconciliations.insert_one(reconciliation)
                
                # Marcar como conciliado
                await self.db.bank_transactions.update_one(
                    {'id': bank_txn['id']},
                    {'$set': {'conciliado': True}}
                )
                
                # Marcar transacción como real
                await self.db.transactions.update_one(
                    {'id': best_match['transaction_id']},
                    {'$set': {'es_real': True, 'es_proyeccion': False}}
                )
                
                reconciled_count += 1
            else:
                skipped_count += 1
        
        return {
            'status': 'success',
            'reconciled': reconciled_count,
            'skipped': skipped_count,
            'total_processed': len(bank_txns)
        }


class AlertService:
    """Servicio de alertas por email y SMS"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.resend_api_key = os.environ.get('RESEND_API_KEY', '')
        self.twilio_account_sid = os.environ.get('TWILIO_ACCOUNT_SID', '')
        self.twilio_auth_token = os.environ.get('TWILIO_AUTH_TOKEN', '')
        self.twilio_phone = os.environ.get('TWILIO_PHONE_NUMBER', '')
        self.sender_email = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
        
        if self.resend_api_key:
            resend.api_key = self.resend_api_key
    
    async def check_and_send_alerts(self, company_id: str) -> List[Dict[str, Any]]:
        """Verifica condiciones y envía alertas si es necesario"""
        
        alerts_sent = []
        
        # 1. Alerta de liquidez baja
        low_liquidity = await self._check_low_liquidity(company_id)
        if low_liquidity:
            alerts_sent.append(await self._send_liquidity_alert(company_id, low_liquidity))
        
        # 2. Alerta de flujo negativo proyectado
        negative_flow = await self._check_negative_cashflow(company_id)
        if negative_flow:
            alerts_sent.append(await self._send_negative_flow_alert(company_id, negative_flow))
        
        # 3. Alerta de movimientos sin conciliar (más de 10)
        unreconciled = await self._check_unreconciled_transactions(company_id)
        if unreconciled:
            alerts_sent.append(await self._send_unreconciled_alert(company_id, unreconciled))
        
        return alerts_sent
    
    async def _check_low_liquidity(self, company_id: str) -> Optional[Dict]:
        """Verifica si hay riesgo de liquidez baja"""
        
        weeks = await self.db.cashflow_weeks.find(
            {'company_id': company_id}
        ).sort('fecha_inicio', 1).limit(4).to_list(4)
        
        for week in weeks:
            transactions = await self.db.transactions.find({
                'company_id': company_id,
                'cashflow_week_id': week['id']
            }).to_list(1000)
            
            ingresos = sum(t['monto'] for t in transactions if t['tipo_transaccion'] == 'ingreso')
            egresos = sum(t['monto'] for t in transactions if t['tipo_transaccion'] == 'egreso')
            flujo_neto = ingresos - egresos
            saldo_proyectado = week.get('saldo_inicial', 0) + flujo_neto
            
            # Alerta si saldo proyectado es negativo o muy bajo
            if saldo_proyectado < 0 or (saldo_proyectado < 50000 and flujo_neto < 0):
                return {
                    'semana': week['numero_semana'],
                    'saldo_proyectado': saldo_proyectado,
                    'flujo_neto': flujo_neto,
                    'fecha_inicio': week['fecha_inicio']
                }
        
        return None
    
    async def _check_negative_cashflow(self, company_id: str) -> Optional[Dict]:
        """Verifica flujo negativo prolongado"""
        
        weeks = await self.db.cashflow_weeks.find(
            {'company_id': company_id}
        ).sort('fecha_inicio', 1).limit(4).to_list(4)
        
        negative_weeks = 0
        for week in weeks:
            transactions = await self.db.transactions.find({
                'company_id': company_id,
                'cashflow_week_id': week['id']
            }).to_list(1000)
            
            ingresos = sum(t['monto'] for t in transactions if t['tipo_transaccion'] == 'ingreso')
            egresos = sum(t['monto'] for t in transactions if t['tipo_transaccion'] == 'egreso')
            
            if egresos > ingresos:
                negative_weeks += 1
        
        if negative_weeks >= 3:
            return {'semanas_negativas': negative_weeks}
        
        return None
    
    async def _check_unreconciled_transactions(self, company_id: str) -> Optional[Dict]:
        """Verifica transacciones sin conciliar"""
        
        count = await self.db.bank_transactions.count_documents({
            'company_id': company_id,
            'conciliado': False
        })
        
        if count >= 10:
            return {'count': count}
        
        return None
    
    async def _send_liquidity_alert(self, company_id: str, data: Dict) -> Dict:
        """Envía alerta de liquidez baja"""
        
        company = await self.db.companies.find_one({'id': company_id}, {'_id': 0})
        users = await self.db.users.find(
            {'company_id': company_id, 'role': {'$in': ['admin', 'cfo']}, 'activo': True},
            {'_id': 0}
        ).to_list(10)
        
        alert_type = 'CRÍTICO' if data['saldo_proyectado'] < 0 else 'ADVERTENCIA'
        
        for user in users:
            if self.resend_api_key and user.get('email'):
                try:
                    html_content = f"""
                    <h2 style="color: #EF4444;">⚠️ Alerta de Liquidez - {alert_type}</h2>
                    <p>Empresa: <strong>{company.get('nombre', 'N/A')}</strong></p>
                    <p>Se detectó riesgo de liquidez baja en la semana {data['semana']}:</p>
                    <ul>
                        <li>Saldo proyectado: <strong>${data['saldo_proyectado']:,.2f}</strong></li>
                        <li>Flujo neto: <strong>${data['flujo_neto']:,.2f}</strong></li>
                        <li>Fecha: {data['fecha_inicio']}</li>
                    </ul>
                    <p>Recomendamos revisar el flujo de efectivo y tomar medidas correctivas.</p>
                    """
                    
                    params = {
                        "from": self.sender_email,
                        "to": [user['email']],
                        "subject": f"🚨 {alert_type}: Riesgo de Liquidez - TaxnFin Cashflow",
                        "html": html_content
                    }
                    
                    await asyncio.to_thread(resend.Emails.send, params)
                    
                except Exception as e:
                    logger.error(f"Error enviando email: {str(e)}")
        
        return {
            'alert_type': 'liquidez_baja',
            'severity': alert_type,
            'recipients': len(users),
            'data': data
        }
    
    async def _send_negative_flow_alert(self, company_id: str, data: Dict) -> Dict:
        """Envía alerta de flujo negativo"""
        return {'alert_type': 'flujo_negativo', 'data': data}
    
    async def _send_unreconciled_alert(self, company_id: str, data: Dict) -> Dict:
        """Envía alerta de transacciones sin conciliar"""
        return {'alert_type': 'sin_conciliar', 'data': data}
