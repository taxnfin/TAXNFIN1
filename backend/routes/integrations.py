"""Integrations management routes - Multi-system accounting connector"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import uuid
import logging

from core.database import db
from core.auth import get_current_user
from models.enums import UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations")

# Supported integration types
SUPPORTED_INTEGRATIONS = {
    'contalink': {
        'name': 'CONTALink',
        'description': 'Sistema contable mexicano - balanza, pólizas, facturas',
        'capabilities': ['trial_balance', 'invoices', 'conciliation', 'account_balance'],
        'auth_type': 'api_key',
        'fields': ['api_key'],
    },
    'alegra': {
        'name': 'Alegra',
        'description': 'Facturación electrónica y contabilidad en la nube',
        'capabilities': ['invoices_cxc', 'invoices_cxp', 'contacts', 'financial_statements'],
        'auth_type': 'api_key',
        'fields': ['email', 'api_token'],
    },
    'quickbooks': {
        'name': 'QuickBooks',
        'description': 'Contabilidad Intuit - balance, P&L, facturas',
        'capabilities': ['trial_balance', 'profit_loss', 'invoices', 'contacts'],
        'auth_type': 'oauth2',
        'fields': ['client_id', 'client_secret', 'realm_id'],
        'status': 'coming_soon',
    },
    'contpaqi': {
        'name': 'CONTPAQi',
        'description': 'Sistema contable mexicano - importación/exportación de pólizas',
        'capabilities': ['polizas', 'catalogo_cuentas', 'balanza'],
        'auth_type': 'file_import',
        'fields': [],
        'status': 'coming_soon',
    },
    'xero': {
        'name': 'Xero',
        'description': 'Contabilidad en la nube - ideal para empresas internacionales',
        'capabilities': ['trial_balance', 'invoices', 'bank_feeds'],
        'auth_type': 'oauth2',
        'fields': ['client_id', 'client_secret'],
        'status': 'coming_soon',
    },
    'sap': {
        'name': 'SAP Business One',
        'description': 'ERP empresarial - estados financieros y operaciones',
        'capabilities': ['financial_statements', 'journals', 'cost_centers'],
        'auth_type': 'service_layer',
        'fields': ['host', 'company_db', 'username', 'password'],
        'status': 'coming_soon',
    },
}


class IntegrationConnect(BaseModel):
    integration_type: str
    credentials: Dict[str, str]
    label: Optional[str] = None


class IntegrationUpdate(BaseModel):
    credentials: Optional[Dict[str, str]] = None
    label: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/available")
async def get_available_integrations(current_user: Dict = Depends(get_current_user)):
    """Get list of all supported integrations with their capabilities"""
    return list(SUPPORTED_INTEGRATIONS.values()) + [
        {**v, 'key': k} for k, v in SUPPORTED_INTEGRATIONS.items()
    ]


@router.get("/available-list")
async def get_integrations_list(current_user: Dict = Depends(get_current_user)):
    """Get clean list of available integrations"""
    result = []
    for key, info in SUPPORTED_INTEGRATIONS.items():
        result.append({
            'key': key,
            'name': info['name'],
            'description': info['description'],
            'capabilities': info['capabilities'],
            'auth_type': info['auth_type'],
            'fields': info['fields'],
            'status': info.get('status', 'available'),
        })
    return result


@router.get("/connected")
async def get_connected_integrations(current_user: Dict = Depends(get_current_user)):
    """Get all connected integrations for the user's company"""
    integrations = await db.integrations.find(
        {'company_id': current_user['company_id']},
        {'_id': 0, 'credentials': 0}  # Never expose credentials
    ).to_list(50)
    
    for i in integrations:
        if isinstance(i.get('connected_at'), datetime):
            i['connected_at'] = i['connected_at'].isoformat()
        if isinstance(i.get('last_sync'), datetime):
            i['last_sync'] = i['last_sync'].isoformat()
    
    return integrations


@router.post("/connect")
async def connect_integration(data: IntegrationConnect, current_user: Dict = Depends(get_current_user)):
    """Connect a new integration for the company"""
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    if data.integration_type not in SUPPORTED_INTEGRATIONS:
        raise HTTPException(status_code=400, detail=f"Tipo de integración no soportado: {data.integration_type}")
    
    info = SUPPORTED_INTEGRATIONS[data.integration_type]
    if info.get('status') == 'coming_soon':
        raise HTTPException(status_code=400, detail=f"{info['name']} estará disponible próximamente")
    
    # Check if already connected
    existing = await db.integrations.find_one({
        'company_id': current_user['company_id'],
        'integration_type': data.integration_type,
    })
    if existing:
        raise HTTPException(status_code=400, detail=f"{info['name']} ya está conectado. Desconéctalo primero para reconectar.")
    
    # Test connection for supported types
    connection_status = 'pending'
    if data.integration_type == 'contalink':
        from services.contalink import ContalinkClient
        client = ContalinkClient(data.credentials.get('api_key', ''))
        test = await client.test_connection()
        connection_status = test['status']
        if connection_status == 'error':
            raise HTTPException(status_code=400, detail=f"Error conectando a CONTALink: {test['message']}")
    elif data.integration_type == 'alegra':
        connection_status = 'connected'  # Alegra validation happens on sync
    
    doc = {
        'id': str(uuid.uuid4()),
        'company_id': current_user['company_id'],
        'integration_type': data.integration_type,
        'name': info['name'],
        'label': data.label or info['name'],
        'credentials': data.credentials,
        'connection_status': connection_status,
        'is_active': True,
        'last_sync': None,
        'sync_count': 0,
        'connected_at': datetime.now(timezone.utc).isoformat(),
        'connected_by': current_user['id'],
    }
    
    await db.integrations.insert_one(doc)
    
    # Return without credentials
    del doc['credentials']
    if '_id' in doc:
        del doc['_id']
    
    return doc


@router.post("/{integration_id}/test")
async def test_integration(integration_id: str, current_user: Dict = Depends(get_current_user)):
    """Test an existing integration connection"""
    integration = await db.integrations.find_one(
        {'id': integration_id, 'company_id': current_user['company_id']}
    )
    if not integration:
        raise HTTPException(status_code=404, detail="Integración no encontrada")
    
    if integration['integration_type'] == 'contalink':
        from services.contalink import ContalinkClient
        client = ContalinkClient(integration['credentials'].get('api_key', ''))
        result = await client.test_connection()
        
        await db.integrations.update_one(
            {'id': integration_id},
            {'$set': {'connection_status': result['status']}}
        )
        return result
    
    return {'status': 'unknown', 'message': 'Test no disponible para este tipo'}


@router.post("/{integration_id}/sync")
async def sync_integration(integration_id: str, current_user: Dict = Depends(get_current_user)):
    """Trigger a full sync for the integration — fetches data and maps to financial statements"""
    integration = await db.integrations.find_one(
        {'id': integration_id, 'company_id': current_user['company_id']}
    )
    if not integration:
        raise HTTPException(status_code=404, detail="Integración no encontrada")
    
    if integration['integration_type'] == 'contalink':
        from services.integration_scheduler import sync_contalink_for_company
        result = await sync_contalink_for_company(db, integration)
        
        if result.get('status') == 'error':
            return {'status': 'error', 'message': result.get('message', 'Error en sincronización')}
        
        synced = result.get('results', [])
        mapped_count = sum(1 for r in synced if r.get('mapped'))
        items_total = sum(r.get('items', 0) for r in synced)
        
        return {
            'status': 'success',
            'message': f'Sincronizado: {items_total} cuentas en {mapped_count} períodos → estados financieros actualizados',
            'details': synced
        }
    
    return {'status': 'error', 'message': 'Sincronización no disponible para este tipo'}


@router.delete("/{integration_id}")
async def disconnect_integration(integration_id: str, current_user: Dict = Depends(get_current_user)):
    """Disconnect (remove) an integration"""
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    result = await db.integrations.delete_one({
        'id': integration_id,
        'company_id': current_user['company_id']
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Integración no encontrada")
    
    return {'status': 'ok', 'message': 'Integración desconectada'}


# ===== ADMIN DASHBOARD =====

@router.get("/admin/all-companies")
async def admin_get_all_companies(current_user: Dict = Depends(get_current_user)):
    """Admin: Get all companies with their integration status and metrics"""
    if current_user['role'] != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Solo administradores")
    
    companies = await db.companies.find({}, {'_id': 0}).to_list(100)
    
    result = []
    for company in companies:
        company_id = company['id']
        
        # Count resources
        users_count = await db.users.count_documents({'company_id': company_id})
        cfdis_count = await db.cfdis.count_documents({'company_id': company_id})
        integrations = await db.integrations.find(
            {'company_id': company_id},
            {'_id': 0, 'credentials': 0}
        ).to_list(10)
        
        # Get latest financial period
        latest_fs = await db.financial_statements.find_one(
            {'company_id': company_id},
            {'_id': 0, 'periodo': 1, 'tipo': 1},
            sort=[('periodo', -1)]
        )
        
        for i in integrations:
            if isinstance(i.get('connected_at'), datetime):
                i['connected_at'] = i['connected_at'].isoformat()
            if isinstance(i.get('last_sync'), datetime):
                i['last_sync'] = i['last_sync'].isoformat()
        
        result.append({
            'id': company_id,
            'nombre': company.get('nombre', ''),
            'rfc': company.get('rfc', ''),
            'moneda_base': company.get('moneda_base', 'MXN'),
            'users_count': users_count,
            'cfdis_count': cfdis_count,
            'integrations': integrations,
            'latest_period': latest_fs.get('periodo') if latest_fs else None,
            'created_at': company.get('created_at', ''),
        })
    
    return result


@router.get("/admin/all-users")
async def admin_get_all_users(current_user: Dict = Depends(get_current_user)):
    """Admin: Get all users across all companies"""
    if current_user['role'] != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Solo administradores")
    
    users = await db.users.find({}, {'_id': 0, 'password_hash': 0}).to_list(200)
    return users
