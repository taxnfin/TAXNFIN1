"""Belvo bank integration routes"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import os
import logging
import uuid

from core.database import db
from core.auth import get_current_user
from services.audit import audit_log
from models.enums import UserRole, BankConnectionStatus
from models.bank import BankConnection, BankMovementRaw

logger = logging.getLogger(__name__)

router = APIRouter()

# ===== BELVO BANK INTEGRATION =====
# Belvo API configuration - set in .env or use sandbox for testing
BELVO_SECRET_ID = os.environ.get('BELVO_SECRET_ID', '')
BELVO_SECRET_PASSWORD = os.environ.get('BELVO_SECRET_PASSWORD', '')
BELVO_ENV = os.environ.get('BELVO_ENV', 'sandbox')  # sandbox or production

def get_belvo_client():
    """Initialize Belvo client"""
    if not BELVO_SECRET_ID or not BELVO_SECRET_PASSWORD:
        return None
    try:
        from belvo.client import Client
        env_url = 'sandbox' if BELVO_ENV == 'sandbox' else 'production'
        client = Client(BELVO_SECRET_ID, BELVO_SECRET_PASSWORD, env_url)
        return client
    except Exception as e:
        logger.error(f"Error initializing Belvo client: {e}")
        return None

@router.get("/belvo/status")
async def get_belvo_status(current_user: Dict = Depends(get_current_user)):
    """Check if Belvo is configured and connected"""
    client = get_belvo_client()
    configured = client is not None
    
    return {
        'configured': configured,
        'environment': BELVO_ENV if configured else None,
        'message': 'Belvo está configurado' if configured else 'Configura BELVO_SECRET_ID y BELVO_SECRET_PASSWORD en .env'
    }

@router.get("/belvo/institutions")
async def get_belvo_institutions(current_user: Dict = Depends(get_current_user)):
    """Get list of available Mexican bank institutions from Belvo"""
    client = get_belvo_client()
    if not client:
        raise HTTPException(status_code=400, detail="Belvo no está configurado. Agrega las credenciales en .env")
    
    try:
        # Get Mexican institutions that support transactions
        institutions = client.Institutions.list(country_codes='MX')
        
        # Filter for banks (retail) that support transactions
        banks = []
        for inst in institutions:
            if 'TRANSACTIONS' in inst.get('resources', []):
                banks.append({
                    'id': inst.get('name'),
                    'display_name': inst.get('display_name', inst.get('name')),
                    'type': inst.get('type'),
                    'country': inst.get('country_codes', ['MX'])[0] if inst.get('country_codes') else 'MX',
                    'logo': inst.get('logo'),
                    'primary_color': inst.get('primary_color'),
                    'resources': inst.get('resources', [])
                })
        
        return {'institutions': banks, 'count': len(banks)}
    except Exception as e:
        logger.error(f"Error fetching Belvo institutions: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo instituciones: {str(e)}")

@router.post("/belvo/connect")
async def create_belvo_connection(
    data: dict,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Create a new bank connection via Belvo"""
    company_id = await get_active_company_id(request, current_user)
    client = get_belvo_client()
    
    if not client:
        raise HTTPException(status_code=400, detail="Belvo no está configurado")
    
    institution_id = data.get('institution_id')
    bank_account_id = data.get('bank_account_id')  # Our internal bank account ID
    username = data.get('username')
    password = data.get('password')
    
    if not all([institution_id, bank_account_id, username, password]):
        raise HTTPException(status_code=400, detail="Se requieren institution_id, bank_account_id, username y password")
    
    # Verify bank account belongs to company
    bank_account = await db.bank_accounts.find_one({'id': bank_account_id, 'company_id': company_id}, {'_id': 0})
    if not bank_account:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    
    try:
        # Register the link with Belvo
        link = client.Links.create(
            institution=institution_id,
            username=username,
            password=password,
            access_mode='recurrent'  # For automatic updates
        )
        
        if not link:
            raise HTTPException(status_code=500, detail="Error creando conexión con el banco")
        
        # Create bank connection record
        connection = BankConnection(
            company_id=company_id,
            bank_account_id=bank_account_id,
            belvo_link_id=link.get('id'),
            institution_name=link.get('institution', institution_id),
            institution_id=institution_id,
            status='active' if link.get('status') == 'valid' else 'pending'
        )
        
        doc = connection.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        if doc.get('last_sync'):
            doc['last_sync'] = doc['last_sync'].isoformat()
        
        await db.bank_connections.insert_one(doc)
        
        # Update bank account with connection reference
        await db.bank_accounts.update_one(
            {'id': bank_account_id},
            {'$set': {'belvo_connection_id': connection.id, 'belvo_link_id': link.get('id')}}
        )
        
        await audit_log(company_id, 'BankConnection', connection.id, 'CREATE', current_user['id'])
        
        return {
            'status': 'success',
            'connection_id': connection.id,
            'link_id': link.get('id'),
            'message': 'Conexión bancaria creada exitosamente'
        }
        
    except Exception as e:
        logger.error(f"Error creating Belvo connection: {e}")
        raise HTTPException(status_code=500, detail=f"Error conectando con el banco: {str(e)}")

@router.get("/belvo/connections")
async def list_belvo_connections(request: Request, current_user: Dict = Depends(get_current_user)):
    """List all bank connections for the company"""
    company_id = await get_active_company_id(request, current_user)
    
    connections = await db.bank_connections.find({'company_id': company_id, 'activo': True}, {'_id': 0}).to_list(100)
    
    # Enrich with bank account info
    for conn in connections:
        bank_account = await db.bank_accounts.find_one({'id': conn.get('bank_account_id')}, {'_id': 0})
        if bank_account:
            conn['bank_account_name'] = bank_account.get('nombre')
            conn['bank_account_number'] = bank_account.get('numero_cuenta')
            conn['banco'] = bank_account.get('banco')
    
    return connections

@router.post("/belvo/sync/{connection_id}")
async def sync_belvo_transactions(
    connection_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
    date_from: str = None,
    date_to: str = None
):
    """Sync transactions from Belvo for a specific connection"""
    company_id = await get_active_company_id(request, current_user)
    client = get_belvo_client()
    
    if not client:
        raise HTTPException(status_code=400, detail="Belvo no está configurado")
    
    # Get connection
    connection = await db.bank_connections.find_one({
        'id': connection_id, 
        'company_id': company_id
    }, {'_id': 0})
    
    if not connection:
        raise HTTPException(status_code=404, detail="Conexión no encontrada")
    
    link_id = connection.get('belvo_link_id')
    bank_account_id = connection.get('bank_account_id')
    
    # Update sync status
    await db.bank_connections.update_one(
        {'id': connection_id},
        {'$set': {'sync_status': 'syncing'}}
    )
    
    try:
        # Set date range (default last 30 days)
        if not date_from:
            date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not date_to:
            date_to = datetime.now().strftime('%Y-%m-%d')
        
        # Fetch transactions from Belvo
        transactions = client.Transactions.create(
            link=link_id,
            date_from=date_from,
            date_to=date_to
        )
        
        if not transactions:
            transactions = []
        
        # Get bank account currency
        bank_account = await db.bank_accounts.find_one({'id': bank_account_id}, {'_id': 0})
        moneda = bank_account.get('moneda', 'MXN') if bank_account else 'MXN'
        
        imported = 0
        duplicates = 0
        
        for txn in transactions:
            belvo_id = txn.get('id')
            
            # Check for duplicate
            existing = await db.bank_movements_raw.find_one({
                'belvo_transaction_id': belvo_id,
                'company_id': company_id
            })
            
            if existing:
                duplicates += 1
                continue
            
            # Determine transaction type
            amount = txn.get('amount', 0)
            tipo = 'credito' if amount > 0 else 'debito'
            
            # Create raw movement record
            movement = BankMovementRaw(
                company_id=company_id,
                bank_connection_id=connection_id,
                bank_account_id=bank_account_id,
                belvo_transaction_id=belvo_id,
                fecha_movimiento=datetime.fromisoformat(txn.get('value_date', txn.get('accounting_date', datetime.now().isoformat())).replace('Z', '+00:00')),
                fecha_valor=datetime.fromisoformat(txn.get('value_date', datetime.now().isoformat()).replace('Z', '+00:00')) if txn.get('value_date') else None,
                descripcion=txn.get('description', ''),
                referencia=txn.get('reference', ''),
                monto=abs(amount),
                tipo_movimiento=tipo,
                saldo=txn.get('balance', 0),
                categoria_belvo=txn.get('category'),
                subcategoria_belvo=txn.get('subcategory'),
                merchant_name=txn.get('merchant', {}).get('name') if txn.get('merchant') else None,
                moneda=moneda,
                raw_data=txn
            )
            
            doc = movement.model_dump()
            doc['fecha_movimiento'] = doc['fecha_movimiento'].isoformat()
            if doc.get('fecha_valor'):
                doc['fecha_valor'] = doc['fecha_valor'].isoformat()
            doc['created_at'] = doc['created_at'].isoformat()
            
            await db.bank_movements_raw.insert_one(doc)
            imported += 1
        
        # Update connection
        await db.bank_connections.update_one(
            {'id': connection_id},
            {'$set': {
                'last_sync': datetime.now(timezone.utc).isoformat(),
                'sync_status': 'success',
                'sync_error': None
            }}
        )
        
        return {
            'status': 'success',
            'imported': imported,
            'duplicates': duplicates,
            'total_fetched': len(transactions),
            'message': f'Sincronización completada: {imported} nuevos movimientos'
        }
        
    except Exception as e:
        logger.error(f"Error syncing Belvo transactions: {e}")
        await db.bank_connections.update_one(
            {'id': connection_id},
            {'$set': {'sync_status': 'error', 'sync_error': str(e)}}
        )
        raise HTTPException(status_code=500, detail=f"Error sincronizando: {str(e)}")

@router.get("/belvo/movements-raw")
async def list_raw_movements(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    limit: int = Query(100, le=1000),
    procesado: bool = None
):
    """List raw bank movements from Belvo"""
    company_id = await get_active_company_id(request, current_user)
    
    query = {'company_id': company_id}
    if procesado is not None:
        query['procesado'] = procesado
    
    movements = await db.bank_movements_raw.find(query, {'_id': 0}).sort('fecha_movimiento', -1).limit(limit).to_list(limit)
    return movements

@router.post("/belvo/movements-raw/{movement_id}/process")
async def process_raw_movement(
    movement_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Convert a raw Belvo movement into a bank_transaction"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get raw movement
    raw = await db.bank_movements_raw.find_one({
        'id': movement_id,
        'company_id': company_id
    }, {'_id': 0})
    
    if not raw:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    if raw.get('procesado'):
        raise HTTPException(status_code=400, detail="Este movimiento ya fue procesado")
    
    # Create bank transaction from raw movement
    txn_id = str(uuid.uuid4())
    txn_doc = {
        'id': txn_id,
        'company_id': company_id,
        'bank_account_id': raw.get('bank_account_id'),
        'fecha_movimiento': raw.get('fecha_movimiento'),
        'fecha_valor': raw.get('fecha_valor'),
        'descripcion': raw.get('descripcion'),
        'referencia': raw.get('referencia'),
        'monto': raw.get('monto'),
        'tipo_movimiento': raw.get('tipo_movimiento'),
        'saldo': raw.get('saldo'),
        'moneda': raw.get('moneda', 'MXN'),
        'fuente': 'belvo',
        'belvo_movement_id': movement_id,
        'categoria': raw.get('categoria_belvo'),
        'merchant_name': raw.get('merchant_name'),
        'conciliado': False,
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    await db.bank_transactions.insert_one(txn_doc)
    
    # Mark raw movement as processed
    await db.bank_movements_raw.update_one(
        {'id': movement_id},
        {'$set': {'procesado': True}}
    )
    
    return {
        'status': 'success',
        'transaction_id': txn_id,
        'message': 'Movimiento procesado y agregado a transacciones bancarias'
    }

@router.post("/belvo/movements-raw/process-all")
async def process_all_raw_movements(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Process all unprocessed raw movements into bank_transactions"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get all unprocessed movements
    raw_movements = await db.bank_movements_raw.find({
        'company_id': company_id,
        'procesado': False
    }, {'_id': 0}).to_list(10000)
    
    processed = 0
    errors = 0
    
    for raw in raw_movements:
        try:
            txn_id = str(uuid.uuid4())
            txn_doc = {
                'id': txn_id,
                'company_id': company_id,
                'bank_account_id': raw.get('bank_account_id'),
                'fecha_movimiento': raw.get('fecha_movimiento'),
                'fecha_valor': raw.get('fecha_valor'),
                'descripcion': raw.get('descripcion'),
                'referencia': raw.get('referencia'),
                'monto': raw.get('monto'),
                'tipo_movimiento': raw.get('tipo_movimiento'),
                'saldo': raw.get('saldo'),
                'moneda': raw.get('moneda', 'MXN'),
                'fuente': 'belvo',
                'belvo_movement_id': raw.get('id'),
                'categoria': raw.get('categoria_belvo'),
                'merchant_name': raw.get('merchant_name'),
                'conciliado': False,
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            await db.bank_transactions.insert_one(txn_doc)
            await db.bank_movements_raw.update_one(
                {'id': raw.get('id')},
                {'$set': {'procesado': True}}
            )
            processed += 1
        except Exception as e:
            logger.error(f"Error processing movement {raw.get('id')}: {e}")
            errors += 1
    
    return {
        'status': 'success',
        'processed': processed,
        'errors': errors,
        'message': f'Se procesaron {processed} movimientos'
    }

@router.delete("/belvo/connections/{connection_id}")
async def delete_belvo_connection(
    connection_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Delete a bank connection"""
    company_id = await get_active_company_id(request, current_user)
    client = get_belvo_client()
    
    # Get connection
    connection = await db.bank_connections.find_one({
        'id': connection_id,
        'company_id': company_id
    }, {'_id': 0})
    
    if not connection:
        raise HTTPException(status_code=404, detail="Conexión no encontrada")
    
    # Try to delete from Belvo
    if client and connection.get('belvo_link_id'):
        try:
            client.Links.delete(connection.get('belvo_link_id'))
        except Exception as e:
            logger.warning(f"Could not delete Belvo link: {e}")
    
    # Mark as inactive
    await db.bank_connections.update_one(
        {'id': connection_id},
        {'$set': {'activo': False, 'status': 'disconnected'}}
    )
    
    # Remove reference from bank account
    await db.bank_accounts.update_one(
        {'id': connection.get('bank_account_id')},
        {'$unset': {'belvo_connection_id': '', 'belvo_link_id': ''}}
    )
    
    await audit_log(company_id, 'BankConnection', connection_id, 'DELETE', current_user['id'])
    
    return {'status': 'success', 'message': 'Conexión eliminada'}

