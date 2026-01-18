"""
FX Rate Scheduler - Automatic daily synchronization of exchange rates
Runs daily at 9:00 AM Mexico City time (UTC-6)
"""
import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from forex_service import get_forex_service, ForexService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mexico City timezone
MEXICO_TZ = pytz.timezone('America/Mexico_City')

# Global scheduler instance
_scheduler: AsyncIOScheduler = None


async def sync_all_company_rates(db):
    """
    Sync FX rates for all active companies
    Called by the scheduler daily at 9:00 AM Mexico time
    """
    logger.info("=" * 50)
    logger.info("🔄 Iniciando sincronización automática de tasas de cambio...")
    logger.info(f"⏰ Hora actual: {datetime.now(MEXICO_TZ).strftime('%Y-%m-%d %H:%M:%S')} (México)")
    
    try:
        # Get forex service
        service = get_forex_service()
        
        # Fetch rates once (same for all companies)
        rates = await service.get_all_rates()
        
        if not rates:
            logger.warning("⚠️ No se obtuvieron tasas de cambio")
            return
        
        # Log fetched rates
        logger.info("📊 Tasas obtenidas:")
        for currency, info in rates.items():
            if currency != 'MXN':
                logger.info(f"   {currency}: {info['rate']:.4f} MXN ({info['source']})")
        
        # Get all active companies
        companies = await db.companies.find(
            {'activo': {'$ne': False}},
            {'_id': 0, 'id': 1, 'nombre': 1}
        ).to_list(100)
        
        if not companies:
            logger.info("ℹ️ No hay empresas activas para actualizar")
            return
        
        timestamp = datetime.now(pytz.UTC)
        updated_count = 0
        
        for company in companies:
            company_id = company['id']
            company_name = company.get('nombre', company_id)
            
            try:
                for currency, rate_info in rates.items():
                    if currency == 'MXN':
                        continue
                    
                    # Check if rate already exists for today
                    today_start = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                    existing = await db.fx_rates.find_one({
                        'company_id': company_id,
                        'moneda_origen': currency,
                        'moneda_destino': 'MXN',
                        'fecha_vigencia': {'$gte': today_start.isoformat()}
                    })
                    
                    if existing:
                        # Update existing rate
                        await db.fx_rates.update_one(
                            {'_id': existing['_id']},
                            {'$set': {
                                'tasa': rate_info['rate'],
                                'fuente': rate_info['source'],
                                'updated_at': timestamp.isoformat(),
                                'auto_sync': True
                            }}
                        )
                    else:
                        # Insert new rate
                        import uuid
                        await db.fx_rates.insert_one({
                            'id': str(uuid.uuid4()),
                            'company_id': company_id,
                            'moneda_origen': currency,
                            'moneda_destino': 'MXN',
                            'tasa': rate_info['rate'],
                            'fuente': rate_info['source'],
                            'fecha_vigencia': timestamp.isoformat(),
                            'created_at': timestamp.isoformat(),
                            'updated_at': timestamp.isoformat(),
                            'auto_sync': True
                        })
                
                updated_count += 1
                logger.info(f"   ✅ {company_name}: tasas actualizadas")
                
            except Exception as e:
                logger.error(f"   ❌ {company_name}: error - {str(e)}")
        
        logger.info(f"✅ Sincronización completada: {updated_count}/{len(companies)} empresas actualizadas")
        logger.info("=" * 50)
        
        # Store sync log
        await db.system_logs.insert_one({
            'type': 'fx_auto_sync',
            'timestamp': timestamp.isoformat(),
            'companies_updated': updated_count,
            'total_companies': len(companies),
            'rates_fetched': len([r for r in rates.keys() if r != 'MXN']),
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"❌ Error en sincronización automática: {str(e)}")
        # Store error log
        try:
            await db.system_logs.insert_one({
                'type': 'fx_auto_sync',
                'timestamp': datetime.now(pytz.UTC).isoformat(),
                'status': 'error',
                'error': str(e)
            })
        except:
            pass


def create_scheduler(db) -> AsyncIOScheduler:
    """
    Create and configure the scheduler for FX rate synchronization
    """
    global _scheduler
    
    if _scheduler is not None:
        return _scheduler
    
    _scheduler = AsyncIOScheduler(timezone=MEXICO_TZ)
    
    # Schedule daily sync at 9:00 AM Mexico City time
    # Banxico publishes FIX rates around 12:00 PM, but we use "oportuno" (latest available)
    _scheduler.add_job(
        sync_all_company_rates,
        trigger=CronTrigger(hour=9, minute=0, timezone=MEXICO_TZ),
        args=[db],
        id='fx_daily_sync',
        name='Sincronización diaria de tasas de cambio (9:00 AM México)',
        replace_existing=True,
        misfire_grace_time=3600  # Allow 1 hour grace time if missed
    )
    
    # Also add a second sync at 1:00 PM to catch the official FIX rate
    _scheduler.add_job(
        sync_all_company_rates,
        trigger=CronTrigger(hour=13, minute=0, timezone=MEXICO_TZ),
        args=[db],
        id='fx_afternoon_sync',
        name='Sincronización vespertina de tasas (1:00 PM México - FIX oficial)',
        replace_existing=True,
        misfire_grace_time=3600
    )
    
    logger.info("📅 Scheduler configurado:")
    logger.info("   - Sincronización matutina: 9:00 AM (México)")
    logger.info("   - Sincronización vespertina: 1:00 PM (México) - Tasa FIX oficial")
    
    return _scheduler


def start_scheduler(db):
    """Start the scheduler if not already running"""
    global _scheduler
    
    scheduler = create_scheduler(db)
    
    if not scheduler.running:
        scheduler.start()
        logger.info("✅ Scheduler de tasas de cambio iniciado")
        
        # Log next run times
        for job in scheduler.get_jobs():
            next_run = job.next_run_time
            if next_run:
                logger.info(f"   📌 {job.name}: próxima ejecución {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    return scheduler


def stop_scheduler():
    """Stop the scheduler gracefully"""
    global _scheduler
    
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("🛑 Scheduler de tasas de cambio detenido")
        _scheduler = None


async def run_sync_now(db):
    """
    Run sync immediately (for manual triggering or testing)
    """
    logger.info("🔄 Ejecutando sincronización manual de tasas...")
    await sync_all_company_rates(db)


def get_scheduler_status():
    """Get current scheduler status and next run times"""
    global _scheduler
    
    if not _scheduler:
        return {
            'running': False,
            'jobs': []
        }
    
    jobs_info = []
    for job in _scheduler.get_jobs():
        jobs_info.append({
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
            'next_run_formatted': job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z') if job.next_run_time else None
        })
    
    return {
        'running': _scheduler.running,
        'timezone': str(MEXICO_TZ),
        'jobs': jobs_info
    }
