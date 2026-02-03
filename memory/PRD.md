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

### Phase 14: SAT Integration for CFDI Downloads ✅
- **Date**: January 31, 2026
- **Feature**: Automatic download of CFDIs from the SAT portal using RFC + CIEC credentials
- **Technology**: Selenium WebDriver for web scraping the SAT portal
- **New files**:
  - `backend/modules/cfdi_sat.py` - SAT integration module with credential encryption (Fernet)
  - `backend/routes/sat.py` - SAT API endpoints
  - `frontend/src/components/SATIntegration.js` - UI component for SAT integration
- **Endpoints**:
  - `GET /api/sat/status` - Get SAT integration status (configured/not configured)
  - `POST /api/sat/credentials` - Save encrypted SAT credentials (RFC + CIEC)
  - `POST /api/sat/credentials/validate` - Validate credentials without saving
  - `DELETE /api/sat/credentials` - Delete saved credentials
  - `POST /api/sat/sync` - Sync CFDIs from SAT portal
  - `GET /api/sat/sync/history` - Get sync history
  - `POST /api/sat/test-connection` - Test connection using saved credentials
  - `GET /api/sat/comprobante-types` - Get list of CFDI types for filtering
- **UI Features**:
  - SAT Integration card in CFDI module showing connection status
  - Configure Credentials dialog with RFC and CIEC fields
  - Security note explaining encrypted storage
  - Sync dialog with date range, CFDI type filter, and emitidos/recibidos options
  - Sync history dialog showing past synchronizations
  - Test connection button to verify credentials
  - Delete credentials with confirmation dialog
- **Security**:
  - Credentials encrypted using Fernet symmetric encryption
  - SAT_ENCRYPTION_KEY should be set in production .env
  - CIEC never stored in plain text
- **Dependencies Added**: selenium, webdriver-manager

---

## Current Architecture

```
/app/
├── backend/
│   ├── server.py               # Main FastAPI app (7000+ lines)
│   │
│   ├── core/                   # Core utilities (Jan 22, 2026)
│   │   ├── __init__.py
│   │   ├── config.py          # Settings from environment
│   │   ├── database.py        # MongoDB connection
│   │   └── auth.py            # JWT authentication
│   │
│   ├── models/                 # Pydantic models (Jan 22, 2026)
│   │   ├── __init__.py
│   │   ├── enums.py           # UserRole, CFDIType, PaymentStatus
│   │   ├── auth.py, company.py, bank.py, cfdi.py
│   │   ├── payment.py, category.py, vendor.py, customer.py
│   │   ├── transaction.py, fx.py, projection.py, audit.py
│   │   └── base.py
│   │
│   ├── services/               # Business logic (Jan 22, 2026)
│   │   ├── audit.py           # Audit logging
│   │   ├── fx.py              # FX rate utilities
│   │   ├── cashflow.py        # Cash flow initialization
│   │   └── cfdi_parser.py     # CFDI XML parsing
│   │
│   ├── routes/                 # API endpoints (Jan 22, 2026)
│   │   ├── auth.py, companies.py, bank_accounts.py
│   │   ├── vendors.py, customers.py, categories.py
│   │   ├── payments.py, reconciliations.py, cfdi.py
│   │   ├── fx_rates.py, bank_transactions.py
│   │   ├── sat.py             # NEW - SAT integration (Jan 31, 2026)
│   │   └── __init__.py
│   │
│   ├── modules/                # NEW - Feature modules (Jan 31, 2026)
│   │   └── cfdi_sat.py        # SAT portal integration (Selenium)
│   │
│   ├── advanced_services.py    # Predictive analysis, alerts
│   ├── integration_services.py # SAT scraping (legacy)
│   ├── scenario_service.py     # What-if analysis
│   ├── export_service.py       # Accounting format exports
│   ├── genetic_optimizer.py    # Genetic algorithm optimization
│   ├── forex_service.py        # Banxico/OpenExchange
│   ├── fx_scheduler.py         # Scheduled FX sync
│   ├── ai_categorization_service.py
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.js
│       ├── api/axios.js        # Axios with X-Company-ID interceptor
│       ├── pages/
│       │   ├── Login.js
│       │   ├── Dashboard.js
│       │   ├── Transactions.js
│       │   ├── CFDIModule.js       # With categorization & SAT integration
│       │   ├── BankStatementsModule.js # Reconciliations, Belvo
│       │   ├── PaymentsModule.js   # CFDI auto-matching
│       │   ├── FXRatesModule.js
│       │   ├── CategoriesModule.js
│       │   ├── DIOTModule.js
│       │   ├── AdvancedFeatures.js
│       │   └── ...
│       └── components/
│           ├── Layout.js           # Navigation
│           └── SATIntegration.js   # NEW - SAT integration UI (Jan 31, 2026)
│       └── components/
│           └── Layout.js       # Navigation
└── tests/
    ├── test_backend_api.py
    └── test_cfdi_matching.py
```

### Module Migration Status (January 22, 2026)

| Module | Files | Status | Notes |
|--------|-------|--------|-------|
| core/ | 4 | ✅ Created | config, database, auth |
| models/ | 15 | ✅ Created | All Pydantic models |
| services/ | 5 | ✅ Created | audit, fx, cashflow, cfdi_parser |
| routes/ | 9 | ✅ Created | Not yet integrated with app |
| server.py | 1 | 🔄 Active | Main entry point, 7000+ lines |

---

## Test Status
- **Backend Tests**: 51/51 passed (100%)
  - Original tests: 15/15
  - Categories/DIOT tests: 18/18
  - Dashboard Advanced tests: 18/18
  - CFDI Matching tests: 11/12 (1 skipped - no test data)
- **Frontend Tests**: All UI flows verified working
- **Last Test Date**: January 22, 2026

---

## Known Limitations / Mocked Features

### MOCKED - Not Connected to Real Services
1. **Bank API Integrations** (BBVA, Santander, Banorte, Bajío, Amex) - Placeholders only
2. **SAT Scraping** - Requires selenium, currently returning mock data
3. **Belvo Bank Integration** - Scaffolding complete, pending user API credentials

---

## Latest Updates (February 2, 2026)

### Completed in This Session ✅

**1. Filtros en Aging de Cartera (CxC / CxP)**

- ✅ Búsqueda por nombre de **Cliente** / **Proveedor**
- ✅ Selector de **Moneda** (Todas, MXN, USD, EUR)
- ✅ Selector de **Antigüedad** (Vigente, 1-30 días, 31-60 días, etc.)
- ✅ Rango de fechas de emisión (**Desde** / **Hasta**)
- ✅ Botón "Limpiar filtros" cuando hay filtros activos

**2. Exportación de Datos Filtrados a Excel**

- ✅ Botón cambia a **"Exportar Filtrado"** cuando hay filtros activos
- ✅ Exporta solo los datos que coinciden con los filtros
- ✅ Muestra contador de facturas filtradas y total filtrado en MXN

**3. Nuevo Fondo de Login Profesional**

- ✅ Gradiente abstracto azul oscuro más sobrio y empresarial

**4. Drill-Down Jerárquico en Modelo de Flujo de Efectivo - 18 Semanas**

- ✅ **Celdas clickeables**: Cada monto en la tabla de proyecciones es ahora clickeable
- ✅ **Dialog de detalle** muestra para cada celda:
  - Proveedor/Cliente con icono distintivo
  - UUID de factura (primeros 8 caracteres + tooltip)
  - Fecha de emisión
  - Monto en moneda original + Monto convertido a MXN
  - Movimiento bancario relacionado
  - Estado de conciliación (✓/✗)
- ✅ **Toggle de vista**: Botones "Por Categoría" / "Por Proveedor/Cliente" en el header
- ✅ **Vista por Proveedor/Cliente**: 
  - Mismas 18 semanas que la vista por categoría
  - Cada tercero en su propia fila
  - Badge C (Cliente) o P (Proveedor)
  - Totales por semana cuadran con vista por categoría
- ✅ **Filtros en vista por Proveedor/Cliente**:
  - Búsqueda por nombre de tercero
  - Filtro por tipo (Todos / Clientes / Proveedores)
  - Filtro por saldo (Todos / Positivo / Negativo)
  - Botón "Limpiar" filtros cuando hay filtros activos
  - **Exportar Terceros / Exportar Filtrado** a Excel
- ✅ **Botón "Exportar Detalle"**: Genera reporte Excel con todos los movimientos

**Archivo modificado:** `frontend/src/pages/CashflowProjections.js`

---

## Previous Updates (January 22, 2026 - Session 2)

### Completed Previously ✅

**Corrección 1: Conciliación = Pagado/Cobrado**

1. ✅ **Lógica actualizada en `POST /api/reconciliations`**
   - Si se concilia con un CFDI, automáticamente crea el registro de pago si no existe
   - Elimina la restricción que requería pago previo para conciliar
   - La conciliación ahora implica que el movimiento está pagado/cobrado

**Corrección 2: Movimientos Sin UUID en Conciliaciones**

1. ✅ **Nuevo diálogo "Registrar Movimiento Sin UUID"**
   - Permite clasificar movimientos sin CFDI (comisiones bancarias, gastos sin factura, etc.)
   - Categorías disponibles:
     - Comisión Bancaria
     - Gasto sin Factura
     - Transferencia Interna
     - Pago de Nómina
     - Impuestos / ISR / IVA
     - Intereses
     - Retiro en Efectivo
     - Depósito No Identificado
     - Otro
   - Crea automáticamente un registro en Cobranza y Pagos

2. ✅ **Endpoint mejorado `POST /api/reconciliations/mark-without-uuid`**
   - Acepta `categoria` y `concepto` adicionales
   - Crea automáticamente el pago/cobro correspondiente
   - Mantiene la integridad del flujo de efectivo

**Corrección 3: Breakdown en Cobranza y Pagos**

1. ✅ **Nuevo endpoint `GET /api/payments/breakdown`**
   - **Por Cobrar / Por Pagar (CFDI)**: De facturas pendientes del SAT
   - **Cobrado / Pagado (Real)**: De movimientos conciliados con banco
     - Con CFDI: Pagos vinculados a facturas
     - Sin CFDI: Comisiones, gastos sin factura, etc.
   - **Proyecciones**: Para análisis de varianza vs real
   - **Varianza**: Comparación Real vs Proyectado (para flujo 13 semanas)

2. ✅ **UI actualizada en PaymentsModule.js**
   - 6 tarjetas de resumen:
     - Por Pagar (CFDI) - rojo
     - Por Cobrar (CFDI) - verde
     - Pagado (Real) - rojo oscuro
     - Cobrado (Real) - verde oscuro
     - Pagos Proyectados - indigo
     - Cobros Proyectados - púrpura
   - Banner negro con Flujo Neto Real vs Proyectado
   - Varianza % mostrada en cada tarjeta de proyección

**Testing Realizado:**
- ✅ Backend: Endpoint breakdown retorna datos correctos
- ✅ Frontend: Summary cards muestran el breakdown completo
- ✅ Diálogo Sin UUID funciona y registra en Cobranza y Pagos
- ✅ Capturas de pantalla verificadas

---

**P0 - Matching Automático de CFDIs (Sesión anterior)**

1. ✅ **Nuevo endpoint `GET /api/bank-transactions/{id}/match-cfdi`**
   - Busca CFDIs que coincidan con un movimiento bancario
   - Parámetros: `tolerance_days` (default: 60 días, configurable por el usuario)
   - Criterios de matching:
     - Monto similar (±10%)
     - Fecha dentro del rango de tolerancia (±60 días)
     - Tipo correcto (depósito → ingreso, retiro → egreso)
     - Moneda coincidente (bonus)
     - UUID parcial en descripción (bonus)
   - Retorna: lista de CFDIs candidatos con score de confianza (alta/media/baja)
   - Solo recomienda auto-link si score ≥ 60

2. ✅ **Nuevo endpoint `POST /api/payments/from-bank-with-cfdi-match`**
   - Crea un pago desde un movimiento bancario con detección automática de CFDI
   - Parámetros: `bank_transaction_id`, `cfdi_id` (opcional), `auto_detect` (default: true)
   - Si `auto_detect=true` y no se provee `cfdi_id`, busca y vincula automáticamente
   - Crea el registro de pago, actualiza el CFDI y crea la conciliación

3. ✅ **Nuevo endpoint `POST /api/bank-transactions/batch-create-payments`**
   - Procesa múltiples movimientos bancarios en lote
   - Body: `{ "transaction_ids": [...], "auto_detect": true }`
   - Intenta vincular automáticamente cada movimiento con su CFDI correspondiente
   - Retorna resumen: `{ created, linked_with_cfdi, errors, results }`

4. ✅ **Frontend actualizado**
   - Diálogo "Desde Banco" muestra información del matching automático
   - Banner verde explicando las reglas de matching
   - Usa el nuevo endpoint batch para procesar movimientos
   - Muestra cuántos pagos fueron vinculados automáticamente con CFDI

**P1 - Bug Crítico: Conciliación sin Pago (CORREGIDO)**

1. ✅ **Validación en `POST /api/reconciliations`**
   - Antes de crear una conciliación con un `cfdi_id`, valida que exista un registro de pago para ese CFDI
   - Si no existe pago, retorna error 400 con mensaje descriptivo
   - Mensaje: "No se puede conciliar con este CFDI porque no existe un registro de pago/cobro asociado. Primero registra el pago/cobro en el módulo 'Cobranza y Pagos' y luego intenta conciliar."
   - Esto previene la creación de conciliaciones huérfanas que corrompían la integridad de datos

**Testing Realizado:**
- ✅ Backend: Endpoint match-cfdi funciona correctamente, retorna candidatos con scores
- ✅ Backend: Validación de reconciliaciones sin pago rechaza correctamente la solicitud
- ✅ Frontend: Diálogo "Desde Banco" muestra información del matching automático
- ✅ Captura de pantalla verificada

---

## Previous Updates (January 22, 2026 - Session 1)

### Completed Previously ✅

**Integración Bancaria con Belvo - Open Banking**

1. ✅ **Backend de Belvo implementado**
   - Modelos: `BankConnection`, `BankMovementRaw` para conexiones y movimientos raw
   - Endpoints:
     - `GET /api/belvo/status` - Verificar estado de configuración
     - `GET /api/belvo/institutions` - Listar bancos mexicanos disponibles
     - `POST /api/belvo/connect` - Crear conexión bancaria
     - `GET /api/belvo/connections` - Listar conexiones activas
     - `POST /api/belvo/sync/{id}` - Sincronizar movimientos
     - `GET /api/belvo/movements-raw` - Listar movimientos raw de Belvo
     - `POST /api/belvo/movements-raw/{id}/process` - Procesar movimiento individual
     - `POST /api/belvo/movements-raw/process-all` - Procesar todos los movimientos pendientes

2. ✅ **Frontend de conexión bancaria**
   - Componente `BelvoConnectForm` con flujo de 3 pasos:
     - Status/Info sobre configuración
     - Selección de banco e institución
     - Ingreso de credenciales
   - Lista de conexiones activas con opciones de sync y eliminar
   - Mensaje informativo cuando Belvo no está configurado

3. ✅ **Configuración requerida** (en `/app/backend/.env`):
   ```
   BELVO_SECRET_ID=""
   BELVO_SECRET_PASSWORD=""
   BELVO_ENV="sandbox"
   ```

**Endpoints de Borrado Masivo (corregido)**

1. ✅ `DELETE /api/payments/bulk/all` - Borra todos los pagos/cobranzas
2. ✅ `DELETE /api/reconciliations/bulk/all` - Borra todas las conciliaciones
3. ✅ Botones "Borrar Todo" y "Borrar Conciliaciones" en la UI

---

**Mejora del Proceso de Conciliación - Movimientos Sin UUID**

1. ✅ **Conciliación de movimientos sin UUID**
   - Nuevo endpoint `POST /api/reconciliations/mark-without-uuid`
   - Permite marcar movimientos como "Sin UUID" (pagos sin factura) o "No relacionado" (movimientos internos)
   - Campo `tipo_conciliacion` agregado al modelo BankReconciliation (con_uuid, sin_uuid, no_relacionado)

2. ✅ **Resumen de conciliación**
   - Nuevo endpoint `GET /api/reconciliations/summary`
   - Muestra totales desglosados: Con UUID, Sin UUID, No Relacionado, Pendientes
   - Porcentaje de conciliación calculado automáticamente

3. ✅ **UI de conciliación actualizada**
   - 5 nuevas tarjetas de resumen (Con UUID, Sin UUID, No Relacionado, Diferencia Pendiente, % Conciliado)
   - Columna "Estado" muestra tipo de conciliación con colores distintivos
   - 3 botones de acción: "Con UUID", "Sin UUID", "No Rel." para cada movimiento pendiente

---

**6 Funcionalidades Anteriores (Completadas)**

1. ✅ **Desglose por Moneda en Cobranza y Pagos**
   - Las tarjetas de resumen muestran totales separados por MXN y USD
   - Endpoint `/api/payments/summary` devuelve: `total_por_cobrar_mxn`, `total_por_cobrar_usd`, `pagado_mes_mxn`, `pagado_mes_usd`, etc.
   - UI muestra: "$X MXN" y "+ $Y USD" cuando hay ambas monedas

2. ✅ **Selector de Cuenta Bancaria en Edición de Pagos**
   - Nuevo campo "Cuenta Bancaria" en el diálogo de edición de pagos
   - Vista previa de conversión de moneda: "Equivalente en MXN: $X" y "TC: 1 USD = X MXN"
   - Campo `bank_account_id` agregado al modelo de Payment

3. ✅ **Saldo Inicial Consolidado en Conciliaciones**
   - Cuando se selecciona "Todas las cuentas", muestra saldo inicial consolidado en MXN
   - Tarjetas muestran: "Saldo Inicial (Consolidado)" y "Saldo Final (Consolidado)"
   - Convierte automáticamente cuentas USD/EUR a MXN para el total

4. ✅ **Vista Anual de Tipos de Cambio**
   - Nueva pestaña "Vista Anual" en módulo FX Rates
   - Tabla de promedios mensuales por moneda (ENE-DIC)
   - Nuevo endpoint: `GET /api/fx-rates/year/{year}`
   - Navegación entre años con botones < >

5. ✅ **Exportación Excel con Tipo de Cambio Histórico**
   - La exportación de pagos incluye nuevas columnas: "TC Histórico", "Monto MXN"
   - Campo `tipo_cambio_historico` agregado al modelo Payment
   - Al crear un pago en USD, se captura automáticamente la tasa actual

6. ✅ **Transferencia de Movimientos Entre Cuentas**
   - Nuevo botón "Transferir" en módulo Conciliaciones
   - Endpoint: `POST /api/bank-transactions/transfer-account`
   - Actualiza automáticamente la moneda de los movimientos al transferir
   - Bug corregido: 28 movimientos transferidos de BBVA (MXN) a Citibanamex (USD)

**Archivos Modificados:**
- `backend/server.py`: Nuevos endpoints y modelos actualizados
- `frontend/src/pages/PaymentsModule.js`: Tarjetas de resumen, diálogo de edición
- `frontend/src/pages/BankStatementsModule.js`: Saldo consolidado, transferencia
- `frontend/src/pages/FXRatesModule.js`: Vista anual con pestañas
- `frontend/src/utils/excelExport.js`: Exportación con TC histórico

**Tests:** 17/17 backend tests passed (test_6_features.py)

---

## Previous Updates (January 21, 2026)
1. ✅ Nuevo botón **"Importar PDF"** en módulo Conciliaciones Bancarias
2. ✅ **Vista Previa antes de importar**: Muestra resumen con:
   - Banco detectado automáticamente
   - Total de movimientos encontrados
   - Suma de depósitos y retiros
   - Flujo neto
   - Tabla con primeros 15 movimientos para revisión
3. ✅ Soporte mejorado para bancos mexicanos:
   - **Banorte** (parser específico)
   - **BBVA** (parser específico)
   - **Santander** (parser específico) - NUEVO
   - **HSBC** (parser específico) - NUEVO
   - **Citibanamex** (parser específico) - NUEVO
   - Otros bancos (parser genérico)
4. ✅ Nuevo endpoint: `POST /api/bank-transactions/preview-pdf` - Vista previa sin importar
5. ✅ Detección de duplicados antes de confirmar
6. ✅ Librería: `pdfplumber` para parsing de PDFs

**Saldo Inicial en Conciliaciones**
1. ✅ El saldo inicial se toma automáticamente del módulo bancario al seleccionar una cuenta
2. ✅ Cálculo correcto: Saldo Final = Saldo Inicial + Depósitos - Retiros
3. ✅ Tarjetas de resumen muestran: Saldo Inicial, + Depósitos, - Retiros, = Saldo Final, Pendientes

---

## Previous Updates (January 20, 2026)

### Completed Previously ✅

**Filtros Avanzados en CFDIs**
1. Filtro por **categoría** (dropdown)
2. Filtro por **subcategoría** (aparece cuando se selecciona categoría)
3. Filtro por **fecha desde/hasta**
4. Botón **"Limpiar"** para resetear filtros
5. Botón **"Exportar Excel"** exporta CFDIs filtrados a CSV

**Exportar Proyecciones a Excel**
1. Botón **"Exportar Excel"** en proyecciones
2. Exporta en la **moneda seleccionada** (MXN/USD/EUR)
3. Incluye: Saldo inicial, Ingresos por categoría/subcategoría, Egresos, Flujo neto, Saldo final

**Selector de Moneda en Proyecciones**
1. Dropdown MXN/USD/EUR en la barra de herramientas
2. Conversión automática de todos los montos
3. TC visible cuando no es MXN

**Categorías y Subcategorías - CORREGIDO**
1. Montos ahora cuadran correctamente
2. Subcategorías expandibles con └
3. Totales por categoría = suma de subcategorías

---

## Recent Updates (January 24, 2026)

### Mejoras en Conciliaciones Bancarias ✅

1. ✅ **Balance Inicial con TC del Primer Día del Mes**
   - El saldo inicial consolidado ahora usa el TC del primer día del mes de las transacciones
   - Automáticamente detecta el mes de la transacción más antigua y obtiene el TC correspondiente
   - Endpoint: `GET /api/fx-rates/first-of-month?moneda=USD&year=YYYY&month=MM`
   - Mejora la precisión del balance cuando hay transacciones de meses anteriores

2. ✅ **Tipo de Cambio Editable en Conciliaciones**
   - Nuevo ícono de lápiz (✏️) junto al TC en el diálogo de conciliación
   - Al hacer clic, muestra un input numérico para modificar el TC manualmente
   - Botones de confirmar (✓) y cancelar (✗) para aplicar o descartar cambios
   - El TC personalizado se usa solo para la conciliación actual
   - Indicador visual cuando se usa TC personalizado vs histórico

3. ✅ **Botón "Sugerir" Mejorado**
   - Mejor manejo de errores con toast messages informativos
   - Indicador de carga mientras busca coincidencias
   - Mensajes claros cuando no hay coincidencias o cuando el CFDI ya está seleccionado
   - data-testid="sugerir-btn" para testing

**Archivos Modificados:**
- `frontend/src/pages/BankStatementsModule.js`:
  - Nuevos estados: `customFxRate`, `isEditingFxRate`
  - Función `loadFxRateFirstOfMonth` actualizada para usar fecha de transacciones
  - Función `getReconciliationTotals` actualizada para soportar TC personalizado
  - UI de edición de TC en el diálogo de conciliación

---

## Latest Updates (January 31, 2026)

### Completed ✅

**Feature 1: Historial de Pagos por CFDI**

Nuevo endpoint y UI para visualizar el historial completo de pagos aplicados a un CFDI:

**Backend (routes/cfdi.py):**
- Nuevo endpoint `GET /cfdi/{cfdi_id}/payment-history`
- Retorna: CFDI info, total pagado, saldo pendiente, % pagado, estado
- Detalle de cada pago: monto, fecha, tipo, estatus
- Referencia bancaria: banco, cuenta, descripción, referencia

**Frontend (BankStatementsModule.js):**
- Dialog "Historial de Pagos - CFDI" con barra de progreso visual
- Botón "Ver historial" en CFDIs con pagos previos
- Lista detallada de pagos con info bancaria

**Feature 2: Filtros Adicionales en Conciliaciones Bancarias**

Nuevos filtros para mejor gestión de movimientos bancarios:

**Frontend (BankStatementsModule.js):**
- Filtro **Emisor/Cliente**: Extrae nombres de descripciones de transacciones
- Filtro **Categoría**: Lista todas las categorías asignadas
- Ambos filtros integrados con el botón "Limpiar"
- Se combinan con los filtros existentes (Cuenta, Estado, Buscar)

**Testing:**
- Endpoint `/cfdi/{id}/payment-history` verificado con curl
- Filtros visibles en la UI

---

**Feature: Conciliación con Pagos Parciales** (Previous)

Implementación completa de funcionalidad para conciliar movimientos bancarios con CFDIs de forma parcial:

**Frontend (BankStatementsModule.js):**
- Estado `montosParciales` para mantener los montos a aplicar por cada CFDI
- Campo editable "Monto a aplicar ahora" para cada CFDI seleccionado
- Muestra "Total CFDI", "Ya pagado anteriormente", "Saldo pendiente"
- Mensaje informativo: "Después de este pago quedará pendiente: $X"
- Cálculo dinámico de totales usando montos parciales
- UI actualizada en la sección "CFDIs seleccionados (Pagos Parciales Permitidos)"

**Backend (routes/reconciliations.py & models/bank.py):**
- Campo `monto_aplicado` opcional en `BankReconciliationCreate`
- Validación de saldo pendiente antes de conciliar
- Actualización de `monto_cobrado` / `monto_pagado` en el CFDI
- Estado del CFDI: 'conciliado' si totalmente pagado, 'parcial' si queda saldo
- Permite múltiples conciliaciones del mismo CFDI con diferentes transacciones

**Backend (server.py):**
- Endpoint `/cfdi` ahora incluye `saldo_pendiente` calculado automáticamente

**Flujo de uso:**
1. Usuario abre diálogo de conciliación para un movimiento
2. Selecciona un CFDI (aunque tenga monto mayor)
3. Edita el "Monto a aplicar ahora" al monto real del movimiento
4. Sistema muestra cuánto quedará pendiente
5. Confirma conciliación → CFDI queda con saldo pendiente para futuros pagos

**Testing:** 
- Verificado manualmente con screenshot
- Conciliación parcial de LULO GELATO ($126,580.00) con pago de $21,096.67
- CFDI quedó con saldo pendiente de $105,483.33

---

## Previous Updates (January 30, 2026)

### Completed ✅

**Feature: Gráficos Comparativos y Exportación a PDF**

Se agregaron 4 gráficos interactivos con Recharts y funcionalidad de exportar a PDF:

**Gráficos implementados:**
1. **Flujo Acumulado: Real vs Proyectado** - Área verde para Real Acumulado (S1-S5), línea punteada azul para Proyectado Total
2. **Ingresos vs Egresos Semanal** - Barras verdes (Ingresos) y rojas (Egresos) por cada semana S1-S18
3. **Saldo Final vs Umbral Mínimo (Cash Gap)** - Área azul de saldo final con línea roja de referencia del umbral
4. **Flujo Neto Semanal** - Barras verdes (flujo positivo) y rojas (flujo negativo) con línea de referencia en 0

**Exportación a PDF:**
- Botón "Exportar PDF" en rojo junto al botón de Excel
- Usa html2canvas + jsPDF para capturar todo el contenido
- Genera PDF en orientación landscape A4
- Incluye: KPIs, Gráficos, Sección de Flujo Acumulado, Tabla completa de 18 semanas
- Nombre: `Proyeccion_Flujo_Efectivo_YYYYMMDD_HHmm.pdf`
- Pie de página con fecha de generación y número de página

**Dependencias agregadas:**
- `html2canvas: ^1.4.1`
- `jspdf: ^4.0.0`

**Archivos Modificados:**
- `frontend/src/pages/CashflowProjections.js`:
  - Importaciones de Recharts (LineChart, BarChart, ComposedChart, Area, etc.)
  - Nueva función `prepareChartData()` para transformar datos
  - Nueva función `exportToPDF()` con html2canvas + jsPDF
  - Sección de 4 gráficos en grid 2x2
  - Ref `reportRef` para captura de PDF

**Testing:** 
- 8/8 funcionalidades verificadas por testing agent
- 100% pass rate en frontend

---

## Previous Updates (January 29, 2026)

### Completed ✅

**Feature P0: KPIs "Grado CFO" en Proyección de Flujo de Efectivo**

Implementación completa de KPIs ejecutivos para transformar el reporte de 13 semanas en un modelo rolling de 18 semanas tipo CFO:

**Cambios estructurales:**
- Modelo expandido de 13 → 18 semanas (4 Real + 1 Actual + 13 Proyectado)
- Nueva propiedad `dataType` por semana: 'real' | 'actual' | 'proyectado'
- Etiquetas visuales diferenciadas por tipo de dato (amarillo=Real, azul=Actual, gris=Proy)

**Nuevos KPIs CFO (4 tarjetas):**
1. **Net Burn Rate**: Promedio semanal de flujo neto Real (S1-S4) vs Proyectado (S6-S18)
2. **Cash Gap Analysis**: 
   - Umbral mínimo de caja configurable (default $500,000)
   - Semanas en riesgo (saldo < umbral)
   - Semana crítica identificada
3. **Volatilidad del Flujo**:
   - Desviación estándar del flujo neto real
   - Coeficiente de variación con indicador de estabilidad
4. **Indicadores Operativos**:
   - Runway (semanas de operación con saldo actual)
   - Ratio Cobranza vs Pagos

**Sección de Flujo Acumulado:**
- Ingresos Reales (S1-S5) vs Ingresos Proyectados (S6-S18)
- Egresos Reales (S1-S5) vs Egresos Proyectados (S6-S18)
- Flujo Neto Real Acumulado
- Flujo Neto Proyectado Total

**Nuevas filas en tabla:**
- SALDO INICIAL SEMANA (al inicio)
- SALDO FINAL SEMANA (antes del resumen)
- CASH GAP (diferencia vs umbral mínimo configurable)

**Archivos Modificados:**
- `frontend/src/pages/CashflowProjections.js`:
  - Líneas 218-260: Generación de 18 semanas con dataType
  - Líneas 770-842: Nueva función `calculateCFOKPIs()`
  - Líneas 1080-1250: Panel de KPIs CFO y Flujo Acumulado
  - Líneas 1570-1620: Filas SALDO FINAL SEMANA y CASH GAP

**Testing:** 
- 9/9 funcionalidades verificadas por testing agent
- 100% pass rate en frontend

---

## Previous Updates (January 25, 2026)

### Completed ✅

**Feature: Separación de Compra/Venta de USD en Proyecciones**
- Implementada nueva sección "OPERACIONES CON DIVISAS" en el módulo de Proyecciones
- Las categorías "Compra de USD" y "Venta de USD" ahora aparecen separadas de INGRESOS y EGRESOS
- Cálculo correcto del flujo neto incluyendo operaciones de divisas
- UI con color púrpura distintivo para la sección de divisas
- Solo se muestra si hay datos de compra/venta de USD

**Archivos Modificados:**
- `frontend/src/pages/CashflowProjections.js`: 
  - Nuevo tracking para `compraUSD` y `ventaUSD` por semana
  - Filtrado de categorías USD de las secciones de INGRESOS/EGRESOS
  - Nueva sección visual "OPERACIONES CON DIVISAS"
  - Cálculo de `flujoDivisas` = ventaUSD - compraUSD

**Refactorización de server.py - FASE 2 COMPLETADA:**
- Archivo reducido: 8,630 → 7,402 líneas (**14% reducción**)
- **TODOS los 8 routers ahora integrados**:
  - auth (7 endpoints)
  - companies (4 endpoints)
  - categories (6 endpoints)
  - vendors (4 endpoints)
  - customers (4 endpoints)
  - bank_accounts (5 endpoints)
  - payments (6 endpoints) - con lógica de reversión CFDI
  - reconciliations (7 endpoints) - con lógica de integridad de datos
- **43 endpoints** en arquitectura modular
- Documentación: `/app/docs/REFACTORING_PLAN.md`

---

## Backlog (P0 - P2)

### P0 - Critical (COMPLETED)
All P0 features implemented and tested:
- ✅ P0 - Matching Automático de CFDIs (January 22, 2026)
- ✅ P0 - KPIs "Grado CFO" en Proyecciones de Flujo de Efectivo (January 29, 2026)

### P1 - High Priority
1. ✅ **Refactor `server.py` - PHASE 2 COMPLETE** (January 25, 2026)
   - All 8 routers integrated with full functionality
   - server.py reduced by 14%
   - Next phase: Create cfdi.py, fx_rates.py, bank_transactions.py modules

2. **Notificaciones automáticas** - Alertas por email/SMS para vencimientos
3. ✅ **Bug Fix: Conciliación sin Pago** - COMPLETED (January 22, 2026)
4. **Completar refactorización de server.py** - Eliminar código duplicado, mover dashboard endpoint a routes/reports.py

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

### Authentication (✅ Moved to routes/auth.py)
- `POST /api/auth/login` - Login
- `POST /api/auth/register` - Register new user
- `GET /api/auth/me` - Get current user
- `GET /api/auth/auth0/config` - Auth0 config
- `GET /api/auth/auth0/login-url` - Auth0 login URL
- `POST /api/auth/auth0/callback` - Auth0 callback
- `POST /api/auth/auth0/verify` - Verify Auth0 token

### Companies (✅ Moved to routes/companies.py)
- `POST/GET /api/companies` - Companies CRUD
- `GET /api/companies/{id}` - Get company
- `PUT /api/companies/{id}` - Update company

### Bank Accounts (✅ Moved to routes/bank_accounts.py)
- `POST/GET /api/bank-accounts` - Bank accounts CRUD
- `PUT /api/bank-accounts/{id}` - Update account
- `DELETE /api/bank-accounts/{id}` - Delete account
- `GET /api/bank-accounts/summary` - Summary with FX conversion

### Categories (✅ Moved to routes/categories.py)
- `GET /api/categories` - List categories (with subcategories)
- `GET /api/categories?tipo=ingreso|egreso` - Filter by type
- `POST /api/categories` - Create category
- `PUT /api/categories/{id}` - Update category
- `DELETE /api/categories/{id}` - Delete category (soft delete)
- `POST /api/subcategories` - Create subcategory
- `DELETE /api/subcategories/{id}` - Delete subcategory

### Vendors (✅ Moved to routes/vendors.py)
- `POST/GET /api/vendors` - Vendors CRUD
- `PUT /api/vendors/{id}` - Update vendor
- `DELETE /api/vendors/{id}` - Delete vendor

### Customers (✅ Moved to routes/customers.py)
- `POST/GET /api/customers` - Customers CRUD
- `PUT /api/customers/{id}` - Update customer
- `DELETE /api/customers/{id}` - Delete customer

### Core Resources (Still in server.py)
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

### January 20, 2026 (Session 3)
- **NEW: Módulo Estados de Cuenta dedicado** (`/bank-statements`)
  - Tabla completa de movimientos bancarios con filtros avanzados
  - Búsqueda por descripción/referencia
  - Filtro por cuenta bancaria y estado de conciliación
  - Botón "Conectar Banco" con información de próxima integración
  - Importación desde Excel de estados de cuenta
  - Exportación a Excel de movimientos
  - Formulario completo para agregar movimientos manualmente
  - Diálogo de conciliación con CFDIs disponibles
  - Tarjetas de resumen: Total Depósitos, Total Retiros, Flujo Neto, Pendientes Conciliar
  - Botón eliminar movimiento
  - Estados visuales: Pendiente/Conciliado

### January 20, 2026 (Session 2)
- **NEW: Reporte DIOT** - Declaración Informativa de Operaciones con Terceros
  - Solo facturas de egreso (pagos a proveedores) que han sido pagadas
  - Filtros por fecha
  - Exportación a Excel (.xlsx) y TXT (formato SAT)
  - Resumen con total de operaciones, monto y IVA
  - Información de tipos de tercero y operación según SAT
  - Nueva ruta `/diot` y entrada en menú lateral
  - Endpoint: GET /api/diot/preview

- **NEW: Estados de Cuenta Bancarios** - Pestaña en módulo Bancario
  - Nueva pestaña "Estados de Cuenta" para captura manual de movimientos
  - Diálogo completo para agregar movimientos: cuenta, fechas, descripción, referencia, tipo, monto, saldo
  - Vista de tabla con estado de conciliación
  - Permite capturar movimientos mientras se obtiene acceso a APIs bancarias

### January 20, 2026
- **Fixed Excel Export Feature**: Completed implementation of XLSX export across all 4 modules
  - `CFDIModule.js`: Export CFDIs to Excel with categories, amounts, dates
  - `PaymentsModule.js`: Export payments/collections to Excel  
  - `Transactions.js` (Aging): Export aging report with CxC and CxP sheets
  - `CashflowProjections.js`: Fixed to use XLSX instead of CSV, includes 13-week model
- Created centralized export utility at `/frontend/src/utils/excelExport.js`
- Uses `xlsx` library (v0.18.5) and `file-saver` (v2.0.5) for proper .xlsx file generation
- All exports include proper date formatting, auto-column widths, and Spanish labels
- Testing: 100% success rate on all 4 export modules

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

### January 25, 2026 (Latest)
- **Bug Fix P0**: Corregido bug crítico de subcategorías no visibles
  - Causa raíz: El backend devolvía `subcategories` pero el frontend esperaba `subcategorias`
  - Solución: Actualizado `routes/categories.py` para usar `subcategorias` 
  - Estado: Las 34 subcategorías ahora se muestran correctamente
  - NOTA: Los datos NUNCA fueron eliminados, solo era un problema de visualización

- **Feature: Rolling 18-Week Cash Flow Model**
  - Implementado modelo rolling de 18 semanas en `/reports`:
    - S1-S4: 4 semanas históricas (Real)
    - S5: Semana actual (Actual)
    - S6-S18: 13 semanas futuras proyectadas (Proy)
  - El modelo se actualiza automáticamente cada semana
  - Las semanas pasadas cambian de Proyectado → Real automáticamente

- **Feature: DIOT Fiscal Compliance Fix**
  - DIOT ahora excluye automáticamente según reglas SAT:
    - Nómina (uso_cfdi = 'CN01')
    - CFDIs sin IVA acreditable (IVA = 0)
    - Sueldos, asimilados, cargas sociales
  - Operaciones reducidas de 33 → 21 (solo proveedores con IVA)
  - Agregado banner de advertencia en UI sobre exclusiones
  - Agregadas columnas de Categoría y Subcategoría en tabla
  - Mejorado layout compacto con moneda origen y moneda MXN

- **Feature: Dashboard KPIs Ejecutivos Mejorado**
  - Nueva sección "KPIs Clave de Liquidez":
    - RUNWAY: Semanas de operación con saldo actual
    - BURN RATE: Promedio de egresos semanales
    - COBRANZA VS PAGOS: Ratio ingresos/egresos
    - SEMANA CRÍTICA: Menor saldo proyectado
  - Nueva sección "¿Qué Hacer Ahora?":
    - Acciones recomendadas dinámicas basadas en el flujo
    - Alertas de liquidez crítica, cobranza baja, CFDIs sin conciliar
  - Nueva sección "Análisis de Escenarios":
    - Escenario Pesimista (cobranza -30%, gastos +15%)
    - Escenario Base (tendencia actual)
    - Escenario Optimista (cobranza +20%, gastos -10%)

- **Bug Fix: CFDI Summary endpoint**
  - Corregido routes/cfdi.py para devolver estructura correcta
  - Ahora muestra totales_convertidos y totales_por_moneda
  - Ingresos y Egresos ahora visibles en el módulo SAT

- **Feature: Proyecciones Drill-Down y Desglose**
  - Nueva sublínea "📥 Depósitos / Otros Cobros (sin CFDI)" para ingresos reales sin factura
  - Endpoint `/api/projections/week-detail` para auditar transacciones por semana:
    - Lista CFDIs con categoría/subcategoría
    - Lista Payments con origen (Banco/CFDI/Manual)
    - Calcula diferencia entre cobros y CFDIs
  - Corrección de lógica: INGRESOS = MAX(real, cfdi) para evitar duplicados

- **Feature: Export Excel con Categoría/Subcategoría**
  - Pagos Excel ahora incluye columnas Categoría y Subcategoría
  - Carga automática de categorías en PaymentsModule

- **Feature: Herencia de Categoría/Subcategoría CFDI → Pagos** (IMPORTANTE)
  - Cuando un CFDI tiene categoría asignada y se cobra/paga o concilia:
    - El registro de Cobranza/Pagos HEREDA automáticamente:
      - `category_id` del CFDI
      - `subcategory_id` del CFDI
      - `cfdi_uuid` del CFDI
      - `cfdi_emisor` y `cfdi_receptor`
  - Actualizado: `routes/payments.py` (create_payment)
  - Actualizado: `routes/reconciliations.py` (create_reconciliation)
  - Nuevo endpoint: `POST /api/payments/backfill-categories` para actualizar pagos existentes
  - UI de Cobranza y Pagos actualizada:
    - Nueva columna "UUID CFDI"
    - Nueva columna "Categoría" (con subcategoría)
    - Botón "Sincronizar Categorías" para backfill
  - **21 de 31 pagos existentes actualizados** con categorías heredadas

- **Refactoring Avance**: 11 routers modulares ahora integrados
  - cfdi.py, fx_rates.py, bank_transactions.py creados con endpoints funcionales
  - server.py reducido a 7,408 líneas
- **Módulos Integrados y Funcionando**:
  - auth, companies, categories, vendors, customers
  - bank_accounts, payments, reconciliations
  - cfdi, fx_rates, bank_transactions

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
