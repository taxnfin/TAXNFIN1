# TaxnFin Cashflow - Motor Financiero y Fiscal

## Descripción General

TaxnFin Cashflow es un sistema SaaS backend-first para gestión avanzada de flujo de efectivo empresarial con integración fiscal (SAT/CFDI) y bancaria.

## Arquitectura del Sistema

### Stack Tecnológico
- **Backend**: FastAPI (Python)
- **Base de Datos**: MongoDB
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **Autenticación**: JWT
- **Gráficas**: Recharts

### Arquitectura Modular

```
/app/
├── backend/
│   ├── server.py          # API principal con todos los endpoints
│   ├── requirements.txt   # Dependencias Python
│   └── .env               # Variables de entorno
├── frontend/
│   ├── src/
│   │   ├── pages/         # Páginas principales
│   │   ├── components/    # Componentes reutilizables
│   │   └── api/          # Cliente Axios
│   └── package.json
└── docs/
    └── templates/        # Plantillas de importación
```

## Entidades Principales

### 1. Company (Empresa)
- Información de la empresa
- Configuración de moneda base y país

### 2. User (Usuario)
- Control de acceso por roles: Admin, CFO, Viewer
- Autenticación JWT

### 3. BankAccount (Cuenta Bancaria)
- Cuentas de la empresa
- Soporte multi-moneda

### 4. CashFlowWeek (Semana de Flujo)
- Sistema rolling de 13 semanas
- Cálculos automáticos de saldos

### 5. Transaction (Transacción)
- Ingresos y egresos
- Clasificación: real vs proyección
- Origen: banco, CSV, manual

### 6. CFDI (Factura Electrónica)
- Facturas del SAT
- Parser XML integrado
- Status: vigente/cancelado

### 7. BankTransaction (Movimiento Bancario)
- Movimientos de cuentas bancarias
- Preparado para APIs bancarias

### 8. BankReconciliation (Conciliación)
- Liga movimientos bancarios con transacciones
- Métodos: automático/manual

### 9. AuditLog (Auditoría)
- Registro completo de operaciones
- Trazabilidad total

## Motor de Cashflow

### Reglas del Motor
1. **13 Semanas Rolling**: Sistema mantiene siempre 13 semanas de flujo
2. **Proyecciones vs Reales**: Separación clara entre proyectado y realizado
3. **Conciliación**: Movimientos bancarios convierten proyecciones en reales
4. **Multi-moneda**: Soporte para múltiples monedas con tipos de cambio

### Cálculos Automáticos
- Saldo inicial + ingresos - egresos = saldo final
- Cálculos separados para real y proyectado
- Actualización automática al crear/modificar transacciones

## Módulo SAT/CFDI

### Funcionalidades Actuales
- **Subida Manual de XML**: Carga de archivos CFDI
- **Parser Automático**: Extracción de datos del XML
- **Visualización**: Listado y detalle de facturas
- **Status**: Control de vigencia/cancelación

### Estructura XML Soportada
- CFDI versión 4.0
- Extracción de: UUID, RFC emisor/receptor, montos, impuestos
- Soporte para diferentes tipos: ingreso, egreso, pago, nota de crédito

### Futuro (Preparado)
- Descarga automática desde portal SAT
- Almacenamiento de credenciales CSD/e.firma cifradas
- Scraping controlado

## Módulo Bancario

### Funcionalidades
- **Registro Manual**: Captura de movimientos bancarios
- **Importación CSV/Excel**: Carga masiva
- **Conciliación Manual**: Liga movimientos con transacciones
- **Status de Conciliación**: Visual de pendientes vs conciliados

### Preparado para Integración
- Estructura lista para APIs bancarias
- Campos para fuente de datos (API, CSV, manual)
- Soporte para diferentes bancos

## API Endpoints

### Autenticación
```
POST /api/auth/register  # Registro de usuario
POST /api/auth/login     # Inicio de sesión
GET  /api/auth/me        # Información del usuario actual
```

### Empresas
```
POST /api/companies      # Crear empresa
GET  /api/companies      # Listar empresas
GET  /api/companies/{id} # Obtener empresa
```

### Cuentas Bancarias
```
POST /api/bank-accounts  # Crear cuenta
GET  /api/bank-accounts  # Listar cuentas
```

### Proveedores y Clientes
```
POST /api/vendors        # Crear proveedor
GET  /api/vendors        # Listar proveedores
POST /api/customers      # Crear cliente
GET  /api/customers      # Listar clientes
```

### Transacciones
```
POST /api/transactions        # Crear transacción
GET  /api/transactions        # Listar transacciones
POST /api/transactions/import # Importar desde Excel
```

### Cashflow
```
GET /api/cashflow/weeks  # Obtener 13 semanas de flujo
```

### CFDI
```
POST /api/cfdi/upload    # Subir XML
GET  /api/cfdi           # Listar CFDIs
```

### Bancario
```
POST /api/bank-transactions   # Crear movimiento
GET  /api/bank-transactions   # Listar movimientos
POST /api/reconciliations     # Crear conciliación
GET  /api/reconciliations     # Listar conciliaciones
```

### Reportes
```
GET /api/reports/dashboard    # Dashboard ejecutivo
```

### Auditoría
```
GET /api/audit-logs      # Logs de auditoría (Admin/CFO)
```

### Tipos de Cambio
```
POST /api/fx-rates       # Crear tipo de cambio
GET  /api/fx-rates       # Listar tipos de cambio
```

## Seguridad

### Control de Acceso
- **Admin**: Acceso completo, gestión de empresas y usuarios
- **CFO**: Acceso a operaciones financieras y reportes
- **Viewer**: Solo lectura

### Auditoría
- Registro automático de todas las operaciones CREATE/UPDATE/DELETE
- Almacenamiento de estados anterior y nuevo
- Trazabilidad completa por usuario y timestamp

### JWT
- Tokens con expiración de 7 días
- Renovación automática en frontend
- Logout desde cualquier dispositivo

## Guía de Uso

### 1. Configuración Inicial

1. **Crear Empresa**
   - Ir a Catálogos → Empresas
   - Clic en "Nueva Empresa"
   - Llenar: nombre, RFC, moneda base
   - Guardar el ID de la empresa

2. **Registrar Usuario**
   - Usar el ID de la empresa
   - Crear cuenta con email y contraseña
   - Asignar rol apropiado

3. **Configurar Cuentas Bancarias**
   - Catálogos → Cuentas Bancarias
   - Agregar cuentas de la empresa
   - Configurar saldo inicial

### 2. Operación Diaria

1. **Registrar Transacciones**
   - Transacciones → Nueva Transacción
   - Clasificar como ingreso/egreso
   - Marcar como real o proyección

2. **Subir CFDIs**
   - CFDI/SAT → Subir XML CFDI
   - Sistema parsea automáticamente
   - Visualizar en listado

3. **Movimientos Bancarios**
   - Bancario → Nuevo Movimiento
   - Registrar movimientos de estado de cuenta
   - Conciliar con transacciones existentes

### 3. Análisis y Reportes

1. **Dashboard**
   - Vista de KPIs principales
   - Gráfica de 13 semanas
   - Comparativos visuales

2. **Reportes**
   - Reporte detallado semanal
   - Variaciones real vs proyectado
   - Indicadores clave

## Importación de Datos

### Template de Transacciones (Excel)

Ver archivo: `/app/docs/templates/transacciones_template.xlsx`

**Columnas requeridas:**
1. bank_account_id (UUID de la cuenta bancaria)
2. concepto (texto)
3. monto (número decimal)
4. tipo_transaccion ("ingreso" o "egreso")
5. fecha_transaccion (YYYY-MM-DD HH:MM:SS)
6. es_real (true/false)
7. es_proyeccion (true/false)
8. vendor_id (UUID del proveedor, opcional)
9. customer_id (UUID del cliente, opcional)

### Uso:
1. Descargar template
2. Llenar con tus datos
3. Ir a Transacciones → Importar Excel
4. Seleccionar archivo
5. Revisar resultado de importación

## Notas Técnicas

### MongoDB
- Base de datos: `taxnfin_cashflow`
- Todas las fechas se almacenan en formato ISO
- Los ObjectId se excluyen automáticamente de las respuestas

### Rendimiento
- Paginación en endpoints de listado (limit/skip)
- Índices recomendados en campos de búsqueda frecuente
- Cache de dashboards para empresas grandes

### Escalabilidad
- Multi-tenant por diseño (company_id en todas las entidades)
- Fácil integración con servicios externos
- Arquitectura preparada para microservicios

## Roadmap

### Fase 2 (Pendiente)
- [ ] Descarga automática de CFDIs desde portal SAT
- [ ] Integración con APIs bancarias (BBVA, Santander, etc.)
- [ ] Conciliación automática con ML
- [ ] Proyecciones inteligentes basadas en historial
- [ ] Alertas y notificaciones por email/SMS
- [ ] Módulo de presupuestos
- [ ] Exportación a formatos contables (COI, XML)

### Fase 3 (Futuro)
- [ ] Cálculos fiscales (IVA, ISR, DIOT)
- [ ] Integración con sistemas contables
- [ ] App móvil
- [ ] Dashboards personalizables
- [ ] Reportes regulatorios automáticos

## Soporte

Para preguntas técnicas o soporte:
- Documentación: Este archivo
- API Docs: http://localhost:8001/docs (Swagger)
- Logs: `/var/log/supervisor/`

## Licencia

Sistema propietario para uso interno empresarial.
