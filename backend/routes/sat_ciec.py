"""SAT CIEC — Routes: RFC + Contraseña, descarga CFDIs, Opinión, Buzón"""
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from typing import Dict
from datetime import datetime, timezone
from core.database import db
from core.auth import get_current_user, get_active_company_id
from modules.cfdi_sat import SATCredentialManager, SATSyncService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Credenciales ──────────────────────────────────────────────────────────────

@router.post("/sat/ciec/credentials")
async def save_ciec_credentials(request: Request, data: dict,
                                current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    rfc  = data.get('rfc', '').strip().upper()
    ciec = data.get('ciec', '').strip()
    if not rfc or not ciec:
        return {'status': 'error', 'message': 'RFC y CIEC son requeridos'}
    return await SATCredentialManager(db).save_credentials(company_id, rfc, ciec)


@router.get("/sat/ciec/status")
async def get_ciec_status(request: Request,
                          current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    cred = await SATCredentialManager(db).get_credential_status(company_id)
    if not cred:
        return {'status': 'not_configured', 'message': 'CIEC no configurada'}
    lr = cred.get('last_sync_result', {})
    return {
        'status': 'configured',
        'rfc': cred.get('rfc', ''),
        'last_sync': cred.get('last_sync'),
        'total_cfdis': lr.get('total_new', 0),
        'errors_count': lr.get('errors_count', 0),
    }


@router.delete("/sat/ciec/credentials")
async def delete_ciec_credentials(request: Request,
                                  current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    await SATCredentialManager(db).delete_credentials(company_id)
    return {'status': 'success', 'message': 'Credenciales eliminadas'}


# ── Test de conexión ──────────────────────────────────────────────────────────

@router.post("/sat/ciec/test-connection")
async def test_ciec_connection(request: Request, data: dict,
                               current_user: Dict = Depends(get_current_user)):
    """Prueba login al portal SAT SIN guardar las credenciales."""
    rfc  = data.get('rfc', '').strip().upper()
    ciec = data.get('ciec', '').strip()
    if not rfc or not ciec:
        return {'status': 'error', 'message': 'RFC y CIEC requeridos'}
    result = await SATSyncService(db).validate_credentials(rfc, ciec)
    return result


# ── Sync CFDIs ────────────────────────────────────────────────────────────────

@router.post("/sat/ciec/sync")
async def sync_ciec_cfdis(request: Request, data: dict,
                           background_tasks: BackgroundTasks,
                           current_user: Dict = Depends(get_current_user)):
    """
    Descarga CFDIs del portal SAT en background.
    Body: { fecha_inicio, fecha_fin, tipo, tipo_comprobante }
    tipo: 'emitidos' | 'recibidos' | 'ambos'
    tipo_comprobante: 'I' | 'E' | 'P' | 'N' | '' (todos)
    """
    company_id = await get_active_company_id(request, current_user)
    creds = await SATCredentialManager(db).get_credentials(company_id)
    if not creds:
        return {'status': 'error', 'message': 'CIEC no configurada'}

    now = datetime.now(timezone.utc)
    tipo = data.get('tipo', 'ambos')

    try:
        fecha_inicio = datetime.fromisoformat(data['fecha_inicio']) if data.get('fecha_inicio') \
            else datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    except Exception:
        fecha_inicio = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    try:
        fecha_fin = datetime.fromisoformat(data['fecha_fin']) if data.get('fecha_fin') else now
    except Exception:
        fecha_fin = now

    tipo_comprobante = data.get('tipo_comprobante', '')  # '' = todos

    background_tasks.add_task(
        SATSyncService(db).sync_cfdis,
        company_id=company_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        incluir_emitidos=(tipo in ('emitidos', 'ambos')),
        incluir_recibidos=(tipo in ('recibidos', 'ambos')),
        tipo_comprobante=tipo_comprobante,
    )

    return {
        'status': 'started',
        'message': 'Descarga de CFDIs iniciada. Puede tomar 2-5 minutos.',
        'tipo': tipo,
        'tipo_comprobante': tipo_comprobante or 'todos',
        'fecha_inicio': fecha_inicio.isoformat(),
        'fecha_fin': fecha_fin.isoformat(),
    }


@router.get("/sat/ciec/sync-status")
async def get_sync_status(request: Request,
                          current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    cred = await SATCredentialManager(db).get_credential_status(company_id)
    if not cred:
        return {'status': 'never_synced'}
    lr = cred.get('last_sync_result', {})
    return {
        'status': 'synced' if cred.get('last_sync') else 'never_synced',
        'last_sync': cred.get('last_sync'),
        'cfdis_nuevos': lr.get('total_new', 0),
        'cfdis_actualizados': lr.get('total_updated', 0),
        'errors_count': lr.get('errors_count', 0),
        'rfc': cred.get('rfc', ''),
    }


# ── Extras: Opinión, Buzón ────────────────────────────────────────────────────

@router.post("/sat/ciec/sync-extras")
async def sync_extras(request: Request, background_tasks: BackgroundTasks,
                      current_user: Dict = Depends(get_current_user)):
    """
    Consulta Opinión de Cumplimiento (32-D) y Buzón Tributario en background.
    """
    company_id = await get_active_company_id(request, current_user)
    creds = await SATCredentialManager(db).get_credentials(company_id)
    if not creds:
        return {'status': 'error', 'message': 'CIEC no configurada'}

    background_tasks.add_task(SATSyncService(db).sync_extras, company_id=company_id)
    return {'status': 'started', 'message': 'Consultando Opinión de Cumplimiento y Buzón Tributario...'}


@router.get("/sat/ciec/extras")
async def get_extras(request: Request, current_user: Dict = Depends(get_current_user)):
    """Devuelve los extras guardados (Opinión, Buzón, Declaraciones)."""
    company_id = await get_active_company_id(request, current_user)
    doc = await db.sat_extras.find_one({'company_id': company_id}, {'_id': 0})
    if not doc:
        return {'status': 'no_data', 'message': 'Sin datos. Ejecuta sync-extras primero.'}
    return doc
