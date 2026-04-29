"""
Integration Scheduler - Automatic periodic sync for CONTALink, Alegra, and other accounting systems.
Runs every 6 hours for active integrations.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_sync_task = None


async def sync_contalink_for_company(db, integration: dict):
    """Sync CONTALink data: trial balance → financial statements"""
    from services.contalink import ContalinkClient
    from services.account_mapper import map_trial_balance_to_statements
    
    api_key = integration.get('credentials', {}).get('api_key', '')
    if not api_key:
        return {'status': 'error', 'message': 'No API key'}
    
    client = ContalinkClient(api_key)
    company_id = integration['company_id']
    
    # Sync last 3 months of trial balance
    now = datetime.now()
    results = []
    
    for months_back in range(3):
        target = now - timedelta(days=30 * months_back)
        year = target.year
        month = target.month
        start = f"{year}-{month:02d}-01"
        # Last day of month
        if month == 12:
            end = f"{year}-12-31"
        else:
            next_m = datetime(year, month + 1, 1) - timedelta(days=1)
            end = next_m.strftime("%Y-%m-%d")
        periodo = f"{year}-{month:02d}"
        
        try:
            tb = await client.get_trial_balance(start, end)
            items = tb.get('trial_balance', {}).get('items', [])
            
            if not items:
                continue
            
            # Save raw trial balance
            await db.integration_sync_data.update_one(
                {'integration_id': integration['id'], 'type': 'trial_balance', 'period': periodo},
                {'$set': {
                    'company_id': company_id,
                    'integration_id': integration['id'],
                    'type': 'trial_balance',
                    'period': periodo,
                    'data': tb,
                    'synced_at': datetime.now(timezone.utc).isoformat(),
                }},
                upsert=True
            )
            
            # Map trial balance to financial statements
            mapped = map_trial_balance_to_statements(items)
            
            if mapped.get('income'):
                await db.financial_statements.update_one(
                    {'company_id': company_id, 'tipo': 'estado_resultados', 'periodo': periodo},
                    {'$set': {
                        'company_id': company_id,
                        'tipo': 'estado_resultados',
                        'periodo': periodo,
                        'año': year,
                        'mes': month,
                        'datos': mapped['income'],
                        'archivo_original': f'CONTALink auto-sync {periodo}',
                        'source': 'contalink',
                        'updated_at': datetime.now(timezone.utc).isoformat(),
                    },
                    '$setOnInsert': {'created_at': datetime.now(timezone.utc).isoformat()}},
                    upsert=True
                )
            
            if mapped.get('balance'):
                await db.financial_statements.update_one(
                    {'company_id': company_id, 'tipo': 'balance_general', 'periodo': periodo},
                    {'$set': {
                        'company_id': company_id,
                        'tipo': 'balance_general',
                        'periodo': periodo,
                        'año': year,
                        'mes': month,
                        'datos': mapped['balance'],
                        'archivo_original': f'CONTALink auto-sync {periodo}',
                        'source': 'contalink',
                        'updated_at': datetime.now(timezone.utc).isoformat(),
                    },
                    '$setOnInsert': {'created_at': datetime.now(timezone.utc).isoformat()}},
                    upsert=True
                )
            
            results.append({'period': periodo, 'items': len(items), 'mapped': True})
            
        except Exception as e:
            logger.error(f"CONTALink sync error for {periodo}: {e}")
            results.append({'period': periodo, 'error': str(e)})
    
    # Update integration status
    await db.integrations.update_one(
        {'id': integration['id']},
        {'$set': {
            'last_sync': datetime.now(timezone.utc).isoformat(),
            'connection_status': 'connected',
            'sync_count': integration.get('sync_count', 0) + 1,
        }}
    )
    
    return {'status': 'success', 'results': results}


async def sync_alegra_for_company(db, integration: dict):
    """Sync Alegra data: generate financial statements from synced invoices/bills"""
    from services.alegra_financials import generate_alegra_financial_statements
    
    company_id = integration['company_id']
    
    # Check if Alegra is connected at company level
    company = await db.companies.find_one({'id': company_id}, {'_id': 0})
    if not company or not company.get('alegra_connected'):
        return {'status': 'skipped', 'message': 'Alegra not connected at company level'}
    
    # Generate financial statements for last 3 months
    now = datetime.now()
    results = []
    for months_back in range(3):
        target = now - timedelta(days=30 * months_back)
        periodo = f"{target.year}-{target.month:02d}"
        try:
            result = await generate_alegra_financial_statements(db, company_id, periodo)
            results.append(result)
        except Exception as e:
            results.append({'periodo': periodo, 'error': str(e)})
    
    # Update integration status
    await db.integrations.update_one(
        {'id': integration['id']},
        {'$set': {
            'last_sync': datetime.now(timezone.utc).isoformat(),
            'connection_status': 'connected',
            'sync_count': integration.get('sync_count', 0) + 1,
        }}
    )
    
    return {'status': 'success', 'results': results}


async def run_all_syncs(db):
    """Run sync for all active integrations across all companies"""
    logger.info("=" * 50)
    logger.info("INTEGRATION SYNC - Starting automatic sync cycle")
    logger.info("=" * 50)
    
    integrations = await db.integrations.find(
        {'is_active': True},
        {'_id': 0}
    ).to_list(100)
    
    if not integrations:
        logger.info("No active integrations to sync")
        return
    
    for integration in integrations:
        itype = integration.get('integration_type', '')
        iname = integration.get('label', integration.get('name', ''))
        logger.info(f"Syncing {iname} ({itype}) for company {integration['company_id'][:8]}...")
        
        try:
            if itype == 'contalink':
                result = await sync_contalink_for_company(db, integration)
            elif itype == 'alegra':
                result = await sync_alegra_for_company(db, integration)
            else:
                result = {'status': 'skipped', 'message': f'No sync handler for {itype}'}
            
            logger.info(f"  Result: {result.get('status', 'unknown')}")
        except Exception as e:
            logger.error(f"  Error syncing {iname}: {e}")
    
    logger.info("INTEGRATION SYNC - Cycle complete")


async def _sync_loop(db, interval_hours: int = 6):
    """Background loop that runs syncs periodically"""
    while True:
        try:
            await run_all_syncs(db)
        except Exception as e:
            logger.error(f"Integration sync loop error: {e}")
        
        await asyncio.sleep(interval_hours * 3600)


def start_integration_scheduler(db, interval_hours: int = 6):
    """Start the background integration sync loop"""
    global _sync_task
    
    if _sync_task is not None:
        return
    
    loop = asyncio.get_event_loop()
    _sync_task = loop.create_task(_sync_loop(db, interval_hours))
    logger.info(f"Integration scheduler started (every {interval_hours}h)")


def stop_integration_scheduler():
    """Stop the integration sync loop"""
    global _sync_task
    if _sync_task:
        _sync_task.cancel()
        _sync_task = None
