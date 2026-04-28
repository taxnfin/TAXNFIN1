"""Scenarios and genetic optimization routes"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from core.database import db
from core.auth import get_current_user
from services.audit import audit_log
from models.enums import UserRole
from scenario_service import ScenarioAnalysisService
from genetic_optimizer import GeneticOptimizer

router = APIRouter()

class ScenarioCreate(BaseModel):
    nombre: str
    descripcion: str
    modificaciones: List[Dict[str, Any]]

@router.post("/scenarios/create")
async def create_scenario(
    scenario_data: ScenarioCreate,
    current_user: Dict = Depends(get_current_user)
):
    """Crea un nuevo escenario de simulación 'qué pasaría si'"""
    
    service = ScenarioAnalysisService(db)
    result = await service.create_scenario(
        company_id=current_user['company_id'],
        nombre=scenario_data.nombre,
        descripcion=scenario_data.descripcion,
        modificaciones=scenario_data.modificaciones,
        user_id=current_user['id']
    )
    
    return result

@router.get("/scenarios")
async def list_scenarios(current_user: Dict = Depends(get_current_user)):
    """Lista todos los escenarios de la empresa"""
    
    service = ScenarioAnalysisService(db)
    scenarios = await service.list_scenarios(current_user['company_id'])
    
    return {
        'status': 'success',
        'scenarios': scenarios
    }

@router.get("/scenarios/{scenario_id}")
async def get_scenario_detail(
    scenario_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Obtiene detalle completo de un escenario"""
    
    service = ScenarioAnalysisService(db)
    scenario = await service.get_scenario_detail(scenario_id, current_user['company_id'])
    
    if not scenario:
        raise HTTPException(status_code=404, detail="Escenario no encontrado")
    
    return scenario

@router.post("/scenarios/compare")
async def compare_scenarios(
    scenario_ids: List[str],
    current_user: Dict = Depends(get_current_user)
):
    """Compara múltiples escenarios lado a lado"""
    
    service = ScenarioAnalysisService(db)
    comparison = await service.compare_multiple_scenarios(
        company_id=current_user['company_id'],
        scenario_ids=scenario_ids
    )
    
    return comparison

# ===== EXPORTACI\u00d3N CONTABLE =====

from export_service import AccountingExportService
from fastapi.responses import StreamingResponse

@router.get("/export/coi")
async def export_coi(
    fecha_inicio: datetime = Query(...),
    fecha_fin: datetime = Query(...),
    current_user: Dict = Depends(get_current_user)
):
    """Exporta a formato COI (Contabilidad)"""
    
    service = AccountingExportService(db)
    csv_data = await service.export_to_coi(
        company_id=current_user['company_id'],
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )
    
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=coi_export_{fecha_inicio.strftime('%Y%m%d')}.csv"}
    )

@router.get("/export/xml-fiscal")
async def export_xml_fiscal(
    fecha_inicio: datetime = Query(...),
    fecha_fin: datetime = Query(...),
    current_user: Dict = Depends(get_current_user)
):
    """Exporta a XML Fiscal (Balanza SAT)"""
    
    service = AccountingExportService(db)
    xml_data = await service.export_to_xml_fiscal(
        company_id=current_user['company_id'],
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )
    
    return StreamingResponse(
        iter([xml_data]),
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename=balanza_sat_{fecha_inicio.strftime('%Y%m%d')}.xml"}
    )

@router.get("/export/alegra")
async def export_alegra(
    fecha_inicio: datetime = Query(...),
    fecha_fin: datetime = Query(...),
    current_user: Dict = Depends(get_current_user)
):
    """Exporta a formato Alegra (JSON)"""
    
    service = AccountingExportService(db)
    json_data = await service.export_to_alegra(
        company_id=current_user['company_id'],
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )
    
    return StreamingResponse(
        iter([json_data]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=alegra_export_{fecha_inicio.strftime('%Y%m%d')}.json"}
    )

@router.get("/export/cashflow")
async def export_cashflow_report(
    formato: str = Query("excel", regex="^(excel|json)$"),
    current_user: Dict = Depends(get_current_user)
):
    """Exporta reporte de cashflow 13 semanas"""
    
    service = AccountingExportService(db)
    data = await service.export_cashflow_report(
        company_id=current_user['company_id'],
        formato=formato
    )
    
    if formato == 'excel':
        return StreamingResponse(
            iter([data]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=cashflow_report_{datetime.now().strftime('%Y%m%d')}.csv"}
        )
    else:
        return StreamingResponse(
            iter([data]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=cashflow_report_{datetime.now().strftime('%Y%m%d')}.json"}
        )



# ===== OPTIMIZACI\u00d3N GEN\u00c9TICA =====

from genetic_optimizer import GeneticOptimizer

class OptimizationConfig(BaseModel):
    objetivos: Dict[str, Any] = {
        "maximizar_liquidez": True,
        "minimizar_costos": True,
        "evitar_crisis": True
    }
    restricciones: Dict[str, Any] = {
        "max_retraso_dias": 30,
        "max_adelanto_dias": 15,
        "min_saldo": 50000
    }
    parametros: Optional[Dict[str, Any]] = {
        "generaciones": 50,
        "poblacion": 100,
        "prob_mutacion": 0.2
    }

@router.post("/optimize/genetic")
async def run_genetic_optimization(
    config: OptimizationConfig,
    current_user: Dict = Depends(get_current_user)
):
    """
    Ejecuta optimización genética del cashflow
    Encuentra automáticamente la mejor combinación de modificaciones
    """
    
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    optimizer = GeneticOptimizer(db)
    
    result = await optimizer.optimize_cashflow(
        company_id=current_user['company_id'],
        objetivos=config.objetivos,
        restricciones=config.restricciones,
        parametros=config.parametros
    )
    
    return result

@router.get("/optimize/history")
async def get_optimization_history(current_user: Dict = Depends(get_current_user)):
    """Obtiene histórico de optimizaciones genéticas"""
    
    optimizer = GeneticOptimizer(db)
    history = await optimizer.get_optimization_history(current_user['company_id'])
    
    return {
        'status': 'success',
        'optimizations': history
    }

@router.post("/optimize/apply/{optimization_id}")
async def apply_optimization(
    optimization_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Aplica la mejor solución de una optimización genética"""
    
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    # Obtener optimización
    optimization = await db.optimizations.find_one(
        {'id': optimization_id, 'company_id': current_user['company_id']},
        {'_id': 0}
    )
    
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimización no encontrada")
    
    # Obtener mejor solución
    mejor_solucion = optimization.get('mejor_solucion')
    if not mejor_solucion:
        raise HTTPException(status_code=400, detail="Esta optimización no tiene soluciones óptimas disponibles")
    
    modificaciones = mejor_solucion.get('modificaciones', [])
    if not modificaciones:
        return {
            'status': 'success',
            'optimization_id': optimization_id,
            'modificaciones_aplicadas': 0,
            'mejora_esperada': mejor_solucion.get('mejora_flujo_neto', 0),
            'message': 'No hay modificaciones para aplicar'
        }
    
    # Aplicar modificaciones a las transacciones reales
    aplicadas = 0
    for mod in modificaciones:
        txn_id = mod.get('transaction_id')
        if not txn_id:
            continue
        
        update_data = {}
        if 'nueva_fecha' in mod:
            update_data['fecha_transaccion'] = mod['nueva_fecha']
        if 'nuevo_monto' in mod:
            update_data['monto'] = mod['nuevo_monto']
        
        if update_data:
            result = await db.transactions.update_one(
                {'id': txn_id, 'company_id': current_user['company_id']},
                {'$set': update_data}
            )
            if result.modified_count > 0:
                aplicadas += 1
    
    # Registrar en auditor\u00eda
    await audit_log(
        current_user['company_id'],
        'Optimization',
        optimization_id,
        'APPLY',
        current_user['id'],
        datos_nuevos={'modificaciones_aplicadas': aplicadas}
    )
