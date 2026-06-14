"""SAT CIEC — Scraping del portal SAT con RFC + Contraseña"""
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from typing import Dict
from datetime import datetime, timezone
from core.database import db
from core.auth import get_current_user, get_active_company_id
from modules.cfdi_sat import SATCredentialManager, SATSyncService, SATPortalClient
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/sat/ciec/credentials")
async def save_ciec_credentials(
    request: Request,
    data: dict,
    current_user: Dict = Depends(get_current_user)
):
    """Guarda RFC + CIEC encriptado"""
    company_id = await get_active_company_id(request, current_user)
    rfc = data.get('rfc', '').strip().upper()
    ciec = data.get('ciec', '').strip()

    if not rfc or not ciec:
        return {'status': 'error', 'message': 'RFC y CIEC son requeridos'}

    manager = SATCredentialManager(db)
    result = await manager.save_credentials(company_id, rfc, ciec)
    return result


@router.get("/sat/ciec/status")
async def get_ciec_status(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Estado de la conexión CIEC"""
    company_id = await get_active_company_id(request, current_user)
    manager = SATCredentialManager(db)
    cred_status = await manager.get_credential_status(company_id)

    if not cred_status:
        return {'status': 'not_configured', 'message': 'CIEC no configurada'}

    return {
        'status': 'configured',
        'rfc': cred_status.get('rfc', ''),
        'last_sync': cred_status.get('last_sync'),
        'total_cfdis': cred_status.get('last_sync_result', {}).get('total_new', 0),
    }


@router.delete("/sat/ciec/credentials")
async def delete_ciec_credentials(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Elimina credenciales CIEC"""
    company_id = await get_active_company_id(request, current_user)
    manager = SATCredentialManager(db)
    await manager.delete_credentials(company_id)
    return {'status': 'success', 'message': 'Credenciales eliminadas'}


@router.post("/sat/ciec/test-connection")
async def test_ciec_connection(
    request: Request,
    data: dict,
    current_user: Dict = Depends(get_current_user)
):
    """Prueba login al portal SAT con RFC + CIEC sin guardar"""
    rfc = data.get('rfc', '').strip().upper()
    ciec = data.get('ciec', '').strip()

    if not rfc or not ciec:
        return {'status': 'error', 'message': 'RFC y CIEC requeridos'}

    service = SATSyncService(db)
    result = await service.validate_credentials(rfc, ciec)
    return result


@router.post("/sat/ciec/sync")
async def sync_ciec_cfdis(
    request: Request,
    background_tasks: BackgroundTasks,
    data: dict,
    current_user: Dict = Depends(get_current_user)
):
    """Descarga CFDIs del SAT via CIEC en background"""
    company_id = await get_active_company_id(request, current_user)
    fecha_inicio_str = data.get('fecha_inicio', '')
    fecha_fin_str = data.get('fecha_fin', '')
    tipo = data.get('tipo', 'ambos')  # 'emitidos' | 'recibidos' | 'ambos'

    manager = SATCredentialManager(db)
    creds = await manager.get_credentials(company_id)

    if not creds:
        return {'status': 'error', 'message': 'CIEC no configurada. Configura tus credenciales primero.'}

    # Defaults: últimos 90 días si no se especifica rango
    now = datetime.now(timezone.utc)
    try:
        fecha_inicio = datetime.fromisoformat(fecha_inicio_str) if fecha_inicio_str else datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    except ValueError:
        fecha_inicio = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    try:
        fecha_fin = datetime.fromisoformat(fecha_fin_str) if fecha_fin_str else now
    except ValueError:
        fecha_fin = now

    incluir_emitidos = tipo in ('emitidos', 'ambos')
    incluir_recibidos = tipo in ('recibidos', 'ambos')

    sync_service = SATSyncService(db)

    background_tasks.add_task(
        sync_service.sync_cfdis,
        company_id=company_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        incluir_emitidos=incluir_emitidos,
        incluir_recibidos=incluir_recibidos,
    )

    return {
        'status': 'started',
        'message': 'Descarga de CFDIs iniciada en background. Puede tomar 2-5 minutos.',
        'tipo': tipo,
        'fecha_inicio': fecha_inicio.isoformat(),
        'fecha_fin': fecha_fin.isoformat(),
    }


@router.get("/sat/ciec/sync-status")
async def get_sync_status(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Estado del último sync de CFDIs via CIEC"""
    company_id = await get_active_company_id(request, current_user)
    manager = SATCredentialManager(db)
    cred_status = await manager.get_credential_status(company_id)

    if not cred_status:
        return {'status': 'never_synced'}

    last_result = cred_status.get('last_sync_result', {})
    return {
        'status': 'synced' if cred_status.get('last_sync') else 'never_synced',
        'cfdis_descargados': last_result.get('total_new', 0),
        'last_sync': cred_status.get('last_sync'),
        'errors_count': last_result.get('errors_count', 0),
    }
