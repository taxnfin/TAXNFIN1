# Server.py Refactoring Plan

## Current State
- **server.py**: 8630+ lines (main monolithic file)
- **routes/*.py**: 8 files created with partial endpoint extraction
- **Status**: Routes created but NOT integrated - server.py handles all requests

## Migration Strategy

### Phase 1: Preparation (DONE)
- [x] Create directory structure (`routes/`, `services/`, `models/`, `core/`)
- [x] Extract models to `models/*.py`
- [x] Create route files with endpoint logic
- [x] Document migration status

### Phase 2: Integration (IN PROGRESS)
For each router module:
1. Test router independently
2. Include router in `api_router`
3. Comment out duplicate endpoint in `server.py`
4. Test full application
5. Delete commented code after verification

### Phase 3: Cleanup (PENDING)
- Remove all duplicate code from `server.py`
- Update imports to use modular structure
- Add comprehensive tests

## Route Modules Status

| Module | File | Endpoints | Status |
|--------|------|-----------|--------|
| Auth | routes/auth.py | 5 | Created, 2 missing (callback, verify) |
| Companies | routes/companies.py | 4 | Created |
| Bank Accounts | routes/bank_accounts.py | 5 | Created |
| Vendors | routes/vendors.py | 4 | Created |
| Customers | routes/customers.py | 4 | Created |
| Categories | routes/categories.py | 6 | Created |
| Payments | routes/payments.py | 6 | Created, ~5 missing |
| Reconciliations | routes/reconciliations.py | 5 | Created, ~3 missing |
| **CFDI** | - | ~10 | **NOT CREATED** |
| **FX Rates** | - | ~10 | **NOT CREATED** |
| **Bank Transactions** | - | ~13 | **NOT CREATED** |
| **Belvo** | - | ~9 | **NOT CREATED** |
| **Reports/Dashboard** | - | ~3 | **NOT CREATED** |
| **Exports** | - | ~5 | **NOT CREATED** |
| **Advanced (AI/Optim)** | - | ~10 | **NOT CREATED** |

## Dependencies Map

```
server.py dependencies:
├── core/
│   ├── database.py (db connection) ✅
│   ├── auth.py (JWT, password) ✅
│   └── config.py (settings) ✅
├── services/
│   ├── audit.py (audit_log) ✅
│   ├── fx.py (get_fx_rate_by_date) ✅
│   ├── cashflow.py (initialize_cashflow) ✅
│   └── cfdi_parser.py (XML parsing) ✅
├── External services (still in server.py):
│   ├── forex_service.py
│   ├── fx_scheduler.py
│   ├── ai_categorization_service.py
│   ├── auth0_service.py
│   └── genetic_optimizer.py
```

## Key Functions to Extract

These functions in server.py are used by multiple endpoints and should be in services:

1. `get_fx_rate_by_date()` - Line ~7300 → services/fx.py
2. `audit_log()` - Already in services/audit.py
3. `get_active_company_id()` - Line ~780 → core/auth.py
4. `parse_cfdi_xml()` - Already in services/cfdi_parser.py

## Testing Strategy

Before removing any code from server.py:
1. Create test file for the module
2. Run pytest to verify endpoint behavior
3. Test with frontend to ensure full integration
4. Only then remove duplicate from server.py

## Rollback Plan

If issues arise after integration:
1. Comment out router include in server.py
2. Uncomment the original endpoints
3. Restart server
4. Investigate and fix router issues
