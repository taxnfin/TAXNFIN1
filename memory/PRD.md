# TaxnFin Cashflow - Product Requirements Document

## Original Problem Statement
Build a backend-first, API-driven SaaS application called "TaxnFin Cashflow" - a fintech-level cash flow management engine designed for enterprise clients in Mexico.

### User's Initial Request
- **Stack Requested**: NestJS, PostgreSQL, Prisma
- **Stack Approved**: FastAPI (Python), MongoDB, React (due to platform constraints)

### Core Requirements
1. **13-week rolling cash flow management**
2. **SAT (CFDI) electronic invoicing integration**
3. **Real bank transaction reconciliation**
4. **Multi-currency support (MXN primary)**
5. **Predictive analysis and forecasting**
6. **Virtual CFO with genetic algorithms for automatic optimization**
7. **Categorization system for financial organization and DIOT reporting**

---

## What's Been Implemented

### Phase 1: Core Application ✅
- **Date**: January 2026
- **Backend**: FastAPI with MongoDB integration
- **Authentication**: JWT-based auth with login/register
- **Core Models**: Company, User, BankAccount, Transaction, CashFlowWeek, Vendor, Customer
- **CRUD APIs**: All entities have full CRUD operations
- **Frontend**: React with TailwindCSS, Shadcn UI components

### Phase 2: Dashboard & Reports ✅
- **Dashboard**: Executive summary with KPIs (transactions, CFDIs, reconciliations)
- **13-Week Cashflow Chart**: Visual representation of projected vs actual cash flow
- **Reports API**: `/api/reports/dashboard` endpoint

### Phase 3: Advanced Features ✅
- **Predictive Analysis**: ML-based forecasting using scikit-learn
- **Auto-Reconciliation**: Intelligent matching of bank transactions
- **Alert System**: Configurable alerts (Twilio integration available)
- **Scenario Modeling**: "What-if" analysis for financial planning
- **Accounting Exports**: COI, XML Fiscal (SAT), Alegra formats

### Phase 4: Virtual CFO with Genetic Algorithms ✅
- **Date**: January 17, 2026
- **Feature**: Automatic cash flow optimization using DEAP genetic algorithms
- **Endpoint**: `/api/optimize/genetic`
- **UI**: Modal dialog with configuration options (generations, population, constraints)
- **Results**: Shows improvement in net flow, suggested modifications, crisis weeks resolved

### Phase 5: Multi-Company & Multi-Currency ✅
- **Date**: January 17, 2026
- **Company Selector**: UI dropdown to switch between companies
- **Data Segregation**: X-Company-ID header for all API calls
- **FX Rates Module**: Manage currency exchange rates (MXN, USD, EUR)
- **Currency Converter**: View all financial data in selected currency

### Phase 6: Categorization System & DIOT Export ✅
- **Date**: January 18, 2026
- **Categories CRUD**: Create, list, update, delete categories (ingreso/egreso)
- **Subcategories**: Nested categorization for detailed reporting
- **CFDI Categorization**: Assign categories to CFDIs
- **Reconciliation Status**: Visible state (pendiente/conciliado/no_conciliable)
- **Filter CFDIs**: By category and reconciliation status
- **DIOT Export**: CSV export for tax declarations
- **Bank Statement Template**: Excel template for importing statements
- **Global Exception Handler**: Standardized error responses

### Phase 7: AI-Powered Categorization ✅
- **Date**: January 18, 2026
- **Technology**: OpenAI GPT-5.2 via Emergent LLM Key
- **Auto-Categorization on Upload**: CFDIs are automatically categorized when uploaded (if confidence ≥70%)
- **Single CFDI**: Click sparkle icon to get AI suggestion for individual CFDI
- **Batch Categorization**: "Categorizar con IA" button analyzes all uncategorized CFDIs
- **Confidence Scores**: AI returns 0-100% confidence with reasoning
- **Apply Suggestions**: Review and apply suggestions individually or in batch
- **Smart Analysis**: AI considers RFC, tipo de comprobante, monto, and available categories
- **Model Updates**: Added category_id, subcategory_id, estado_conciliacion to CFDI model

### Phase 8: Customer/Vendor Association ✅
- **Date**: January 18, 2026
- **CFDI Customer Link**: CFDIs de tipo "ingreso" pueden asociarse con un Cliente
- **CFDI Vendor Link**: CFDIs de tipo "egreso" pueden asociarse con un Proveedor  
- **Transaction Fields**: Transactions now include category_id, subcategory_id, customer_id, vendor_id
- **Visual Indicators**: 👤 for customers (blue), 🏢 for vendors (orange) in tables
- **Category/Tercero Column**: New column in both CFDI and Transactions showing category and associated party
- **Form Updates**: Transaction form now includes selectors for category, subcategory, and customer/vendor based on type

### Phase 9: Enhanced Features ✅
- **Date**: January 18, 2026
- **Auto-Link by RFC**: When uploading CFDI, system auto-detects customer/vendor by RFC match
- **New RFC Detection**: Prompts user to create customer/vendor when unknown RFC is detected
- **Quick Party Creation**: POST /cfdi/{id}/create-party endpoint creates and links in one step
- **Dashboard Saldo Inicial**: Shows sum of bank account initial balances CONVERTED TO MXN
- **Multi-Currency Conversion**: Bank accounts in USD/EUR are converted using FX rates
- **Dashboard Saldo Final Proyectado**: Shows projected balance at week 13
- **Cascading Balances**: Each week's saldo_inicial = previous week's saldo_final
- **Vendor Import Template**: Excel template for bulk vendor import
- **Customer Import Template**: Excel template for bulk customer import
- **Bulk Import**: POST /vendors/import and /customers/import endpoints
- **Empty State UI**: Shows helpful actions when no vendors/customers exist

### Phase 10: Advanced Dashboard ✅
- **Date**: January 18, 2026
- **Currency Selector**: Dashboard supports 8 currencies with real-time conversion:
  - MXN - Peso Mexicano ($)
  - USD - Dólar USA ($)
  - EUR - Euro (€)
  - GBP - Libra Esterlina (£)
  - JPY - Yen Japonés (¥)
  - CHF - Franco Suizo (Fr)
  - CAD - Dólar Canadiense (C$)
  - CNY - Yuan Chino (¥)
- **Bank Account Filter**: Filter dashboard data by specific bank account or view all
- **Date Range Filter**: Custom date picker with quick buttons (1S, 1M, 3M, 6M, 1A, 13S)
- **Real-Time FX Rates**: 
  - **Banxico API Integration**: Official Mexican exchange rates (USD, EUR, GBP, JPY, CAD)
  - **Open Exchange Rates**: Complementary rates (CHF, CNY)
  - **"Actualizar Tasas" button**: One-click sync from official sources
  - **Rate display**: Shows all current rates after sync
  - **Automatic Daily Sync**: APScheduler runs at 9:00 AM and 1:00 PM Mexico City time
  - **Visual Scheduler Status**: Shows "Auto-sync activo" with next sync time
  - **New files**: `/app/backend/forex_service.py`, `/app/backend/fx_scheduler.py`
  - **New endpoints**: `POST /api/fx-rates/sync`, `GET /api/fx-rates/scheduler-status`
- **Enhanced KPIs**: 
  - Saldo Inicial (consolidated from all bank accounts with currency conversion)
  - Saldo Final Proyectado (S13)
  - Flujo Promedio (4 semanas) with trend indicator
- **13-Week Cashflow Chart**: ComposedChart with Ingresos, Egresos bars and Saldo line
- **Variance Chart**: BarChart showing weekly variance vs previous week
- **Cash Pooling Section**: Shows currency breakdown with totals by currency
- **Account Details Section**: Shows bank accounts with risk indicators (ocioso, bajo saldo)
- **Risk Indicators**: liquidez_critica, tendencia_negativa, saldos_ociosos, cuentas_bajo_saldo, semanas_con_deficit
- **Secondary KPIs**: Transacciones, CFDIs, Conciliaciones, Clientes, Proveedores
- **Refresh Button**: Manual data reload functionality
- **Tests**: 18/18 backend tests passed (test_dashboard_advanced.py)

### Phase 11: Auth0 Integration ✅
- **Date**: January 18, 2026
- **Auth0 Configuration**: 
  - Domain: dev-87116dk850gry8mn.us.auth0.com
  - Audience: https://api.taxnfin.com/cashflow
- **New file**: `/app/backend/auth0_service.py`
- **Backend Endpoints**:
  - `GET /api/auth/auth0/config` - Get Auth0 configuration for frontend
  - `GET /api/auth/auth0/login-url` - Generate Auth0 login redirect URL
  - `POST /api/auth/auth0/callback` - Exchange code for tokens and create/update user
  - `POST /api/auth/auth0/verify` - Verify Auth0 token
- **Frontend**:
  - "Iniciar con Cuenta Empresarial" button on Login page
  - Blue/indigo gradient styling
  - Separator "o continúa con email" for traditional login
- **Features**:
  - JWKS caching for performance
  - Hybrid authentication (Auth0 + internal JWT)
  - Auto-provisioning of users from Auth0
  - M2M token support for API integrations

### Phase 12: FX Rate Alerts ✅
- **Date**: January 18, 2026
- **Alert Banner**: Visual banner in dashboard for rate anomalies
- **Threshold**: >2% change triggers warning, >5% triggers critical alert
- **New endpoint**: `GET /api/fx-rates/alerts`
- **Visual indicators**: 
  - Red banner for critical alerts
  - Amber banner for warnings
  - Trend icons (up/down) for each currency
  - Dismissible with X button

### Phase 13: Bank Account Management ✅
- **Date**: January 18, 2026
- **Edit Bank Accounts**: Modal with pre-filled fields, "Guardar Cambios" button
- **Delete Bank Accounts**: Confirmation dialog with warning message
- **UI Updates**:
  - New "Acciones" column in bank accounts table
  - Pencil icon (blue) for edit
  - Trash icon (red) for delete
  - Alert dialog for delete confirmation
- **Endpoints used**: `PUT /api/bank-accounts/{id}`, `DELETE /api/bank-accounts/{id}`

---

## Current Architecture

```
/app/
├── backend/
│   ├── server.py               # Main FastAPI app (monolithic)
│   ├── advanced_services.py    # Predictive analysis, alerts
│   ├── integration_services.py # SAT scraping (mocked), Bank APIs (mocked)
│   ├── scenario_service.py     # What-if analysis
│   ├── export_service.py       # Accounting format exports
│   ├── genetic_optimizer.py    # Genetic algorithm optimization
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.js
│       ├── api/axios.js        # Axios with X-Company-ID interceptor
│       ├── pages/
│       │   ├── Login.js
│       │   ├── Dashboard.js
│       │   ├── Transactions.js
│       │   ├── CFDIModule.js       # With categorization & filters
│       │   ├── BankModule.js
│       │   ├── PaymentsModule.js
│       │   ├── FXRatesModule.js
│       │   ├── CategoriesModule.js # NEW
│       │   ├── AdvancedFeatures.js
│       │   └── ...
│       └── components/
│           └── Layout.js       # Navigation with Categories link
└── tests/
    ├── test_backend_api.py
    └── test_categories_diot.py # NEW - 18 tests
```

---

## Test Status
- **Backend Tests**: 51/51 passed (100%)
  - Original tests: 15/15
  - Categories/DIOT tests: 18/18
  - Dashboard Advanced tests: 18/18
- **Frontend Tests**: All UI flows verified working
- **Last Test Date**: January 18, 2026

---

## Known Limitations / Mocked Features

### MOCKED - Not Connected to Real Services
1. **Bank API Integrations** (BBVA, Santander, Banorte, Bajío, Amex) - Placeholders only
2. **SAT Scraping** - Requires selenium, currently returning mock data

---

## Latest Updates (January 20, 2026)

### Completed in This Session ✅

**Selector de Moneda en Proyecciones**
1. Selector dropdown MXN/USD/EUR en la barra de herramientas
2. Conversión automática usando tipos de cambio actuales
3. Muestra el TC usado en el subtítulo cuando no es MXN
4. Todos los montos (saldo, ingresos, egresos) convertidos

**Tabla de Tipos de Cambio Históricos - ARREGLADA**
1. Muestra 7 registros de Banxico y OpenExchange
2. Columnas: Fecha, Moneda, Tipo de Cambio (MXN), Fuente
3. Fuentes coloreadas: banxico (azul), openexchange (naranja)
4. Normalización de campos entre formatos antiguos y nuevos

**Scheduler de Tipos de Cambio - VERIFICADO**
1. Scheduler activo con APScheduler
2. Sincronización matutina: 9:00 AM México
3. Sincronización vespertina: 1:00 PM México (FIX oficial)
4. Status endpoint: `/api/fx-rates/scheduler-status`

**Tipos de Cambio Históricos**
1. Almacenamiento por fecha en `fecha_vigencia`
2. Helper `get_fx_rate_by_date()` para TC histórico
3. Fecha en saldo de bancos para conversión correcta

**Categorías y Subcategorías en Proyecciones**
1. Categorías expandibles (Cobranza, Proveedores, etc.)
2. Subcategorías indentadas con └
3. Click para expandir/colapsar

---

## Backlog (P0 - P2)

### P0 - Critical (None currently)
All critical features implemented and tested.

### P1 - High Priority
1. **Refactor `server.py`** - Split into modular structure:
   - `/app/backend/routes/` - API endpoints
   - `/app/backend/models/` - Pydantic models
   - `/app/backend/services/` - Business logic
   - `/app/backend/core/` - Auth, DB, config
2. **Notificaciones automáticas** - Alertas por email/SMS para vencimientos

### P2 - Medium Priority
1. **Restaurar datos de Ortech** - Si el usuario tiene XMLs
2. **Secure Bank Connections** - Integrate with Plaid or Fintoc
3. **Email notifications** - Add email alerts
4. **User management UI** - Admin panel

### P3 - Nice to Have
1. **ISO 27001 Compliance**
2. **Mobile-responsive improvements**
3. **Dark mode theme**
4. **Export to Excel with charts**
5. **API rate limiting**

---

## Credentials for Testing
- **Email**: admin@demo.com
- **Password**: admin123
- **Role**: admin
- **Company**: Empresa Demo SA de CV

---

## API Endpoints Reference

### Authentication
- `POST /api/auth/login` - Login
- `POST /api/auth/register` - Register new user
- `GET /api/auth/me` - Get current user

### Core Resources
- `POST/GET /api/companies` - Companies CRUD
- `POST/GET /api/bank-accounts` - Bank accounts CRUD
- `POST/GET /api/transactions` - Transactions CRUD
- `GET /api/cashflow/weeks` - Get 13-week cashflow

### CFDI
- `POST /api/cfdi/upload` - Upload XML files
- `GET /api/cfdi` - List CFDIs
- `DELETE /api/cfdi/{id}` - Delete CFDI
- `PUT /api/cfdi/{id}/categorize` - Assign category to CFDI
- `PUT /api/cfdi/{id}/reconciliation-status` - Update reconciliation status
- `POST /api/cfdi/{id}/ai-categorize` - AI suggestion for single CFDI
- `POST /api/cfdi/ai-categorize-batch` - AI categorize all uncategorized CFDIs

### Categories
- `GET /api/categories` - List categories (with subcategories)
- `GET /api/categories?tipo=ingreso|egreso` - Filter by type
- `POST /api/categories` - Create category
- `PUT /api/categories/{id}` - Update category
- `DELETE /api/categories/{id}` - Delete category (soft delete)
- `POST /api/subcategories` - Create subcategory
- `DELETE /api/subcategories/{id}` - Delete subcategory

### Exports
- `GET /api/export/diot` - Export DIOT CSV
- `GET /api/bank-transactions/template` - Download bank statement template
- `GET /api/export/coi` - Export to COI format
- `GET /api/export/xml-fiscal` - Export to XML Fiscal

### Reports
- `GET /api/reports/dashboard` - Dashboard KPIs and weekly data

### Advanced Features
- `GET /api/ai/predictive-analysis` - Run predictive analysis
- `POST /api/reconciliation/auto-reconcile-batch` - Auto-reconcile transactions
- `POST /api/alerts/check-and-send` - Check and send alerts
- `POST /api/scenarios/create` - Create scenario
- `GET /api/scenarios` - List scenarios

### Genetic Optimization
- `POST /api/optimize/genetic` - Run genetic optimization
- `GET /api/optimize/history` - Get optimization history
- `POST /api/optimize/apply/{id}` - Apply optimization solution

---

## Changelog

### January 18, 2026 (Session 2)
- Implemented AI-powered categorization using GPT-5.2 via Emergent LLM Key
- Created `/app/backend/ai_categorization_service.py` for AI integration
- Added `POST /api/cfdi/{id}/ai-categorize` endpoint for single CFDI
- Added `POST /api/cfdi/ai-categorize-batch` endpoint for batch processing
- Updated CFDIModule.js with "Categorizar con IA" button and sparkle icons
- AI analyzes RFC, tipo, monto and suggests category with confidence score
- Results dialog shows all suggestions with reasoning and "Aplicar" buttons

### January 18, 2026 (Session 1)
- Implemented Categories/Subcategories CRUD system
- Added CFDI categorization feature
- Added CFDI reconciliation status (visible and editable)
- Implemented filters by category and reconciliation status on CFDI page
- Added DIOT CSV export endpoint with date filters
- Added bank statement Excel template download
- Implemented global exception handler for standardized error responses
- Created CategoriesModule.js frontend page
- Updated CFDIModule.js with categorization, filters, and reconciliation status
- Added Categories link to navigation sidebar
- All tests passing (18/18 new tests)

### January 17, 2026
- Fixed critical login bugs (SyntaxError, password hashing)
- Implemented multi-company data segregation (X-Company-ID header)
- Built FX Rates module with currency conversion
- Enhanced CFDI upload (multi-file, progress tracking)
- Fixed Virtual CFO genetic algorithm (timezone, numpy serialization)
- Created Payments History module

---

## DB Schema Reference

### categories
```json
{
  "id": "uuid",
  "company_id": "uuid",
  "nombre": "string",
  "tipo": "ingreso|egreso",
  "color": "#hex",
  "icono": "string",
  "activo": true,
  "created_at": "datetime"
}
```

### subcategories
```json
{
  "id": "uuid",
  "company_id": "uuid",
  "category_id": "uuid",
  "nombre": "string",
  "activo": true,
  "created_at": "datetime"
}
```

### cfdis (updated fields)
```json
{
  "category_id": "uuid|null",
  "subcategory_id": "uuid|null",
  "estado_conciliacion": "pendiente|conciliado|no_conciliable"
}
```
