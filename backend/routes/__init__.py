# Routes module - API endpoints organized by domain
# Refactoring Status: January 25, 2026

from fastapi import APIRouter

# ✅ INTEGRATED ROUTERS (imported and used in server.py)
from .auth import router as auth_router
from .companies import router as companies_router
from .categories import router as categories_router
from .vendors import router as vendors_router
from .customers import router as customers_router
from .bank_accounts import router as bank_accounts_router

# ❌ NOT INTEGRATED (server.py has more complete logic)
# from .payments import router as payments_router  # Missing CFDI reversal logic
# from .reconciliations import router as reconciliations_router  # Critical data integrity

__all__ = [
    'auth_router',
    'companies_router',
    'categories_router',
    'vendors_router',
    'customers_router',
    'bank_accounts_router',
]

# MIGRATION SUMMARY:
# ===================
# Integrated: 6 routers (30 endpoints)
# Not Integrated: 2 routers (payments, reconciliations)
# server.py reduced: 8,630 -> 8,122 lines (~508 lines removed)
#
# Next steps:
# - Update payments.py with CFDI reversal logic, then integrate
# - Update reconciliations.py with full data integrity logic, then integrate
# - Create new modules: cfdi, fx_rates, bank_transactions, belvo
