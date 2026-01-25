# Routes module - API endpoints organized by domain
# Refactoring Status: January 25, 2026

from fastapi import APIRouter

# ✅ ALL 11 ROUTERS NOW INTEGRATED
from .auth import router as auth_router
from .companies import router as companies_router
from .categories import router as categories_router
from .vendors import router as vendors_router
from .customers import router as customers_router
from .bank_accounts import router as bank_accounts_router
from .payments import router as payments_router
from .reconciliations import router as reconciliations_router
from .cfdi import router as cfdi_router
from .fx_rates import router as fx_rates_router
from .bank_transactions import router as bank_transactions_router

__all__ = [
    'auth_router',
    'companies_router',
    'categories_router',
    'vendors_router',
    'customers_router',
    'bank_accounts_router',
    'payments_router',
    'reconciliations_router',
    'cfdi_router',
    'fx_rates_router',
    'bank_transactions_router',
]

# MIGRATION SUMMARY (January 25, 2026):
# =====================================
# 11 routers integrated:
# - auth_router: 7 endpoints
# - companies_router: 4 endpoints
# - categories_router: 6 endpoints
# - vendors_router: 4 endpoints
# - customers_router: 4 endpoints
# - bank_accounts_router: 5 endpoints
# - payments_router: 6 endpoints
# - reconciliations_router: 7 endpoints
# - cfdi_router: 7 endpoints (NEW)
# - fx_rates_router: 7 endpoints (NEW)
# - bank_transactions_router: 8 endpoints (NEW)
#
# Total: 65 endpoints in modular routers
# server.py: 7,408 lines (reduced from 8,630)
# server.py endpoints: 84 (reduced from 127)
#
# Remaining in server.py:
# - CFDI upload (complex XML parsing + AI)
# - Advanced AI categorization
# - Reports/Dashboard
# - Belvo integration
# - Exports (DIOT, COI, etc.)
# - PDF/Excel import
