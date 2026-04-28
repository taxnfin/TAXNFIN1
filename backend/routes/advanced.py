"""Advanced features: AI predictive, auto-reconciliation, alerts, bank API routes"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging

from core.database import db
from core.auth import get_current_user
from services.audit import audit_log
from models.enums import UserRole

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/ai/predictive-analysis")
async def get_predictive_analysis(current_user: Dict = Depends(get_current_user)):
    """An\u00e1lisis predictivo de cashflow con ML + LLM"""
    
    service = PredictiveAnalysisService(db)
    
    # An\u00e1lisis cuantitativo (ML)
    analysis = await service.analyze_cashflow_trends(
        company_id=current_user['company_id'],
        weeks_history=13
    )
    
    if analysis['status'] == 'insufficient_data':
        return analysis
    
    # Insights cualitativos (LLM)
    ai_insights = await service.generate_ai_insights(
        company_id=current_user['company_id'],
        analysis_data=analysis
    )
    
    return {
        'status': 'success',
        'company_id': current_user['company_id'],
        'analisis_cuantitativo': analysis['analisis'],
        'predicciones_8_semanas': analysis['predictions'],
        'insights_ia': ai_insights
    }

# ===== CONCILIACI\u00d3N AUTOM\u00c1TICA INTELIGENTE =====

@router.get("/reconciliation/auto-match/{bank_transaction_id}")
async def find_reconciliation_matches(
    bank_transaction_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Encuentra coincidencias autom\u00e1ticas para un movimiento bancario"""
    
    service = AutoReconciliationService(db)
    matches = await service.find_matches(bank_transaction_id, current_user['company_id'])
    
    return {
        'status': 'success',
        'bank_transaction_id': bank_transaction_id,
        'matches_found': len(matches),
        'matches': matches
    }

@router.post("/reconciliation/auto-reconcile-batch")
async def auto_reconcile_batch(
    min_score: float = Query(85, ge=60, le=100),
    current_user: Dict = Depends(get_current_user)
):
    """Concilia autom\u00e1ticamente movimientos con alta confianza"""
    
    service = AutoReconciliationService(db)
    result = await service.auto_reconcile_batch(
        company_id=current_user['company_id'],
        user_id=current_user['id'],
        min_score=min_score
    )
    
    return result

# ===== SISTEMA DE ALERTAS =====

@router.post("/alerts/check-and-send")
async def check_and_send_alerts(current_user: Dict = Depends(get_current_user)):
    """Verifica condiciones y env\u00eda alertas autom\u00e1ticas"""
    
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    service = AlertService(db)
    alerts = await service.check_and_send_alerts(current_user['company_id'])
    
    return {
        'status': 'success',
        'alerts_sent': len(alerts),
        'alerts': alerts
    }

# ===== SCRAPING SAT AUTOMATIZADO =====

@router.post("/sat/download-cfdis")
async def download_cfdis_from_sat(
    fecha_inicio: datetime,
    fecha_fin: datetime,
    tipo: str = Query("recibidos", regex="^(emitidos|recibidos)$"),
    current_user: Dict = Depends(get_current_user)
):
    """Descarga autom\u00e1tica de CFDIs desde portal SAT"""
    
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    service = SATScraperService(db)
    result = await service.download_cfdis_by_date_range(
        company_id=current_user['company_id'],
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        tipo=tipo
    )
    
    return result

@router.post("/sat/schedule-automatic")
async def schedule_sat_downloads(
    frequency: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    current_user: Dict = Depends(get_current_user)
):
    """Programa descargas autom\u00e1ticas de CFDIs"""
    
    if current_user['role'] != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    service = SATScraperService(db)
    result = await service.schedule_automatic_download(
        company_id=current_user['company_id'],
        frequency=frequency
    )
    
    return result

@router.post("/sat/credentials")
async def store_sat_credentials(
    rfc: str,
    certificado_file: UploadFile = File(...),
    llave_file: UploadFile = File(...),
    password: str = Query(...),
    current_user: Dict = Depends(get_current_user)
):
    """Almacena credenciales CSD/e.firma para el SAT"""
    
    if current_user['role'] != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    certificado_bytes = await certificado_file.read()
    llave_bytes = await llave_file.read()
    
    manager = SATCredentialManager(db)
    result = await manager.store_csd_credentials(
        company_id=current_user['company_id'],
        rfc=rfc,
        certificado_cer=certificado_bytes,
        llave_key=llave_bytes,
        password=password
    )
    
    return result

# ===== INTEGRACI\u00d3N APIS BANCARIAS =====

@router.get("/bank-api/available-banks")
async def get_available_banks():
    """Lista de bancos con APIs disponibles"""
    
    service = BankAPIService(db)
    banks = await service.get_available_banks()
    
    return {
        'status': 'success',
        'banks': banks
    }

# ===== AN\u00c1LISIS DE ESCENARIOS "QU\u00c9 PASAR\u00cdA SI" =====

from scenario_service import ScenarioAnalysisService

class BankAPIConnection(BaseModel):
    bank_account_id: str
    bank_name: str
    credentials: Dict[str, str]

@router.post("/bank-api/connect")
async def connect_bank_api(
    connection_data: BankAPIConnection,
    current_user: Dict = Depends(get_current_user)
):
    """Conecta cuenta bancaria con su API"""
    
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    service = BankAPIService(db)
    result = await service.connect_bank_account(
        company_id=current_user['company_id'],
        bank_account_id=connection_data.bank_account_id,
        bank_name=connection_data.bank_name,
        credentials=connection_data.credentials
    )
    
    return result

@router.post("/bank-api/sync/{bank_account_id}")
async def sync_bank_transactions(
    bank_account_id: str,
    days_back: int = Query(30, ge=1, le=90),
    current_user: Dict = Depends(get_current_user)
):
    """Sincroniza transacciones desde API del banco"""
    
    service = BankAPIService(db)
    result = await service.sync_transactions(
        bank_account_id=bank_account_id,
        days_back=days_back
    )
    
    return result

# ===== DRILL-DOWN ENDPOINT: Week Transactions Detail =====
