# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**TaxnFin Cashflow** is a fintech SaaS backend-first cash flow management system for Mexican enterprises with SAT (CFDI) integration. FastAPI + MongoDB backend with a React frontend, supporting multi-company, multi-currency operations.

### Core Domain
- 13-week rolling cash flow forecasting with real vs. projected separation
- Electronic invoice (CFDI/SAT) management with XML parsing and AI categorization
- Bank reconciliation with multi-source integration (Belvo, Alegra, Contalink, manual CSV/Excel)
- Multi-currency support with real-time FX rates (Banxico, OpenExchangeRates APIs)
- Financial reporting with scenario modeling, genetic algorithm optimization, and PDF generation
- SAT FIEL (e.firma) integration for automated CFDI download from SAT web services

## Architecture at a Glance

### Tech Stack
- Backend: FastAPI (Python), Motor (async MongoDB driver), `core.database.db` singleton
- Database: MongoDB (`taxnfin_cashflow` database, async operations only)
- Frontend: React 18, React Router, Tailwind CSS, Shadcn UI, Recharts
- Authentication: JWT (7-day expiration), optional Auth0 integration
- Key Services: APScheduler (FX sync + integration sync every 6h), DEAP (genetic optimization), scikit-learn (ML forecasting)

### Directory Structure
```
/backend/
  ├── server.py              # FastAPI app initialization, all router registration
  ├── core/                  # config.py, auth.py, database.py (db singleton)
  ├── models/                # Pydantic models (enums, company, user, transaction, cfdi, bank, etc.)
  ├── routes/                # ~40 API endpoint modules (all registered in server.py)
  ├── services/              # Business logic (cashflow, cfdi_parser, fx, audit, pdf, alegra, contalink, etc.)
  ├── modules/               # SAT/CFDI specialist modules (cfdi_sat.py, sat_fiel.py)
  ├── requirements.txt
  └── tests/

/frontend/
  ├── src/
  │   ├── pages/            # Page components (~27 pages)
  │   ├── components/       # Reusable UI components
  │   ├── api/              # Axios client
  │   ├── hooks/            # React hooks
  │   ├── utils/            # Helpers
  │   └── data/             # Constants
```

### Key Models & Data Flow

**Company-centered Multi-tenancy**: All entities carry `company_id`. Users belong to multiple companies via `company_ids` list. `X-Company-ID` header selects the active company.

**CashFlowWeek**: 13-week rolling window (`saldo_inicial`, `ingresos`, `egresos`, `saldo_final`). Transactions link to `cashflow_week_id`.

**Transaction**: `tipo_transaccion` (ingreso/egreso), `es_real` (reconciled), `es_proyeccion` (forecast), `origen` (banco/csv/manual), links to vendor/customer/category/bank_account.

**CFDI**: Parsed from XML v4.0, `estado_conciliacion` (pendiente/conciliado/no_conciliable), AI auto-categorization (OpenAI, confidence ≥ 70%).

**User & Authentication**: Roles — admin (full), cfo (operational), viewer (read-only). Self-registration creates new company (admin); joining existing company assigns viewer.

### Backend Request Flow
1. CORS middleware
2. Auth: `get_current_user()` validates JWT
3. Company: `get_active_company_id(request, current_user)` reads `X-Company-ID` header
4. Route handler → async MongoDB queries
5. Audit logging on CREATE/UPDATE/DELETE
6. Response with `_id` excluded

### Critical Services & Integrations

**Cashflow Engine** (`services/cashflow.py`): 13-week rolling window, balance cascading, `saldo_inicial` propagation.

**CFDI Parser** (`services/cfdi_parser.py`): Extracts XML v4.0 data (UUID, RFCs, amounts, taxes).

**SAT FIEL** (`modules/sat_fiel.py`): `FIELManager` class uses `cfdiclient` library to authenticate with SAT web services using `.cer`/`.key` e.firma files and download CFDIs in bulk.

**AI Categorization** (`routes/cfdi_operations.py`): Auto-categorizes CFDIs via OpenAI if confidence ≥ 70%.

**Cashflow Sync** (`routes/cashflow_sync_service.py`): Maps transactions from connected ERPs (Contalink ✅, Alegra ✅) to the 13-week cashflow model. Includes a default category catalog (`DEFAULT_CATEGORIES` with codes ING-001…ING-099, EGR-001…EGR-099).

**FX Scheduler** (`fx_scheduler.py`): Daily at 9 AM & 1 PM Mexico City time (Banxico + OpenExchangeRates).

**Integration Scheduler** (`services/integration_scheduler.py`): Syncs connected ERPs every 6 hours on startup.

**Genetic Optimizer** (`genetic_optimizer.py`): Virtual CFO feature using DEAP for 13-week optimization.

**Contalink Financial** (`routes/contalink_financial.py`): Imports Balance General and Estado de Resultados from Contalink Excel exports; auto-detects sheet type.

**Treasury Module** (`routes/treasury.py`): `/treasury/dashboard` — actionable alerts, recommendations, treasury calendar, concentration KPIs, working capital intelligence.

## Common Development Commands

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --reload --host 0.0.0.0 --port 8001
# API docs: http://localhost:8001/docs
```

### Backend Testing
```bash
pytest tests/ -v
pytest tests/test_dashboard_advanced.py::test_dashboard_with_conversion -v
pytest -k "cashflow" -v
pytest --cov=. tests/
```

### Frontend
```bash
cd frontend
npm install
npm start        # http://localhost:3000
npm run build    # DISABLE_ESLINT_PLUGIN=true craco build (uses craco, not react-scripts)
```

### Linting
```bash
black . && flake8 . && isort .
```

## Important Patterns & Conventions

### Database Access
`db` is a module-level singleton — import directly, do not inject as a FastAPI dependency:
```python
from core.database import db

doc = await db.transactions.find_one({"id": tid, "company_id": company_id}, {"_id": 0})
await db.transactions.insert_one(doc)
await db.transactions.update_one({"id": tid, "company_id": company_id}, {"$set": {...}})
```

### Route Signature Pattern
```python
from core.auth import get_current_user, get_active_company_id

@router.get("/my-endpoint")
async def my_endpoint(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    # company_id resolved inline, not as a dependency:
):
    company_id = await get_active_company_id(request, current_user)
    # current_user keys: id, email, role, company_ids
```

### Audit Logging
```python
from services.audit import audit_log

await audit_log(
    company_id=company_id,
    entidad="transactions",      # collection name
    entity_id=doc_id,
    accion="create",             # "create", "update", "delete"
    user_id=current_user["id"],
    datos_anteriores=None,       # old state (None for create)
    datos_nuevos=new_doc         # new state (None for delete)
)
```

### Create Pattern
```python
from datetime import datetime, timezone
import uuid

doc = {
    "id": str(uuid.uuid4()),
    "company_id": company_id,
    "created_at": datetime.now(timezone.utc),
}
await db.collection.insert_one(doc)
```

### Error Handling
```python
from fastapi import HTTPException

raise HTTPException(status_code=404, detail="Recurso no encontrado")
raise HTTPException(status_code=403, detail="No tienes acceso a esta empresa")
```

### Enums (`models/enums.py`)
```
TransactionType: ingreso, egreso
TransactionOrigin: banco, csv, manual
CFDIType: ingreso, egreso, pago, nota_credito
CFDIStatus: vigente, cancelado
UserRole: admin, cfo, viewer
ReconciliationStatus: pendiente, conciliado, no_conciliable
PaymentStatus: pendiente, completado, cancelado, vencido
PaymentMethod: transferencia, cheque, efectivo, tarjeta, domiciliacion, spei
```

### Naming Conventions
- Spanish field names: `concepto`, `monto`, `fecha_transaccion`, `estado_conciliacion`
- All timestamps: `datetime.now(timezone.utc)` — always timezone-aware
- MongoDB `_id` always excluded with `{"_id": 0}`

## Design System (Frontend)

"The Executive Suite" — cockpit-like control panel for CFOs. See `design_guidelines.json` for full specs.
- Typography: Manrope (headings), Public Sans (body), JetBrains Mono (financial data)
- Colors: Deep Obsidian `#0F172A`, Slate Mist `#F1F5F9`, Emerald Ledger `#10B981`, Audit Red `#EF4444`
- Layout: Bento grid KPIs, dense tables (py-2 px-3), fixed collapsible sidebar, sharp borders (rounded-sm)
- Every interactive element **must** have `data-testid` attribute

## Testing

Test credentials: `admin@demo.com` / `admin123` (see `memory/test_credentials.md`).
Tests must NOT write to the production MongoDB — use a test database or mocking.

Key test files: `test_dashboard_advanced.py`, `test_categories_diot.py`, `test_alegra_integration.py`, `test_financial_statements.py`, `test_ai_analysis_and_pdf.py`.

## Key Files Reference

| File | Purpose |
|------|---------|
| `server.py` | App setup, all router registration, startup schedulers |
| `core/config.py` | All settings (MongoDB, JWT, API keys) |
| `core/auth.py` | JWT creation/validation, `get_current_user`, `get_active_company_id` |
| `core/database.py` | `db` singleton (Motor async client) |
| `services/cashflow.py` | 13-week window logic, balance cascading |
| `services/cfdi_parser.py` | XML CFDI v4.0 parsing |
| `services/fx.py` | Currency conversion |
| `services/audit.py` | `audit_log()` — all mutation logging |
| `services/integration_scheduler.py` | ERP sync every 6h |
| `modules/sat_fiel.py` | `FIELManager` — SAT FIEL/e.firma authentication & bulk CFDI download |
| `modules/cfdi_sat.py` | SAT CFDI specialist processing |
| `routes/cashflow.py` | CashFlow weeks + transactions CRUD |
| `routes/cashflow_sync_service.py` | Multi-ERP → cashflow mapping, default category catalog |
| `routes/cfdi.py` | CFDI management |
| `routes/cfdi_operations.py` | AI auto-categorization |
| `routes/treasury.py` | Treasury dashboard: alerts, recommendations, working capital |
| `routes/contalink_financial.py` | Contalink Excel financial statement import |
| `routes/bank_import.py` | Bank statement import from Excel (cols: `fecha_movimiento`, `descripcion`, `monto`) |
| `routes/reports.py` | Dashboard data aggregation |
| `routes/exports.py` | COI, SAT, Alegra, Excel export |
| `genetic_optimizer.py` | Virtual CFO optimization (DEAP) |
| `fx_scheduler.py` | Automated FX rate sync (9 AM & 1 PM MX) |
| `design_guidelines.json` | Full UI/UX specifications |
| `memory/PRD.md` | Full product roadmap |

## X-Company-ID Header

Required for all multi-company operations:
```javascript
// Frontend: always set on axios instance
axios.defaults.headers.common['X-Company-ID'] = selectedCompanyId;
```
```python
# Backend: resolved via get_active_company_id(request, current_user)
# Falls back to user's primary company_id if header is absent
# Admins access any company; other roles must be in company_ids list
```

## Environment Variables

```
MONGO_URL=mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true
DB_NAME=taxnfin_cashflow
JWT_SECRET=your-secret-key-min-32-chars
BANXICO_TOKEN=your-banxico-api-token
OPEN_EXCHANGE_APP_ID=your-openexchangerates-key
BELVO_SECRET_ID=your-belvo-id
BELVO_SECRET_PASSWORD=your-belvo-password
BELVO_ENV=sandbox
AUTH0_DOMAIN=your-auth0-domain.auth0.com
AUTH0_CLIENT_ID=your-client-id
AUTH0_CLIENT_SECRET=your-client-secret
AUTH0_AUDIENCE=https://api.taxnfin.com/cashflow
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
SAT_ENCRYPTION_KEY=your-sat-encryption-key
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-token
STRIPE_SECRET_KEY=your-stripe-key
CONEKTA_SECRET_KEY=your-conekta-key
CORS_ORIGINS=http://localhost:3000  # comma-separated, defaults to *
```
