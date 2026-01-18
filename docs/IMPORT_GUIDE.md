# Plantilla de Importación de Transacciones

## Instrucciones de Uso

Este documento describe cómo usar la plantilla Excel para importar transacciones masivamente.

## Formato del Archivo Excel

### Columnas (en orden)

| Columna | Nombre | Tipo | Descripción | Ejemplo |
|---------|--------|------|-------------|----------|
| A | bank_account_id | UUID | ID de la cuenta bancaria (obtener de Catálogos) | `550e8400-e29b-41d4-a716-446655440000` |
| B | concepto | Texto | Descripción de la transacción | `Pago a proveedor ABC` |
| C | monto | Número | Monto de la transacción (sin comas) | `15000.50` |
| D | tipo_transaccion | Texto | `ingreso` o `egreso` | `egreso` |
| E | fecha_transaccion | Fecha/Hora | Fecha y hora de la transacción | `2025-01-15 10:30:00` |
| F | es_real | Booleano | `true` o `false` - ¿Es transacción real? | `false` |
| G | es_proyeccion | Booleano | `true` o `false` - ¿Es proyección? | `true` |
| H | vendor_id | UUID (opcional) | ID del proveedor (para egresos) | `650e8400-e29b-41d4-a716-446655440001` |
| I | customer_id | UUID (opcional) | ID del cliente (para ingresos) | `750e8400-e29b-41d4-a716-446655440002` |

## Pasos para Importar

### 1. Preparar los IDs

Antes de llenar la plantilla, necesitas obtener los IDs:

**Cuentas Bancarias:**
1. Ve a Catálogos → Cuentas Bancarias
2. Copia el ID de la cuenta que deseas usar
3. Pégalo en la columna A

**Proveedores (opcional):**
1. Ve a Catálogos → Proveedores
2. Copia el ID del proveedor
3. Pégalo en la columna H (solo para egresos)

**Clientes (opcional):**
1. Ve a Catálogos → Clientes
2. Copia el ID del cliente
3. Pégalo en la columna I (solo para ingresos)

### 2. Llenar los Datos

**Ejemplo de Fila:**
```
bank_account_id: 123e4567-e89b-12d3-a456-426614174000
concepto: Pago renta oficina
monto: 50000.00
tipo_transaccion: egreso
fecha_transaccion: 2025-01-20 09:00:00
es_real: false
es_proyeccion: true
vendor_id: 234e5678-e89b-12d3-a456-426614174001
customer_id: (vacío)
```

### 3. Validar Datos

**Antes de importar, verifica:**
- [ ] Todos los IDs son válidos (formato UUID)
- [ ] Las fechas están en formato correcto
- [ ] Los montos son números positivos sin comas
- [ ] tipo_transaccion es exactamente "ingreso" o "egreso"
- [ ] es_real y es_proyeccion son "true" o "false"
- [ ] No hay filas vacías entre datos

### 4. Importar

1. Guarda el archivo Excel
2. Ve a Transacciones en la aplicación
3. Haz clic en "Importar Excel"
4. Selecciona tu archivo
5. Espera la confirmación
6. Revisa el resultado:
   - Número de transacciones importadas
   - Lista de errores (si hay)

## Ejemplos de Transacciones

### Ejemplo 1: Ingreso Proyectado (Cobro a Cliente)
```
bank_account_id: 123e4567-e89b-12d3-a456-426614174000
concepto: Cobro factura 001 - Cliente XYZ
monto: 125000.00
tipo_transaccion: ingreso
fecha_transaccion: 2025-01-25 14:00:00
es_real: false
es_proyeccion: true
vendor_id: 
customer_id: 345e6789-e89b-12d3-a456-426614174003
```

### Ejemplo 2: Egreso Real (Pago a Proveedor)
```
bank_account_id: 123e4567-e89b-12d3-a456-426614174000
concepto: Pago servicios enero
monto: 35000.00
tipo_transaccion: egreso
fecha_transaccion: 2025-01-15 10:30:00
es_real: true
es_proyeccion: false
vendor_id: 234e5678-e89b-12d3-a456-426614174001
customer_id: 
```

### Ejemplo 3: Egreso Proyectado (Nómina)
```
bank_account_id: 123e4567-e89b-12d3-a456-426614174000
concepto: Nómina quincena 2
monto: 450000.00
tipo_transaccion: egreso
fecha_transaccion: 2025-02-01 08:00:00
es_real: false
es_proyeccion: true
vendor_id: 
customer_id: 
```

## Consejos y Mejores Prácticas

### Organización
- Separa transacciones reales de proyecciones en hojas diferentes
- Usa nombres descriptivos en el concepto
- Mantén un archivo maestro con todos los IDs

### Fechas
- Las transacciones deben caer dentro de las 13 semanas del sistema
- Usa fechas futuras para proyecciones
- Usa fechas pasadas solo para transacciones reales

### Validación
- Importa primero un pequeño lote de prueba (5-10 registros)
- Verifica en la aplicación que se importaron correctamente
- Luego procede con el archivo completo

### Errores Comunes

**Error: "Cuenta bancaria no encontrada"**
- Solución: Verifica que el bank_account_id existe y pertenece a tu empresa

**Error: "No se encontró semana de cashflow para la fecha"**
- Solución: La fecha está fuera del rango de 13 semanas. Ajusta la fecha.

**Error: "Formato de fecha inválido"**
- Solución: Usa formato YYYY-MM-DD HH:MM:SS exactamente

**Error: "Tipo de transacción inválido"**
- Solución: Debe ser exactamente "ingreso" o "egreso" (minúsculas)

## Plantilla Descargable

Puedes crear tu plantilla Excel con estos encabezados en la primera fila:

```
bank_account_id | concepto | monto | tipo_transaccion | fecha_transaccion | es_real | es_proyeccion | vendor_id | customer_id
```

Guarda como: `transacciones_template.xlsx`

## Soporte

Si tienes problemas con la importación:
1. Revisa los errores reportados
2. Valida tu archivo contra esta guía
3. Intenta con un archivo más pequeño
4. Contacta al administrador del sistema
