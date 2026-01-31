"""
SAT Integration Routes - CFDI download from SAT using FIEL (e.firma)
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, UploadFile, File, Form
from typing import Dict, Optional, List
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
import logging
import base64

from core.database import db
from core.auth import get_current_user, get_active_company_id
from services.audit import audit_log
from modules.sat_fiel import SATFIELCredentialManager, SATFIELSyncService, FIELManager

router = APIRouter(prefix="/sat")
logger = logging.getLogger(__name__)


class SATSyncRequest(BaseModel):
    """Request model for SAT sync"""
    fecha_inicio: str
    fecha_fin: str
    tipo_comprobante: Optional[str] = None
    tipo_solicitud: str = 'CFDI'


class CheckRequestModel(BaseModel):
    """Model for checking request status"""
    id_solicitud: str


class DownloadPackageModel(BaseModel):
    """Model for downloading a package"""
    id_paquete: str


@router.get("/status")
async def get_sat_status(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Get SAT integration status for the company"""
    company_id = await get_active_company_id(request, current_user)
    credential_manager = SATFIELCredentialManager(db)
    
    cred_status = await credential_manager.get_status(company_id)
    
    if not cred_status:
        return {
            'configured': False,
            'auth_type': None,
            'message': 'No hay credenciales SAT configuradas',
            'last_sync': None
        }
    
    return {
        'configured': True,
        'auth_type': cred_status.get('auth_type', 'fiel'),
        'rfc': cred_status.get('rfc'),
        'serial_number': cred_status.get('serial_number'),
        'status': cred_status.get('status'),
        'valid_from': cred_status.get('valid_from'),
        'valid_to': cred_status.get('valid_to'),
        'last_sync': cred_status.get('last_sync'),
        'last_sync_result': cred_status.get('last_sync_result'),
        'last_test': cred_status.get('last_test'),
        'last_test_result': cred_status.get('last_test_result'),
        'created_at': cred_status.get('created_at'),
        'updated_at': cred_status.get('updated_at')
    }


@router.post("/fiel/upload")
async def upload_fiel(
    request: Request,
    cer_file: UploadFile = File(..., description="Archivo .cer de la FIEL"),
    key_file: UploadFile = File(..., description="Archivo .key de la FIEL"),
    password: str = Form(..., description="Contraseña de la llave privada"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Upload FIEL credentials (.cer and .key files)
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Validate file extensions
    if not cer_file.filename.lower().endswith('.cer'):
        raise HTTPException(status_code=400, detail="El archivo de certificado debe tener extensión .cer")
    
    if not key_file.filename.lower().endswith('.key'):
        raise HTTPException(status_code=400, detail="El archivo de llave debe tener extensión .key")
    
    try:
        # Read file contents
        cer_content = await cer_file.read()
        key_content = await key_file.read()
        
        if len(cer_content) == 0:
            raise HTTPException(status_code=400, detail="El archivo .cer está vacío")
        
        if len(key_content) == 0:
            raise HTTPException(status_code=400, detail="El archivo .key está vacío")
        
        credential_manager = SATFIELCredentialManager(db)
        result = await credential_manager.save_fiel(company_id, cer_content, key_content, password)
        
        if result.get('success'):
            await audit_log(company_id, 'SATFIEL', result.get('serial_number', ''), 'CREATE', current_user['id'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading FIEL: {e}")
        raise HTTPException(status_code=500, detail=f"Error procesando archivos: {str(e)}")


@router.post("/fiel/validate")
async def validate_fiel(
    request: Request,
    cer_file: UploadFile = File(...),
    key_file: UploadFile = File(...),
    password: str = Form(...),
    current_user: Dict = Depends(get_current_user)
):
    """
    Validate FIEL credentials without saving them
    """
    try:
        cer_content = await cer_file.read()
        key_content = await key_file.read()
        
        # Try to load FIEL
        fiel = FIELManager(cer_content, key_content, password)
        
        return {
            'success': True,
            'rfc': fiel.rfc,
            'serial_number': fiel.serial_number,
            'valid_from': fiel.not_before.isoformat() if fiel.not_before else None,
            'valid_to': fiel.not_after.isoformat() if fiel.not_after else None,
            'is_valid': fiel.is_valid(),
            'message': 'FIEL válida' if fiel.is_valid() else 'FIEL expirada'
        }
        
    except ValueError as e:
        return {'success': False, 'error': str(e)}
    except Exception as e:
        logger.error(f"Error validating FIEL: {e}")
        return {'success': False, 'error': f'Error validando FIEL: {str(e)}'}


@router.delete("/credentials")
async def delete_sat_credentials(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Delete SAT credentials (FIEL) for the company"""
    company_id = await get_active_company_id(request, current_user)
    
    credential_manager = SATFIELCredentialManager(db)
    deleted = await credential_manager.delete_fiel(company_id)
    
    if deleted:
        await audit_log(company_id, 'SATFIEL', company_id, 'DELETE', current_user['id'])
        return {'success': True, 'message': 'Credenciales SAT eliminadas'}
    else:
        raise HTTPException(status_code=404, detail="No hay credenciales SAT configuradas")


@router.post("/test-connection")
async def test_sat_connection(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Test SAT connection using saved FIEL
    Attempts to authenticate with the SAT web service
    """
    company_id = await get_active_company_id(request, current_user)
    
    sync_service = SATFIELSyncService(db)
    result = await sync_service.test_connection(company_id)
    
    return result


@router.post("/request-download")
async def request_cfdi_download(
    data: SATSyncRequest,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Request CFDI download from SAT
    This creates a download request that SAT will process asynchronously
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Parse dates
    try:
        fecha_inicio = datetime.fromisoformat(data.fecha_inicio.replace('Z', '+00:00'))
        fecha_fin = datetime.fromisoformat(data.fecha_fin.replace('Z', '+00:00'))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Formato de fecha inválido: {str(e)}")
    
    # Validate date range (SAT allows max 1 day for XML, more for metadata)
    if data.tipo_solicitud == 'CFDI' and (fecha_fin - fecha_inicio).days > 1:
        raise HTTPException(
            status_code=400,
            detail="Para descarga de XML, el rango máximo es 1 día. Use tipo 'Metadata' para rangos mayores."
        )
    
    if (fecha_fin - fecha_inicio).days > 7:
        raise HTTPException(
            status_code=400,
            detail="El rango máximo de fechas es 7 días. Divida la solicitud en períodos más cortos."
        )
    
    sync_service = SATFIELSyncService(db)
    result = await sync_service.request_download(
        company_id=company_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        tipo_comprobante=data.tipo_comprobante,
        tipo_solicitud=data.tipo_solicitud
    )
    
    if result.get('success'):
        await audit_log(company_id, 'SATDownloadRequest', result.get('id_solicitud', ''), 'CREATE', current_user['id'])
    
    return result


@router.post("/check-request")
async def check_download_request(
    data: CheckRequestModel,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Check status of a download request
    """
    company_id = await get_active_company_id(request, current_user)
    
    sync_service = SATFIELSyncService(db)
    result = await sync_service.check_request_status(company_id, data.id_solicitud)
    
    return result


@router.post("/download-package")
async def download_package(
    data: DownloadPackageModel,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Download and process a CFDI package
    """
    company_id = await get_active_company_id(request, current_user)
    
    sync_service = SATFIELSyncService(db)
    result = await sync_service.download_and_process_package(company_id, data.id_paquete)
    
    if result.get('success'):
        await audit_log(company_id, 'SATPackageDownload', data.id_paquete, 'DOWNLOAD', current_user['id'], {
            'cfdis_new': result.get('cfdis_new', 0),
            'cfdis_updated': result.get('cfdis_updated', 0)
        })
    
    return result


@router.get("/requests")
async def get_download_requests(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    limit: int = Query(20, le=100)
):
    """Get list of download requests for the company"""
    company_id = await get_active_company_id(request, current_user)
    
    requests_list = await db.sat_download_requests.find(
        {'company_id': company_id},
        {'_id': 0}
    ).sort('created_at', -1).limit(limit).to_list(limit)
    
    return requests_list


@router.get("/comprobante-types")
async def get_comprobante_types():
    """Get list of CFDI comprobante types for filtering"""
    return [
        {'value': 'todos', 'label': 'Todos los tipos'},
        {'value': 'I', 'label': 'Ingreso (I)'},
        {'value': 'E', 'label': 'Egreso (E)'},
        {'value': 'P', 'label': 'Pago (P)'},
        {'value': 'N', 'label': 'Nómina (N)'},
        {'value': 'T', 'label': 'Traslado (T)'}
    ]


@router.get("/solicitud-types")
async def get_solicitud_types():
    """Get list of download request types"""
    return [
        {'value': 'CFDI', 'label': 'XML Completos (máx. 1 día)'},
        {'value': 'Metadata', 'label': 'Solo Metadatos (máx. 7 días)'}
    ]
