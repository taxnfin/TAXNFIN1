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
3. **Belvo Bank Integration** - Scaffolding complete, pending user API credentials

---

## Latest Updates (January 22, 2026 - Session 2)

### Completed in This Session ✅

**P0 - Matching Automático de CFDIs**

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
