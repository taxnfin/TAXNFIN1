# Resumen Sesión TaxnFin — 27 Junio 2026

## FIXES COMPLETADOS HOY (commits en main)

### Alejandro Contreras — RESUELTO ✅
- **Bug:** `role: 'user'` no existía en UserRole enum → crash 500 en login
- **Fix:** Agregado `USER = "user"` a `backend/models/enums.py` (commit `e9e464c`)
- **Acceso actual:** rol=contador, empresa HEALLY NUTRITION visible en selector
- **Empresa ALSTEC:** fantasma en MongoDB, pendiente eliminar (company_id: `e0351a9e-992f-41fd-9df5-75033e3cd709`)

### Dashboard Ortech — Fixes aplicados
- `None==None` bug en `venta_usd_id` → todos los pagos sin categoría iban a venta_usd (commit `aff275c`)
- Dashboard Alegra incluye todos los pagos completados, no solo conciliados (commit `79b806c`)
- Saldo inicial ajustado con pagos entre `fecha_saldo` y `start_monday` (commit `a7bfe27`)
- Burn rate usa solo semanas con actividad real (commit `a7bfe27`)
- Filtro de traspasos USD↔MXN excluye "retiro/deposito por operacion cambios" (commit `c010a6e`)

### Usuarios / Gestión
- `sessionGet` lee sessionStorage + localStorage fallback → Usuarios.jsx ya no muestra "sin permisos" (commit `9a67d1f`)
- Invitar usuario ya registrado agrega empresas en lugar de rechazar (commit `0318423`)
- Email bienvenida con credenciales vía Resend al invitar (commit `352ee5f`)
- Endpoint `POST /usuarios/{id}/reset-password` para CFO (commit `c2b59a3`)
- Endpoint `POST /auth/admin-reset-password` genera link directo (commit `bb5acb9`)
- Endpoint `PATCH /bank-accounts/{id}/saldo` para actualizar saldo sin requerir todos los campos (commit `8a97ece`)

## PROBLEMA PENDIENTE — Dashboard Ortech (CRÍTICO)

### Síntoma
- Saldo Inicial siempre muestra $387,509 (saldo de ene/feb) sin importar el mes seleccionado
- Saldo Final Proyectado = Saldo Inicial (no cambia)
- Flujo Promedio incorrecto

### Diagnóstico raíz
Los 1,900 pagos de Ortech están en `db.payments` con `fuente: 'bank_transaction'` y `estatus: 'completado'`.
El modelo del dashboard SÍ los toma, pero el `saldo_bancos_mxn` (base del modelo) siempre parte del saldo estático en BD.
El `adjusted_balance` (fix de hoy) debería ajustar el saldo con pagos entre `fecha_saldo` y `start_monday`, pero Railway tardó en desplegar y no se verificó si funcionó.

### Saldos verificados con estados de cuenta BanBajío
| Fecha | BanBajío MXN | BanBajío USD | Total MXN aprox |
|-------|-------------|-------------|-----------------|
| 01-ene-2026 (inicio) | $25,180.98 | $16,286.71 | $305,849 |
| 31-ene-2026 | $96,512.44 | $15,853.83 | $387,509 |
| 28-feb-2026 | $132,865.17 | $30,887.28 | $~670,000 |
| 30-may-2026 | $65,149.37 | $10,207.71 | $~243,000 |

### Saldos actuales en MongoDB
- BAJIO MXN (id: `908fd8ae-657f-4b24-8138-46a606be60c2`): $96,512.44 al 31-ene ← pendiente actualizar a 28-feb
- BAJIO USD (id: `9090c0a2-ce48-4fe1-894b-405af275cb50`): $15,853.83 al 31-ene ← pendiente actualizar a 28-feb

### Primer paso en chat nuevo
1. Verificar si el `adjusted_balance` fix está funcionando (Railway deployment `79b806c`)
2. Actualizar saldos a 28-feb y verificar si el dashboard de marzo cuadra
3. Si no cuadra → revisar por qué `week_payments` para feb/mar está vacío
4. Conseguir estados de cuenta marzo/abril/mayo para llegar a saldo más reciente

## PENDIENTES MENORES

- Empresa ALSTEC fantasma → eliminar de MongoDB para Alejandro
- Capital $0 en Balance General Contalink (Heally)
- RFC "PENDIENTE" en Board Report
- `OPENEXCHANGE_APP_ID` en Railway (CHF/JPY)
- Filtro de fechas en Cobranza y Pagos sigue sin funcionar
- Ícono "ojito" para mostrar/ocultar contraseña en login
- SAT CIEC persona física VICL7103077N8 (login ✅, campos fecha ❌)
- Sincronización bancaria → implementar Syncfy (reemplazo de Belvo)

## IDs importantes MongoDB
- Ortech company_id: `89cda61e-...` (Alegra)
- Heally company_id: `a9241bc8-ea86-4c3f-97f6-b8e802b1354e` (Contalink)
- Alejandro user_id: `ff428580-323f-4519-a7cc-222abc0f0d0e`
- ALSTEC (fantasma) company_id: `e0351a9e-992f-41fd-9df5-75033e3cd709`

## Stack
- Frontend: taxnfin/TAXNFIN1 → Vercel → cashflow.taxnfin.com
- Backend: Railway → taxnfin1-production.up.railway.app
- DB: MongoDB Atlas
- Layout correcto: Layout_5.js
