"""SAT CIEC — Routes: RFC + Contraseña, descarga CFDIs, Opinión, Buzón"""
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from typing import Dict
from datetime import datetime, timezone
import uuid
from core.database import db
from core.auth import get_current_user, get_active_company_id
from modules.cfdi_sat import SATCredentialManager, SATSyncService
from modules.syntage_client import SyntageClient
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

async def _run_test_connection(test_id: str, rfc: str, ciec: str):
    await db.sat_ciec_test.update_one(
        {'test_id': test_id},
        {'$set': {'status': 'running', 'updated_at': datetime.now(timezone.utc)}},
        upsert=True,
    )
    try:
        result = await SATSyncService(db).validate_credentials(rfc, ciec)
        await db.sat_ciec_test.update_one(
            {'test_id': test_id},
            {'$set': {'status': 'done', 'result': result, 'updated_at': datetime.now(timezone.utc)}},
        )
    except Exception as e:
        await db.sat_ciec_test.update_one(
            {'test_id': test_id},
            {'$set': {'status': 'error',
                      'result': {'success': False, 'error': str(e)},
                      'updated_at': datetime.now(timezone.utc)}},
        )


@router.post("/sat/ciec/test-connection")
async def test_ciec_connection(request: Request, data: dict,
                               background_tasks: BackgroundTasks,
                               current_user: Dict = Depends(get_current_user)):
    """Prueba login al portal SAT SIN guardar las credenciales (background)."""
    rfc  = data.get('rfc', '').strip().upper()
    ciec = data.get('ciec', '').strip()
    if not rfc or not ciec:
        return {'status': 'error', 'message': 'RFC y CIEC requeridos'}
    test_id = str(uuid.uuid4())
    background_tasks.add_task(_run_test_connection, test_id, rfc, ciec)
    return {'status': 'started', 'test_id': test_id}


@router.get("/sat/ciec/test-status/{test_id}")
async def get_test_connection_status(test_id: str, request: Request,
                                     current_user: Dict = Depends(get_current_user)):
    """Polling del resultado de test-connection."""
    record = await db.sat_ciec_test.find_one({'test_id': test_id}, {'_id': 0})
    if not record:
        return {'status': 'not_found'}
    return {'status': record.get('status'), 'result': record.get('result')}


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

async def _run_sync_extras(sync_id: str, company_id: str):
    await db.sat_extras_sync.update_one(
        {'sync_id': sync_id},
        {'$set': {'status': 'running', 'updated_at': datetime.now(timezone.utc)}},
        upsert=True,
    )
    try:
        result = await SATSyncService(db).sync_extras(company_id=company_id)
        await db.sat_extras_sync.update_one(
            {'sync_id': sync_id},
            {'$set': {'status': 'done', 'result': result, 'updated_at': datetime.now(timezone.utc)}},
        )
    except Exception as e:
        await db.sat_extras_sync.update_one(
            {'sync_id': sync_id},
            {'$set': {'status': 'error',
                      'result': {'success': False, 'error': str(e)},
                      'updated_at': datetime.now(timezone.utc)}},
        )


@router.post("/sat/ciec/sync-extras")
async def sync_extras(request: Request, background_tasks: BackgroundTasks,
                      current_user: Dict = Depends(get_current_user)):
    """Consulta Opinión de Cumplimiento (32-D) y Buzón Tributario en background."""
    company_id = await get_active_company_id(request, current_user)
    creds = await SATCredentialManager(db).get_credentials(company_id)
    if not creds:
        return {'status': 'error', 'message': 'CIEC no configurada'}

    sync_id = str(uuid.uuid4())
    background_tasks.add_task(_run_sync_extras, sync_id, company_id)
    return {'status': 'started', 'sync_id': sync_id}


@router.get("/sat/ciec/sync-extras-status/{sync_id}")
async def get_sync_extras_status(sync_id: str, request: Request,
                                 current_user: Dict = Depends(get_current_user)):
    """Polling del resultado de sync-extras."""
    record = await db.sat_extras_sync.find_one({'sync_id': sync_id}, {'_id': 0})
    if not record:
        return {'status': 'not_found'}
    return {'status': record.get('status'), 'result': record.get('result')}


@router.get("/sat/ciec/extras")
async def get_extras(request: Request, current_user: Dict = Depends(get_current_user)):
    """Devuelve los extras guardados (Opinión, Buzón, Declaraciones)."""
    company_id = await get_active_company_id(request, current_user)
    doc = await db.sat_extras.find_one({'company_id': company_id}, {'_id': 0})
    if not doc:
        return {'status': 'no_data', 'message': 'Sin datos. Ejecuta sync-extras primero.'}
    return doc


# ── Constancia de Situación Fiscal ───────────────────────────────────────────

async def _run_sync_constancia(sync_id: str, company_id: str):
    import traceback
    print(f"[CONSTANCIA] Iniciando sync_id={sync_id} company_id={company_id}", flush=True)
    await db.sat_constancia_sync.update_one(
        {'sync_id': sync_id},
        {'$set': {'status': 'running', 'updated_at': datetime.now(timezone.utc)}},
        upsert=True,
    )
    try:
        print(f"[CONSTANCIA] Llamando SATSyncService.sync_constancia...", flush=True)
        result = await SATSyncService(db).sync_constancia(company_id=company_id)
        print(f"[CONSTANCIA] Resultado: {result}", flush=True)
        await db.sat_constancia_sync.update_one(
            {'sync_id': sync_id},
            {'$set': {'status': 'done', 'result': result, 'updated_at': datetime.now(timezone.utc)}},
        )
    except Exception as e:
        print(f"[CONSTANCIA] ERROR: {e}", flush=True)
        print(traceback.format_exc(), flush=True)
        await db.sat_constancia_sync.update_one(
            {'sync_id': sync_id},
            {'$set': {'status': 'error',
                      'result': {'success': False, 'error': str(e)},
                      'updated_at': datetime.now(timezone.utc)}},
        )


@router.post("/sat/ciec/constancia")
async def sync_constancia(request: Request, background_tasks: BackgroundTasks,
                          current_user: Dict = Depends(get_current_user)):
    """Descarga la Constancia de Situación Fiscal en background."""
    company_id = await get_active_company_id(request, current_user)
    creds = await SATCredentialManager(db).get_credentials(company_id)
    if not creds:
        return {'status': 'error', 'message': 'CIEC no configurada'}
    sync_id = str(uuid.uuid4())
    background_tasks.add_task(_run_sync_constancia, sync_id, company_id)
    return {'status': 'started', 'sync_id': sync_id}


@router.get("/sat/ciec/constancia-status/{sync_id}")
async def get_constancia_status(sync_id: str, request: Request,
                                current_user: Dict = Depends(get_current_user)):
    """Polling del resultado de descarga de Constancia Fiscal."""
    record = await db.sat_constancia_sync.find_one({'sync_id': sync_id}, {'_id': 0})
    if not record:
        return {'status': 'not_found'}
    return {'status': record.get('status'), 'result': record.get('result')}


@router.get("/sat/ciec/constancia")
async def get_constancia(request: Request, current_user: Dict = Depends(get_current_user)):
    """Devuelve la Constancia de Situación Fiscal guardada."""
    company_id = await get_active_company_id(request, current_user)
    doc = await db.sat_constancia.find_one({'company_id': company_id}, {'_id': 0, 'pdf_base64': 0})
    if not doc:
        return {'status': 'no_data', 'message': 'Sin constancia. Ejecuta la descarga primero.'}
    return doc


# ── Syntage API: Constancia y Opinión de Cumplimiento ────────────────────────

@router.post("/sat/syntage/sync")
async def syntage_sync(request: Request, current_user: Dict = Depends(get_current_user)):
    """Registra credenciales en Syntage y obtiene Constancia + Opinión de Cumplimiento."""
    company_id = await get_active_company_id(request, current_user)
    creds = await SATCredentialManager(db).get_credentials(company_id)
    if not creds:
        return {"success": False, "error": "CIEC no configurada"}
    rfc = creds["rfc"]
    ciec = creds["ciec"]
    client = SyntageClient()
    try:
        cred_result = await client.create_credential(rfc, ciec)
        print(f"[SYNTAGE] create_credential result: {cred_result}", flush=True)

        entity = await client.get_entity_by_rfc(rfc)
        if not entity:
            return {"success": False, "error": "No se encontró entity en Syntage para este RFC"}
        entity_id = entity["id"]
        print(f"[SYNTAGE] entity_id: {entity_id}", flush=True)

        await db.sat_syntage_config.update_one(
            {"company_id": company_id},
            {"$set": {
                "company_id": company_id,
                "entity_id": entity_id,
                "rfc": rfc,
                "updated_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )

        tax_status = await client.get_tax_status(entity_id)
        tax_compliance = await client.get_tax_compliance(entity_id)
        print(f"[SYNTAGE] tax_status: {tax_status}", flush=True)
        print(f"[SYNTAGE] tax_compliance: {tax_compliance}", flush=True)

        await db.sat_syntage_data.update_one(
            {"company_id": company_id},
            {"$set": {
                "company_id": company_id,
                "entity_id": entity_id,
                "rfc": rfc,
                "tax_status": tax_status,
                "tax_compliance": tax_compliance,
                "updated_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
        return {
            "success": True,
            "entity_id": entity_id,
            "tax_status": tax_status,
            "tax_compliance": tax_compliance,
        }
    except Exception as e:
        print(f"[SYNTAGE] ERROR: {e}", flush=True)
        return {"success": False, "error": str(e)}


@router.get("/sat/syntage/status")
async def syntage_status(request: Request, current_user: Dict = Depends(get_current_user)):
    """Devuelve los datos de Syntage guardados (Constancia + Opinión)."""
    company_id = await get_active_company_id(request, current_user)
    data = await db.sat_syntage_data.find_one({"company_id": company_id}, {"_id": 0})
    if not data:
        return {"connected": False}
    return {"connected": True, **data}


@router.get("/sat/syntage/tax-status/pdf")
async def syntage_tax_status_pdf(request: Request, current_user: Dict = Depends(get_current_user)):
    """Descarga la Constancia de Situación Fiscal en PDF desde Syntage."""
    from fastapi.responses import Response
    company_id = await get_active_company_id(request, current_user)
    config = await db.sat_syntage_config.find_one({"company_id": company_id}, {"_id": 0})
    if not config:
        return {"error": "No hay entity_id configurado. Ejecuta sync primero."}
    entity_id = config["entity_id"]
    client = SyntageClient()
    try:
        pdf_bytes = await client.get_tax_status_pdf(entity_id)
        filename = f"Constancia_{config['rfc']}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        return {"error": str(e)}
