"""TaxnFin Cashflow API - Main Application Entry Point"""
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# ===== CONFIGURATION =====
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="TaxnFin Cashflow API", version="2.0.0")
api_router = APIRouter(prefix="/api")

# ===== IMPORT ROUTERS =====
from routes.auth import router as auth_router
from routes.companies import router as companies_router
from routes.categories import router as categories_router
from routes.vendors import router as vendors_router
from routes.customers import router as customers_router
from routes.bank_accounts import router as bank_accounts_router
from routes.payments import router as payments_router
from routes.reconciliations import router as reconciliations_router
from routes.cfdi import router as cfdi_router
from routes.fx_rates import router as fx_rates_router
from routes.bank_transactions import router as bank_transactions_router
from routes.sat import router as sat_router
from routes.pdf_invoices import router as pdf_invoices_router
from routes.alegra import router as alegra_router
from routes.treasury import router as treasury_router
from routes.financial_statements import router as financial_statements_router
from routes.belvo import router as belvo_router
from routes.reports import router as reports_router
from routes.scenarios import router as scenarios_router
from routes.exports import router as exports_router
from routes.advanced import router as advanced_router
from routes.projections import router as projections_router
from routes.import_templates import router as import_templates_router
from routes.cashflow import router as cashflow_router
from routes.payment_matching import router as payment_matching_router
from routes.cfdi_operations import router as cfdi_operations_router
from routes.bank_import import router as bank_import_router
from routes.notifications import router as notifications_router
from routes.integrations import router as integrations_router
from routes.account_mappings import router as account_mappings_router

# ===== REGISTER ROUTERS =====
api_router.include_router(auth_router)
api_router.include_router(companies_router)
api_router.include_router(categories_router)
api_router.include_router(vendors_router)
api_router.include_router(customers_router)
api_router.include_router(bank_accounts_router)
api_router.include_router(payments_router)
api_router.include_router(reconciliations_router)
api_router.include_router(cfdi_router)
api_router.include_router(fx_rates_router)
api_router.include_router(bank_transactions_router)
api_router.include_router(sat_router)
api_router.include_router(pdf_invoices_router)
api_router.include_router(alegra_router)
api_router.include_router(treasury_router)
api_router.include_router(financial_statements_router)
api_router.include_router(belvo_router)
api_router.include_router(reports_router)
api_router.include_router(scenarios_router)
api_router.include_router(exports_router)
api_router.include_router(advanced_router)
api_router.include_router(projections_router)
api_router.include_router(import_templates_router)
api_router.include_router(cashflow_router)
api_router.include_router(payment_matching_router)
api_router.include_router(cfdi_operations_router)
api_router.include_router(bank_import_router)
api_router.include_router(notifications_router)
api_router.include_router(integrations_router)
api_router.include_router(account_mappings_router)

# ===== MIDDLEWARE =====
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ===== GLOBAL EXCEPTION HANDLER =====
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Error interno del servidor. Por favor, intente de nuevo.",
            "error_type": type(exc).__name__
        }
    )

# ===== LIFECYCLE EVENTS =====
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        from fx_scheduler import start_scheduler
        start_scheduler(db)
        logging.info("FX Rate Scheduler iniciado correctamente")
    except Exception as e:
        logging.error(f"Error iniciando FX Scheduler: {e}")
    
    try:
        from services.integration_scheduler import start_integration_scheduler
        start_integration_scheduler(db, interval_hours=6)
        logging.info("Integration Scheduler iniciado (cada 6h)")
    except Exception as e:
        logging.error(f"Error iniciando Integration Scheduler: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    try:
        from fx_scheduler import stop_scheduler
        stop_scheduler()
    except:
        pass
    try:
        from services.integration_scheduler import stop_integration_scheduler
        stop_integration_scheduler()
    except:
        pass
    client.close()
