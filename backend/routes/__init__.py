# Routes module - API endpoints organized by domain
from fastapi import APIRouter

# Import all route modules
from .auth import router as auth_router
from .companies import router as companies_router
from .bank_accounts import router as bank_accounts_router
from .vendors import router as vendors_router
from .customers import router as customers_router
from .categories import router as categories_router
from .payments import router as payments_router
from .reconciliations import router as reconciliations_router

# Main API router that includes all sub-routers
api_router = APIRouter(prefix="/api")

# Include all routers
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(companies_router, tags=["companies"])
api_router.include_router(bank_accounts_router, tags=["bank-accounts"])
api_router.include_router(vendors_router, tags=["vendors"])
api_router.include_router(customers_router, tags=["customers"])
api_router.include_router(categories_router, tags=["categories"])
api_router.include_router(payments_router, tags=["payments"])
api_router.include_router(reconciliations_router, tags=["reconciliations"])

__all__ = ['api_router']
