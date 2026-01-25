# Routes module - API endpoints organized by domain
# During refactoring, routes are being migrated gradually from server.py
# These routers can be included in the main api_router for modular architecture

from fastapi import APIRouter

# Import individual routers - These are ready to be integrated
# Note: server.py still has duplicate endpoints that need to be removed
# after testing the modular routes work correctly

# from .auth import router as auth_router
# from .companies import router as companies_router
# from .bank_accounts import router as bank_accounts_router
# from .vendors import router as vendors_router
# from .customers import router as customers_router
# from .categories import router as categories_router
# from .payments import router as payments_router
# from .reconciliations import router as reconciliations_router

# Routers ready for integration (commented out until server.py duplicates are removed):
# - auth_router: /auth/* (register, login, me, auth0)
# - companies_router: /companies/* (CRUD)
# - bank_accounts_router: /bank-accounts/* (CRUD, summary)
# - vendors_router: /vendors/* (CRUD)
# - customers_router: /customers/* (CRUD)
# - categories_router: /categories/* and /subcategories/* (CRUD)
# - payments_router: /payments/* (CRUD, summary, complete, bulk delete)
# - reconciliations_router: /reconciliations/* (CRUD, summary, mark-without-uuid)

# MIGRATION STATUS:
# ==================
# The following modules have been extracted but server.py still handles all routes:
#
# ✅ Created (routes/*.py exists):
#   - auth.py (5 endpoints)
#   - companies.py (4 endpoints)
#   - bank_accounts.py (5 endpoints)
#   - vendors.py (4 endpoints)
#   - customers.py (4 endpoints)
#   - categories.py (6 endpoints)
#   - payments.py (6 endpoints)
#   - reconciliations.py (5 endpoints)
#
# ❌ Pending creation:
#   - cfdi.py (~10 endpoints)
#   - fx_rates.py (~10 endpoints)
#   - bank_transactions.py (~13 endpoints)
#   - belvo.py (~9 endpoints)
#   - manual_projections.py (4 endpoints)
#   - transactions.py (4 endpoints)
#   - reports.py (~3 endpoints)
#   - exports.py (~5 endpoints)
#   - advanced.py (AI, optimization, scenarios)
#
# NEXT STEPS:
# 1. Test each router independently
# 2. Include working routers in api_router
# 3. Remove duplicate endpoints from server.py
# 4. Continue extracting remaining endpoints

__all__ = []
