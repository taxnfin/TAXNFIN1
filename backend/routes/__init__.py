# Routes module - API endpoints organized by domain
# Refactoring Status: January 25, 2026

from fastapi import APIRouter

# ✅ ALL ROUTERS NOW INTEGRATED
from .auth import router as auth_router
from .companies import router as companies_router
from .categories import router as categories_router
from .vendors import router as vendors_router
from .customers import router as customers_router
from .bank_accounts import router as bank_accounts_router
from .payments import router as payments_router
from .reconciliations import router as reconciliations_router

__all__ = [
    'auth_router',
    'companies_router',
    'categories_router',
    'vendors_router',
    'customers_router',
    'bank_accounts_router',
    'payments_router',
    'reconciliations_router',
]

# MIGRATION SUMMARY (January 25, 2026):
# =====================================
# ALL 8 routers now integrated:
# - auth_router: 7 endpoints (login, register, me, auth0)
# - companies_router: 4 endpoints (CRUD)
# - categories_router: 6 endpoints (categories + subcategories CRUD)
# - vendors_router: 4 endpoints (CRUD)
# - customers_router: 4 endpoints (CRUD)
# - bank_accounts_router: 5 endpoints (CRUD + summary)
# - payments_router: 6 endpoints (CRUD + complete + bulk delete)
# - reconciliations_router: 7 endpoints (CRUD + summary + mark-without-uuid + bulk delete)
#
# Total: 43 endpoints in modular routers
# server.py reduced: 8,630 -> 7,402 lines (~14% reduction)
#
# Specialized endpoints still in server.py:
# - CFDI endpoints (~10)
# - FX Rates endpoints (~10)
# - Bank Transactions endpoints (~13)
# - Belvo integration (~9)
# - Reports endpoints (~5)
# - Advanced AI endpoints
