# TaxnFin Cashflow - Fase 3: Escenarios y Exportaciones

## Análisis de Escenarios "Qué Pasaría Si"

### Descripción
Permite simular diferentes estrategias financieras y ver su impacto en el flujo de efectivo antes de ejecutarlas.

### Tipos de Escenarios Soportados

1. **Adelantar Pago**
   - Simula el pago anticipado a un proveedor
   - Útil para: evaluar descuentos por pronto pago
   
2. **Retrasar Cobro**
   - Simula la extensión de plazo de cobro a un cliente
   - Útil para: mantener relaciones comerciales

3. **Ajustar Monto**
   - Simula cambios en el monto de una transacción
   - Útil para: negociaciones de descuentos

4. **Eliminar Transacción**
   - Simula la cancelación de una compra/venta
   - Útil para: evaluar recortes de gastos

5. **Agregar Transacción**
   - Simula una nueva transacción (ej: préstamo bancario)
   - Útil para: evaluar inyecciones de capital

### API Usage

```bash
# Crear escenario
curl -X POST "$API_URL/api/scenarios/create" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Adelantar pago proveedor ABC",
    "descripcion": "Evaluar descuento 5% por pronto pago",
    "modificaciones": [
      {
        "tipo": "adelantar_pago",
        "transaction_id": "txn-id-123",
        "nueva_fecha": "2026-01-20",
        "razon": "Descuento 5%"
      }
    ]
  }'

# Listar escenarios
curl -X GET "$API_URL/api/scenarios" \
  -H "Authorization: Bearer $TOKEN"

# Comparar múltiples escenarios
curl -X POST "$API_URL/api/scenarios/compare" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_ids": ["scenario-1", "scenario-2", "scenario-3"]
  }'
```

### Métricas de Comparación

Cada escenario calcula:
- Diferencia en ingresos totales
- Diferencia en egresos totales
- Diferencia en flujo neto
- Diferencia en saldo final
- % de mejora
- Semanas críticas evitadas
- Recomendación automática (🟢 Recomendado | 🟡 Considerar | 🔴 No recomendado)

### Casos de Uso

**Caso 1: Préstamo vs Extensión de Plazo**
```
Escenario A: Solicitar préstamo $500,000
Escenario B: Negociar extensión 30 días con proveedores

Sistema compara ambos y recomienda el mejor impacto en liquidez
```

**Caso 2: Descuento Pronto Pago**
```
Escenario: Adelantar 10 pagos para obtener 5% descuento
Sistema calcula: Ahorro vs impacto en liquidez

Resultado: Si ahorro supera costo de oportunidad → Recomendado
```

---

## Exportaciones Contables

### Formatos Disponibles

### 1. COI (Contabilidad)
**Descripción**: Formato CSV usado por sistemas contables mexicanos  
**Estructura**:
- RFC, Razón Social
- Fecha, Tipo Póliza, Número Póliza
- Cuenta, SubCuenta, Concepto
- Cargo, Abono, Referencia

**Cuentas Contables**:
- 1020: Bancos
- 4010: Ingresos por servicios
- 5010: Gastos de operación

**Uso**:
```bash
curl -X GET "$API_URL/api/export/coi?fecha_inicio=2026-01-01&fecha_fin=2026-01-31" \
  -H "Authorization: Bearer $TOKEN" \
  -o coi_enero.csv
```

### 2. XML Fiscal (Balanza SAT)
**Descripción**: Formato XML según anexo 24 SAT (Balanza de Comprobación)  
**Normativa**: Cumple con requisitos de contabilidad electrónica SAT  
**Elementos**:
- RFC, Mes, Año, TipoEnvío
- Listado de cuentas con saldos iniciales, debe, haber, saldo final

**Uso**:
```bash
curl -X GET "$API_URL/api/export/xml-fiscal?fecha_inicio=2026-01-01&fecha_fin=2026-01-31" \
  -H "Authorization: Bearer $TOKEN" \
  -o balanza_enero.xml
```

**Importante**: Este XML puede enviarse directamente al SAT como parte de la contabilidad electrónica.

### 3. Alegra (JSON)
**Descripción**: Formato JSON para importación en Alegra  
**Alegra**: Software contable popular en Latinoamérica  
**Estructura**:
```json
{
  "metadata": {
    "company": {...},
    "export_date": "...",
    "format": "alegra_v1"
  },
  "journal_entries": [
    {
      "number": 1,
      "date": "2026-01-15",
      "description": "...",
      "items": [
        {
          "account": {"code": "1105", "name": "Bancos"},
          "debit": 50000,
          "credit": 0
        }
      ]
    }
  ]
}
```

**Plan de Cuentas Alegra**:
- 1105: Bancos
- 4135: Ingresos por servicios
- 5195: Gastos diversos

**Uso**:
```bash
curl -X GET "$API_URL/api/export/alegra?fecha_inicio=2026-01-01&fecha_fin=2026-01-31" \
  -H "Authorization: Bearer $TOKEN" \
  -o alegra_enero.json
```

**Importación en Alegra**:
1. Ir a Contabilidad → Importar
2. Seleccionar formato JSON
3. Cargar archivo exportado
4. Validar y confirmar

### 4. Cashflow Report
**Descripción**: Reporte completo de 13 semanas en Excel/JSON  
**Columnas**:
- Semana, Fecha Inicio, Fecha Fin
- Saldo Inicial
- Ingresos Reales, Egresos Reales
- Ingresos Proyectados, Egresos Proyectados
- Flujo Neto Real, Flujo Neto Proyectado

**Uso**:
```bash
# Excel (CSV)
curl -X GET "$API_URL/api/export/cashflow?formato=excel" \
  -H "Authorization: Bearer $TOKEN" \
  -o cashflow_13_semanas.csv

# JSON
curl -X GET "$API_URL/api/export/cashflow?formato=json" \
  -H "Authorization: Bearer $TOKEN" \
  -o cashflow_13_semanas.json
```

---

## Integraciones Bancarias Ampliadas

### Bancos Agregados

#### Banco del Bajío
- **API URL**: https://api.bancobajio.com.mx/v1
- **Autenticación**: OAuth 2.0
- **Credenciales requeridas**:
  - client_id
  - client_secret
  - institution_id
- **Tipo**: Open Banking
- **Endpoints disponibles**:
  - `/accounts`: Lista de cuentas
  - `/transactions`: Movimientos
  - `/balance`: Saldo en tiempo real

#### American Express (Tarjetas Empresariales)
- **API URL**: https://api.americanexpress.com/v1
- **Autenticación**: API Key + Secret
- **Credenciales requeridas**:
  - api_key
  - api_secret
- **Tipo**: Credit Card API
- **Endpoints disponibles**:
  - `/corporate-cards`: Tarjetas corporativas
  - `/transactions`: Gastos con tarjeta
  - `/statements`: Estados de cuenta

### Conectar Banco

```bash
curl -X POST "$API_URL/api/bank-api/connect" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "bank_account_id": "cuenta-123",
    "bank_name": "BAJIO",
    "credentials": {
      "client_id": "your-client-id",
      "client_secret": "your-client-secret",
      "institution_id": "your-institution-id"
    }
  }'
```

### Sincronizar Transacciones

```bash
curl -X POST "$API_URL/api/bank-api/sync/cuenta-123?days_back=30" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Workflow Completo: CFO Toma Decisión

### Paso 1: Análisis Predictivo
```bash
GET /api/ai/predictive-analysis
# Resultado: "Semana +3 tendrá déficit de $150,000"
```

### Paso 2: Crear Escenarios
```bash
POST /api/scenarios/create
# Escenario A: Solicitar préstamo
# Escenario B: Retrasar 3 pagos grandes
# Escenario C: Adelantar cobro urgente
```

### Paso 3: Comparar Escenarios
```bash
POST /api/scenarios/compare
# Resultado: Escenario B es mejor (resuelve crisis sin costo)
```

### Paso 4: Ejecutar Decisión
- CFO negocia con proveedores
- Actualiza fechas en sistema
- Flujo se actualiza automáticamente

### Paso 5: Monitoreo
```bash
POST /api/alerts/check-and-send
# Sistema envía alertas si surge nuevo problema
```

### Paso 6: Reportar a Contabilidad
```bash
GET /api/export/alegra?fecha_inicio=...&fecha_fin=...
# Exporta a Alegra para cierre contable
```

---

## Mejores Prácticas

### Escenarios
1. **Crea múltiples escenarios** antes de tomar decisiones importantes
2. **Compara siempre** al menos 3 alternativas
3. **Documenta las razones** de cada modificación
4. **Revisa semanalmente** los escenarios vs realidad

### Exportaciones
1. **Programa exportaciones mensuales** para contabilidad
2. **Usa COI** para sistemas contables tradicionales
3. **Usa Alegra** si usas ese software
4. **XML Fiscal** es obligatorio para cumplimiento SAT
5. **Guarda backups** de cada exportación

### Integraciones Bancarias
1. **Conecta todas las cuentas principales**
2. **Sincroniza diariamente** para datos actualizados
3. **Verifica credenciales** cada 90 días
4. **Monitorea fallos** de sincronización

---

## Roadmap Futuro

### Fase 4 (Próximos 3 meses)
- [ ] Machine Learning avanzado (LSTM para series temporales)
- [ ] Recomendaciones automáticas de optimización
- [ ] Integración con ERPs (SAP, Oracle)
- [ ] App móvil para aprobaciones
- [ ] Tableros configurables por usuario

### Fase 5 (6-12 meses)
- [ ] Análisis de riesgo crediticio
- [ ] Scoring de proveedores/clientes
- [ ] Optimización de capital de trabajo
- [ ] Integración con fondos de inversión
- [ ] Marketplace financiero (factoraje, créditos)
