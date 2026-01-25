# Server.py Refactoring Plan

## Current State (January 25, 2026)
- **server.py**: 8,122 lines (reduced from 8,630)
- **routes/*.py**: 8 files, 6 integrated
- **Lines removed**: ~508 lines

## Migration Status

### ✅ INTEGRATED ROUTERS (6)
| Module | File | Endpoints | Status |
|--------|------|-----------|--------|
| Auth | routes/auth.py | 7 | ✅ Integrated |
| Companies | routes/companies.py | 4 | ✅ Integrated |
| Categories | routes/categories.py | 6 | ✅ Integrated |
| Vendors | routes/vendors.py | 4 | ✅ Integrated |
| Customers | routes/customers.py | 4 | ✅ Integrated |
| Bank Accounts | routes/bank_accounts.py | 5 | ✅ Integrated |

**Total endpoints moved to modular routers: 30**

### ❌ NOT INTEGRATED (2)
| Module | File | Reason |
|--------|------|--------|
| Payments | routes/payments.py | server.py has CFDI reversal logic that modules don't have |
| Reconciliations | routes/reconciliations.py | Critical data integrity logic, too risky to migrate |

### ❌ NOT CREATED YET
- cfdi.py (~10 endpoints)
- fx_rates.py (~10 endpoints)
- bank_transactions.py (~13 endpoints)
- belvo.py (~9 endpoints)
- reports.py (~5 endpoints)
- exports.py (~5 endpoints)
- advanced.py (AI/optimization)

## Endpoints Remaining in server.py: 97

## Key Decisions Made

1. **Payments router NOT integrated** - The server.py version correctly reverses CFDI monto_cobrado/monto_pagado when payments are deleted. The module version is simpler and would lose this functionality.

2. **Reconciliations router NOT integrated** - Too critical for data integrity. Multiple endpoints with complex duplicate-prevention logic and bank transaction updates.

3. **Categories, Vendors, Customers fully migrated** - These are simple CRUD operations with no complex business logic dependencies.

4. **Bank accounts summary preserved** - The module has complete logic including historical FX rate lookups.

## Testing Performed
- All 6 integrated routers tested via curl
- Login/auth flow verified
- Companies CRUD verified
- Categories CRUD verified
- Vendors/Customers CRUD verified
- Bank accounts + summary verified
- Frontend dashboard loads correctly

## Next Steps
1. Create new route modules for cfdi, fx_rates, bank_transactions
2. Update payments module to include CFDI reversal logic
3. Update reconciliations module with full data integrity logic
4. Gradually integrate remaining modules
