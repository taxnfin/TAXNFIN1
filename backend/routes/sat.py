"""
SAT Integration Routes - CFDI download from SAT portal
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, BackgroundTasks
from typing import Dict, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id
from services.audit import audit_log
from modules.cfdi_sat import SATCredentialManager, SATSyncService

router = APIRouter(prefix="/sat")
logger = logging.getLogger(__name__)


class SATCredentialsRequest(BaseModel):
    """Request model for SAT credentials"""
    rfc: str
    ciec: str


class SATSyncRequest(BaseModel):
    """Request model for SAT sync"""
    fecha_inicio: str  # ISO date string
    fecha_fin: str     # ISO date string
    tipo_comprobante: str = 'todos'  # todos, ingreso, egreso, pago, nomina
    incluir_emitidos: bool = True
    incluir_recibidos: bool = True


@router.get("/status")
async def get_sat_status(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get SAT integration status for the company
    Returns credential status and last sync info
    """
    company_id = await get_active_company_id(request, current_user)
    credential_manager = SATCredentialManager(db)
    
    cred_status = await credential_manager.get_credential_status(company_id)
    
    if not cred_status:
        return {
            'configured': False,
            'message': 'No hay credenciales SAT configuradas',
            'last_sync': None
        }
    
    return {
        'configured': True,
        'rfc': cred_status.get('rfc'),
        'status': cred_status.get('status'),
        'last_sync': cred_status.get('last_sync'),
        'last_sync_result': cred_status.get('last_sync_result'),
        'created_at': cred_status.get('created_at'),
        'updated_at': cred_status.get('updated_at')
    }


@router.post("/credentials")
async def save_sat_credentials(
    data: SATCredentialsRequest,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Save SAT credentials (RFC + CIEC) for the company
    Credentials are encrypted before storage
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Validate RFC format
    rfc = data.rfc.strip().upper()
    if len(rfc) < 12 or len(rfc) > 13:
        raise HTTPException(status_code=400, detail="RFC inválido. Debe tener 12 o 13 caracteres.")
    
    # Validate CIEC
    ciec = data.ciec.strip()
    if len(ciec) < 8:
        raise HTTPException(status_code=400, detail="CIEC inválida. Debe tener al menos 8 caracteres.")
    
    credential_manager = SATCredentialManager(db)
    
    try:
        result = await credential_manager.save_credentials(company_id, rfc, ciec)
        await audit_log(company_id, 'SATCredentials', result['id'], 'CREATE', current_user['id'])
        
        return {
            'success': True,
            'rfc': rfc,
            'message': 'Credenciales SAT guardadas correctamente. Puede probar la conexión.'
        }
    except Exception as e:
        logger.error(f"Error saving SAT credentials: {e}")
        raise HTTPException(status_code=500, detail=f"Error guardando credenciales: {str(e)}")


@router.post("/credentials/validate")
async def validate_sat_credentials(
    data: SATCredentialsRequest,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Validate SAT credentials without saving them
    Tests authentication against SAT portal
    """
    company_id = await get_active_company_id(request, current_user)
    
    rfc = data.rfc.strip().upper()
    ciec = data.ciec.strip()
    
    sync_service = SATSyncService(db)
    
    try:
        result = await sync_service.validate_credentials(rfc, ciec)
        
        await audit_log(company_id, 'SATCredentials', 'validation', 'VALIDATE', current_user['id'], {
            'rfc': rfc,
            'success': result.get('success', False)
        })
        
        return result
    except Exception as e:
        logger.error(f"Error validating SAT credentials: {e}")
        raise HTTPException(status_code=500, detail=f"Error validando credenciales: {str(e)}")


@router.delete("/credentials")
async def delete_sat_credentials(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Delete SAT credentials for the company"""
    company_id = await get_active_company_id(request, current_user)
    
    credential_manager = SATCredentialManager(db)
    
    deleted = await credential_manager.delete_credentials(company_id)
    
    if deleted:
        await audit_log(company_id, 'SATCredentials', company_id, 'DELETE', current_user['id'])
        return {'success': True, 'message': 'Credenciales SAT eliminadas'}
    else:
        raise HTTPException(status_code=404, detail="No hay credenciales SAT configuradas")


@router.post("/sync")
async def sync_cfdis_from_sat(
    data: SATSyncRequest,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Synchronize CFDIs from SAT portal
    Downloads CFDIs (emitidos and/or recibidos) for the specified date range
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Parse dates
    try:
        fecha_inicio = datetime.fromisoformat(data.fecha_inicio.replace('Z', '+00:00'))
        fecha_fin = datetime.fromisoformat(data.fecha_fin.replace('Z', '+00:00'))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Formato de fecha inválido: {str(e)}")
    
    # Validate date range (max 1 month)
    if (fecha_fin - fecha_inicio).days > 31:
        raise HTTPException(
            status_code=400, 
            detail="El rango de fechas no puede exceder 31 días. Divida la sincronización en períodos más cortos."
        )
    
    if fecha_fin < fecha_inicio:
        raise HTTPException(status_code=400, detail="La fecha final debe ser posterior a la fecha inicial")
    
    sync_service = SATSyncService(db)
    
    try:
        result = await sync_service.sync_cfdis(
            company_id=company_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            tipo_comprobante=data.tipo_comprobante,
            incluir_emitidos=data.incluir_emitidos,
            incluir_recibidos=data.incluir_recibidos
        )
        
        # Log sync history
        history_doc = {
            'company_id': company_id,
            'user_id': current_user['id'],
            'fecha_inicio': data.fecha_inicio,
            'fecha_fin': data.fecha_fin,
            'tipo_comprobante': data.tipo_comprobante,
            'result': result,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        await db.sat_sync_history.insert_one(history_doc)
        
        await audit_log(company_id, 'SATSync', 'sync', 'SYNC', current_user['id'], result)
        
        return result
        
    except Exception as e:
        logger.error(f"Error syncing from SAT: {e}")
        raise HTTPException(status_code=500, detail=f"Error sincronizando con SAT: {str(e)}")


@router.get("/sync/history")
async def get_sync_history(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    limit: int = Query(10, le=50)
):
    """Get SAT sync history for the company"""
    company_id = await get_active_company_id(request, current_user)
    
    sync_service = SATSyncService(db)
    history = await sync_service.get_sync_history(company_id, limit)
    
    return history


@router.post("/test-connection")
async def test_sat_connection(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Test SAT connection using saved credentials
    Attempts to login and verify connectivity
    """
    company_id = await get_active_company_id(request, current_user)
    
    credential_manager = SATCredentialManager(db)
    credentials = await credential_manager.get_credentials(company_id)
    
    if not credentials:
        raise HTTPException(status_code=404, detail="No hay credenciales SAT configuradas")
    
    sync_service = SATSyncService(db)
    
    try:
        result = await sync_service.validate_credentials(
            credentials['rfc'],
            credentials['ciec']
        )
        
        # Check if Chrome is missing
        if result.get('chrome_missing'):
            # Credentials are valid but we can't test - return success with warning
            return {
                'success': False,
                'chrome_missing': True,
                'error': result.get('error'),
                'rfc': credentials['rfc'],
                'message': 'Credenciales guardadas. La prueba de conexión no está disponible en este servidor.'
            }
        
        # Update credential status based on test
        if result.get('success'):
            await db.sat_credentials.update_one(
                {'company_id': company_id},
                {'$set': {
                    'status': 'active',
                    'last_test': datetime.now(timezone.utc).isoformat(),
                    'last_test_result': 'success'
                }}
            )
        else:
            await db.sat_credentials.update_one(
                {'company_id': company_id},
                {'$set': {
                    'status': 'error',
                    'last_test': datetime.now(timezone.utc).isoformat(),
                    'last_test_result': result.get('error', 'Unknown error')
                }}
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Error testing SAT connection: {e}")
        raise HTTPException(status_code=500, detail=f"Error probando conexión: {str(e)}")


@router.get("/comprobante-types")
async def get_comprobante_types():
    """Get list of CFDI comprobante types for filtering"""
    return [
        {'value': 'todos', 'label': 'Todos los tipos'},
        {'value': 'ingreso', 'label': 'Ingreso (I)'},
        {'value': 'egreso', 'label': 'Egreso (E)'},
        {'value': 'pago', 'label': 'Pago (P)'},
        {'value': 'nomina', 'label': 'Nómina (N)'},
        {'value': 'traslado', 'label': 'Traslado (T)'}
    ]
