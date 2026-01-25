# Server.py Refactoring Plan

## Current State (January 25, 2026 - PHASE 2 COMPLETE)
- **server.py**: 7,402 lines (reduced from 8,630 - **14% reduction**)
- **routes/*.py**: 8 files, ALL integrated
- **Lines removed**: ~1,228 lines
- **Endpoints moved to modular routers**: 43

## Migration Status - ALL 8 ROUTERS INTEGRATED ✅

### ✅ FULLY INTEGRATED ROUTERS
| Module | File | Endpoints | Features |
|--------|------|-----------|----------|
| Auth | routes/auth.py | 7 | Login, Register, Me, Auth0 integration |
| Companies | routes/companies.py | 4 | CRUD + cashflow initialization |
| Categories | routes/categories.py | 6 | Categories + Subcategories CRUD |
| Vendors | routes/vendors.py | 4 | CRUD |
| Customers | routes/customers.py | 4 | CRUD |
| Bank Accounts | routes/bank_accounts.py | 5 | CRUD + Summary with FX |
| Payments | routes/payments.py | 6 | CRUD + CFDI reversal logic |
| Reconciliations | routes/reconciliations.py | 7 | CRUD + Summary + mark-without-uuid |

**Total: 43 endpoints in modular architecture**

### ❌ MODULES NOT YET CREATED
- cfdi.py (~10 endpoints)
- fx_rates.py (~10 endpoints)  
- bank_transactions.py (~13 endpoints)
- belvo.py (~9 endpoints)
- reports.py (~5 endpoints)
- exports.py (~5 endpoints)
- advanced.py (AI/optimization)

## Endpoints Remaining in server.py: ~55

## Key Features Preserved

### Payments Module (routes/payments.py)
- ✅ Automatic FX rate capture for non-MXN currencies
- ✅ CFDI amount updates when payment is created (monto_cobrado/monto_pagado)
- ✅ CFDI amount reversal when payment is deleted
- ✅ CFDI amount adjustment when payment is edited
- ✅ Bulk delete with full CFDI reset

### Reconciliations Module (routes/reconciliations.py)
- ✅ Duplicate prevention (same bank_transaction + cfdi)
- ✅ Automatic payment creation on reconciliation
- ✅ CFDI estado_conciliacion update
- ✅ Historical FX rate capture
- ✅ mark-without-uuid for bank fees and non-invoice expenses
- ✅ Summary by reconciliation type (con_uuid, sin_uuid, no_relacionado)
- ✅ Full cleanup on delete (payment, bank transaction status, CFDI status)

## Testing Performed
- All 8 routers tested via curl
- Login/auth flow verified
- Full CRUD operations verified for all modules
- Reconciliation summary verified
- Frontend dashboard loads correctly

## Next Steps (Phase 3)
1. Create cfdi.py module
2. Create fx_rates.py module
3. Create bank_transactions.py module
4. Continue reducing server.py
