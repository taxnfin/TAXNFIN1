"""
TaxnFin — Cashflow Sync Service
Jala movimientos conciliados de cualquier ERP/contabilidad conectado
y los mapea al modelo de flujo de efectivo de 13 semanas.

ERPs soportados:
  - Contalink  ✅ activo
  - Alegra     ✅ activo
  - CONTPAQi   🔜 próximamente (import XML/CSV)
  - Odoo       🔜 próximamente (API REST)
  - QuickBooks 🔜 próximamente (OAuth2)
  - SAP B1     🔜 próximamente (Service Layer)
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
import logging

from core.database import db
from core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cashflow-sync", tags=["Cashflow Sync"])


# ══════════════════════════════════════════════════════════════════════
# CATÁLOGO DE CATEGORÍAS DEFAULT
# ══════════════════════════════════════════════════════════════════════

DEFAULT_CATEGORIES = [
    # ── INGRESOS ──────────────────────────────────────────────────────
    {"code": "ING-001", "nombre": "Ventas de productos",         "tipo": "ingreso",  "subtipo": "operativo",  "icon": "📦", "color": "#22C55E"},
    {"code": "ING-002", "nombre": "Prestación de servicios",     "tipo": "ingreso",  "subtipo": "operativo",  "icon": "🛠️", "color": "#22C55E"},
    {"code": "ING-003", "nombre": "Honorarios profesionales",    "tipo": "ingreso",  "subtipo": "operativo",  "icon": "💼", "color": "#22C55E"},
    {"code": "ING-004", "nombre": "Arrendamiento",               "tipo": "ingreso",  "subtipo": "operativo",  "icon": "🏢", "color": "#22C55E"},
    {"code": "ING-005", "nombre": "Cobro de anticipos",          "tipo": "ingreso",  "subtipo": "operativo",  "icon": "💰", "color": "#22C55E"},
    {"code": "ING-006", "nombre": "Devoluciones recibidas",      "tipo": "ingreso",  "subtipo": "operativo",  "icon": "↩️", "color": "#22C55E"},
    {"code": "ING-007", "nombre": "Intereses cobrados",          "tipo": "ingreso",  "subtipo": "financiero", "icon": "📈", "color": "#3B82F6"},
    {"code": "ING-008", "nombre": "Dividendos recibidos",        "tipo": "ingreso",  "subtipo": "financiero", "icon": "💹", "color": "#3B82F6"},
    {"code": "ING-009", "nombre": "Venta de activos",            "tipo": "ingreso",  "subtipo": "inversion",  "icon": "🏗️", "color": "#8B5CF6"},
    {"code": "ING-010", "nombre": "Préstamos recibidos",         "tipo": "ingreso",  "subtipo": "financiero", "icon": "🏦", "color": "#3B82F6"},
    {"code": "ING-011", "nombre": "Aportaciones de socios",      "tipo": "ingreso",  "subtipo": "financiero", "icon": "🤝", "color": "#3B82F6"},
    {"code": "ING-099", "nombre": "Otros ingresos",              "tipo": "ingreso",  "subtipo": "otro",       "icon": "➕", "color": "#22C55E"},

    # ── EGRESOS OPERATIVOS ────────────────────────────────────────────
    {"code": "EGR-001", "nombre": "Nómina y salarios",           "tipo": "egreso",   "subtipo": "operativo",  "icon": "👥", "color": "#EF4444"},
    {"code": "EGR-002", "nombre": "IMSS / INFONAVIT",            "tipo": "egreso",   "subtipo": "operativo",  "icon": "🏥", "color": "#EF4444"},
    {"code": "EGR-003", "nombre": "ISR (pago provisional)",      "tipo": "egreso",   "subtipo": "fiscal",     "icon": "🏛️", "color": "#F59E0B"},
    {"code": "EGR-004", "nombre": "IVA (pago mensual)",          "tipo": "egreso",   "subtipo": "fiscal",     "icon": "🏛️", "color": "#F59E0B"},
    {"code": "EGR-005", "nombre": "Renta / arrendamiento",       "tipo": "egreso",   "subtipo": "operativo",  "icon": "🏢", "color": "#EF4444"},
    {"code": "EGR-006", "nombre": "Proveedores de materia prima","tipo": "egreso",   "subtipo": "operativo",  "icon": "📦", "color": "#EF4444"},
    {"code": "EGR-007", "nombre": "Servicios (luz, agua, gas)",  "tipo": "egreso",   "subtipo": "operativo",  "icon": "⚡", "color": "#EF4444"},
    {"code": "EGR-008", "nombre": "Telefonía e internet",        "tipo": "egreso",   "subtipo": "operativo",  "icon": "📱", "color": "#EF4444"},
    {"code": "EGR-009", "nombre": "Publicidad y marketing",      "tipo": "egreso",   "subtipo": "operativo",  "icon": "📣", "color": "#EF4444"},
    {"code": "EGR-010", "nombre": "Honorarios externos",         "tipo": "egreso",   "subtipo": "operativo",  "icon": "💼", "color": "#EF4444"},
    {"code": "EGR-011", "nombre": "Viáticos y gastos de viaje",  "tipo": "egreso",   "subtipo": "operativo",  "icon": "✈️", "color": "#EF4444"},
    {"code": "EGR-012", "nombre": "Seguros y fianzas",           "tipo": "egreso",   "subtipo": "operativo",  "icon": "🛡️", "color": "#EF4444"},
    {"code": "EGR-013", "nombre": "Mantenimiento y reparaciones","tipo": "egreso",   "subtipo": "operativo",  "icon": "🔧", "color": "#EF4444"},
    {"code": "EGR-014", "nombre": "Papelería y consumibles",     "tipo": "egreso",   "subtipo": "operativo",  "icon": "📄", "color": "#EF4444"},
    {"code": "EGR-015", "nombre": "Software y suscripciones",    "tipo": "egreso",   "subtipo": "operativo",  "icon": "💻", "color": "#EF4444"},
    # ── EGRESOS FINANCIEROS ───────────────────────────────────────────
    {"code": "EGR-016", "nombre": "Pago de crédito bancario",    "tipo": "egreso",   "subtipo": "financiero", "icon": "🏦", "color": "#F59E0B"},
    {"code": "EGR-017", "nombre": "Intereses pagados",           "tipo": "egreso",   "subtipo": "financiero", "icon": "📉", "color": "#F59E0B"},
    {"code": "EGR-018", "nombre": "Comisiones bancarias",        "tipo": "egreso",   "subtipo": "financiero", "icon": "🏧", "color": "#F59E0B"},
    {"code": "EGR-019", "nombre": "Pago de dividendos",          "tipo": "egreso",   "subtipo": "financiero", "icon": "💸", "color": "#F59E0B"},
    # ── EGRESOS INVERSIÓN ─────────────────────────────────────────────
    {"code": "EGR-020", "nombre": "Compra de activo fijo",       "tipo": "egreso",   "subtipo": "inversion",  "icon": "🏗️", "color": "#8B5CF6"},
    {"code": "EGR-021", "nombre": "Depósito en garantía",        "tipo": "egreso",   "subtipo": "inversion",  "icon": "🔐", "color": "#8B5CF6"},
    {"code": "EGR-099", "nombre": "Otros egresos",               "tipo": "egreso",   "subtipo": "otro",       "icon": "➖", "color": "#EF4444"},
]


# ══════════════════════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════════════════════

class CategoryCreate(BaseModel):
    nombre:   str
    tipo:     str          # "ingreso" | "egreso"
    subtipo:  str = "operativo"
    icon:     Optional[str] = "📌"
    color:    Optional[str] = "#64748B"

class CategoryUpdate(BaseModel):
    nombre:   Optional[str] = None
    subtipo:  Optional[str] = None
    icon:     Optional[str] = None
    color:    Optional[str] = None
    activa:   Optional[bool] = None


# ══════════════════════════════════════════════════════════════════════
# CATEGORÍAS — CRUD
# ══════════════════════════════════════════════════════════════════════

@router.get("/categories")
async def list_categories(
    tipo: Optional[str] = None,
    current_user: Dict = Depends(get_current_user)
):
    """
    Lista categorías de la empresa.
    Mezcla: defaults del sistema + las que el cliente haya creado/personalizado.
    """
    company_id = current_user["company_id"]

    # Categorías custom de la empresa
    query = {"company_id": company_id, "activa": True}
    if tipo:
        query["tipo"] = tipo
    custom = await db.cashflow_categories.find(query, {"_id": 0}).to_list(200)
    custom_codes = {c["code"] for c in custom}

    # Agregar defaults que no hayan sido sobreescritos
    result = list(custom)
    for cat in DEFAULT_CATEGORIES:
        if cat["code"] not in custom_codes:
            if not tipo or cat["tipo"] == tipo:
                result.append({**cat, "company_id": company_id, "is_default": True, "activa": True})

    # Ordenar: ingresos primero, luego egresos, por code
    result.sort(key=lambda x: (0 if x["tipo"] == "ingreso" else 1, x["code"]))
    return result


@router.post("/categories")
async def create_category(
    data: CategoryCreate,
    current_user: Dict = Depends(get_current_user)
):
    """El cliente agrega una categoría personalizada"""
    company_id = current_user["company_id"]

    if data.tipo not in ("ingreso", "egreso"):
        raise HTTPException(status_code=400, detail="tipo debe ser 'ingreso' o 'egreso'")

    # Generar code único
    prefix = "ING" if data.tipo == "ingreso" else "EGR"
    count = await db.cashflow_categories.count_documents({"company_id": company_id})
    code = f"{prefix}-C{str(count + 1).zfill(3)}"

    doc = {
        "code":       code,
        "company_id": company_id,
        "nombre":     data.nombre.strip(),
        "tipo":       data.tipo,
        "subtipo":    data.subtipo,
        "icon":       data.icon or "📌",
        "color":      data.color or ("#22C55E" if data.tipo == "ingreso" else "#EF4444"),
        "is_default": False,
        "activa":     True,
        "created_by": current_user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.cashflow_categories.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/categories/{code}")
async def update_category(
    code: str,
    data: CategoryUpdate,
    current_user: Dict = Depends(get_current_user)
):
    """Editar o desactivar una categoría"""
    company_id = current_user["company_id"]
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="Nada que actualizar")

    # Si es default, crear copia custom antes de editar
    existing = await db.cashflow_categories.find_one({"code": code, "company_id": company_id})
    if not existing:
        # Buscar en defaults
        default = next((c for c in DEFAULT_CATEGORIES if c["code"] == code), None)
        if not default:
            raise HTTPException(status_code=404, detail="Categoría no encontrada")
        # Crear override
        doc = {**default, "company_id": company_id, "is_default": False,
               "activa": True, "created_at": datetime.now(timezone.utc).isoformat()}
        doc.update(update)
        await db.cashflow_categories.insert_one(doc)
        doc.pop("_id", None)
        return doc

    await db.cashflow_categories.update_one(
        {"code": code, "company_id": company_id},
        {"$set": {**update, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    updated = await db.cashflow_categories.find_one(
        {"code": code, "company_id": company_id}, {"_id": 0}
    )
    return updated


@router.delete("/categories/{code}")
async def delete_category(code: str, current_user: Dict = Depends(get_current_user)):
    """Desactivar categoría (soft delete)"""
    company_id = current_user["company_id"]
    await db.cashflow_categories.update_one(
        {"code": code, "company_id": company_id},
        {"$set": {"activa": False}}
    )
    return {"success": True, "message": "Categoría desactivada"}


# ══════════════════════════════════════════════════════════════════════
# SYNC ENGINE — Interface base para ERPs
# ══════════════════════════════════════════════════════════════════════

class ERPSyncResult:
    """Resultado estándar de sync para cualquier ERP"""
    def __init__(self, erp_name: str):
        self.erp_name    = erp_name
        self.ingresos    = []   # [{fecha, monto, descripcion, referencia, categoria_code}]
        self.egresos     = []
        self.errors      = []
        self.period      = None

    def to_dict(self):
        return {
            "erp":       self.erp_name,
            "period":    self.period,
            "ingresos":  len(self.ingresos),
            "egresos":   len(self.egresos),
            "errors":    self.errors,
        }


async def sync_contalink_to_cashflow(
    company_id: str,
    periodo: str,           # "2026-04"
    integration: dict,
) -> ERPSyncResult:
    """
    Jala movimientos conciliados de Contalink y los mapea al cashflow.
    Usa la balanza de comprobación para identificar cuentas de bancos (1-1-*).
    """
    result = ERPSyncResult("contalink")
    result.period = periodo

    try:
        year, month = periodo.split("-")
        start = f"{year}-{month}-01"
        # Último día del mes
        import calendar
        last_day = calendar.monthrange(int(year), int(month))[1]
        end = f"{year}-{month}-{last_day:02d}"

        from services.contalink import ContalinkClient
        api_key = integration.get("credentials", {}).get("api_key", "")
        client  = ContalinkClient(api_key)

        # 1. Obtener balanza del período
        trial_balance = await client.get_trial_balance(start, end)
        if not trial_balance.get("status"):
            result.errors.append(f"Error obteniendo balanza: {trial_balance.get('message')}")
            return result

        accounts = trial_balance.get("data", {}).get("accounts", [])

        # 2. Filtrar cuentas bancarias (1-1-*) y cuentas de ingresos/egresos
        for account in accounts:
            account_num = str(account.get("account_number", ""))
            name        = account.get("account_name", "")
            debit       = float(account.get("period_debit", 0) or 0)
            credit      = float(account.get("period_credit", 0) or 0)

            # Cuentas de ingreso (4-*): crédito = ingreso
            if account_num.startswith("4") and credit > 0:
                result.ingresos.append({
                    "fecha":       end,
                    "monto":       credit,
                    "descripcion": name,
                    "referencia":  f"contalink-{account_num}-{periodo}",
                    "cuenta":      account_num,
                    "categoria_code": _map_account_to_category(account_num, "ingreso"),
                    "source":      "contalink",
                })

            # Cuentas de egreso (5-*, 6-*): débito = egreso
            elif account_num.startswith(("5", "6")) and debit > 0:
                result.egresos.append({
                    "fecha":       end,
                    "monto":       debit,
                    "descripcion": name,
                    "referencia":  f"contalink-{account_num}-{periodo}",
                    "cuenta":      account_num,
                    "categoria_code": _map_account_to_category(account_num, "egreso"),
                    "source":      "contalink",
                })

    except Exception as e:
        result.errors.append(str(e))
        logger.error(f"sync_contalink_to_cashflow error: {e}")

    return result


async def sync_alegra_to_cashflow(
    company_id: str,
    periodo: str,
    integration: dict,
) -> ERPSyncResult:
    """
    Jala facturas cobradas (ingresos) y facturas pagadas (egresos) de Alegra
    para el período indicado y los mapea al cashflow.
    """
    result = ERPSyncResult("alegra")
    result.period = periodo

    try:
        year, month = periodo.split("-")
        start = f"{year}-{month}-01"
        import calendar
        last_day = calendar.monthrange(int(year), int(month))[1]
        end = f"{year}-{month}-{last_day:02d}"

        email     = integration.get("credentials", {}).get("email", "")
        api_token = integration.get("credentials", {}).get("api_token", "")
        if not email or not api_token:
            result.errors.append("Credenciales de Alegra incompletas")
            return result

        import httpx, base64
        auth = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type":  "application/json",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            # Ingresos — facturas emitidas cobradas
            inv_res = await client.get(
                "https://api.alegra.com/api/v1/invoices",
                headers=headers,
                params={
                    "start":   0,
                    "limit":   200,
                    "order":   "date-asc",
                    "datege":  start,
                    "datele":  end,
                    "status":  "closed",  # cobradas
                }
            )
            if inv_res.status_code == 200:
                for inv in inv_res.json():
                    monto = float(inv.get("total", 0))
                    if monto > 0:
                        result.ingresos.append({
                            "fecha":       inv.get("date", end),
                            "monto":       monto,
                            "descripcion": f"Factura {inv.get('numberTemplate', {}).get('number', '')} - {inv.get('client', {}).get('name', '')}",
                            "referencia":  f"alegra-inv-{inv.get('id')}-{periodo}",
                            "categoria_code": "ING-001",
                            "source":      "alegra",
                        })

            # Egresos — facturas de compra pagadas
            bill_res = await client.get(
                "https://api.alegra.com/api/v1/bills",
                headers=headers,
                params={
                    "start":   0,
                    "limit":   200,
                    "datege":  start,
                    "datele":  end,
                    "status":  "closed",
                }
            )
            if bill_res.status_code == 200:
                for bill in bill_res.json():
                    monto = float(bill.get("total", 0))
                    if monto > 0:
                        result.egresos.append({
                            "fecha":       bill.get("date", end),
                            "monto":       monto,
                            "descripcion": f"Compra {bill.get('numberTemplate', {}).get('number', '')} - {bill.get('vendor', {}).get('name', '')}",
                            "referencia":  f"alegra-bill-{bill.get('id')}-{periodo}",
                            "categoria_code": "EGR-006",
                            "source":      "alegra",
                        })

    except Exception as e:
        result.errors.append(str(e))
        logger.error(f"sync_alegra_to_cashflow error: {e}")

    return result


# Placeholder para futuros ERPs — misma interfaz
async def sync_contpaqi_to_cashflow(company_id, periodo, integration) -> ERPSyncResult:
    """CONTPAQi — próximamente vía import XML/CSV de pólizas"""
    result = ERPSyncResult("contpaqi")
    result.errors.append("CONTPAQi estará disponible próximamente. Por ahora usa importación de Excel.")
    return result

async def sync_odoo_to_cashflow(company_id, periodo, integration) -> ERPSyncResult:
    """Odoo — próximamente vía API REST JSON-RPC"""
    result = ERPSyncResult("odoo")
    result.errors.append("Odoo estará disponible próximamente.")
    return result

async def sync_quickbooks_to_cashflow(company_id, periodo, integration) -> ERPSyncResult:
    """QuickBooks — próximamente vía OAuth2"""
    result = ERPSyncResult("quickbooks")
    result.errors.append("QuickBooks estará disponible próximamente.")
    return result


# Mapa de ERPs disponibles
ERP_SYNC_MAP = {
    "contalink":  sync_contalink_to_cashflow,
    "alegra":     sync_alegra_to_cashflow,
    "contpaqi":   sync_contpaqi_to_cashflow,
    "odoo":       sync_odoo_to_cashflow,
    "quickbooks": sync_quickbooks_to_cashflow,
}


def _map_account_to_category(account_num: str, tipo: str) -> str:
    """Mapeo simple de número de cuenta contable → categoría de cashflow"""
    if tipo == "ingreso":
        if account_num.startswith("401"): return "ING-001"
        if account_num.startswith("402"): return "ING-002"
        if account_num.startswith("403"): return "ING-003"
        return "ING-099"
    else:
        if account_num.startswith("501"): return "EGR-001"  # Nómina
        if account_num.startswith("502"): return "EGR-005"  # Renta
        if account_num.startswith("503"): return "EGR-006"  # Proveedores
        if account_num.startswith("510"): return "EGR-003"  # Impuestos
        if account_num.startswith("601"): return "EGR-016"  # Crédito
        return "EGR-099"


# ══════════════════════════════════════════════════════════════════════
# ENDPOINTS DE SYNC
# ══════════════════════════════════════════════════════════════════════

@router.post("/sync/{erp_name}")
async def sync_erp_to_cashflow(
    erp_name: str,
    periodo: str,                  # Query param: "2026-04"
    current_user: Dict = Depends(get_current_user)
):
    """
    Sincroniza movimientos de cualquier ERP conectado al cashflow.
    erp_name: contalink | alegra | contpaqi | odoo | quickbooks
    periodo:  YYYY-MM
    """
    if erp_name not in ERP_SYNC_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"ERP '{erp_name}' no reconocido. Disponibles: {list(ERP_SYNC_MAP.keys())}"
        )

    company_id = current_user["company_id"]

    # Buscar integración activa
    integration = await db.integrations.find_one({
        "company_id":       company_id,
        "integration_type": erp_name,
        "is_active":        True,
    })
    if not integration:
        raise HTTPException(
            status_code=404,
            detail=f"No tienes {erp_name} conectado. Ve a Admin → Integraciones."
        )

    # Ejecutar sync del ERP correspondiente
    sync_fn = ERP_SYNC_MAP[erp_name]
    result  = await sync_fn(company_id, periodo, integration)

    if result.errors and not result.ingresos and not result.egresos:
        raise HTTPException(status_code=400, detail=result.errors[0])

    # Guardar movimientos en cashflow_movements
    saved = 0
    for mov in result.ingresos + result.egresos:
        # Upsert por referencia para evitar duplicados
        existing = await db.cashflow_movements.find_one({
            "company_id": company_id,
            "referencia": mov["referencia"],
        })
        if not existing:
            await db.cashflow_movements.insert_one({
                **mov,
                "company_id": company_id,
                "periodo":    periodo,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            saved += 1

    return {
        "success":  True,
        "erp":      erp_name,
        "periodo":  periodo,
        "ingresos": len(result.ingresos),
        "egresos":  len(result.egresos),
        "saved":    saved,
        "errors":   result.errors,
        "message":  f"Sincronizado: {len(result.ingresos)} ingresos + {len(result.egresos)} egresos desde {erp_name}.",
    }


@router.post("/sync/all")
async def sync_all_erps(
    periodo: str,
    current_user: Dict = Depends(get_current_user)
):
    """Sincroniza TODOS los ERPs conectados en un solo llamado"""
    company_id = current_user["company_id"]
    integrations = await db.integrations.find(
        {"company_id": company_id, "is_active": True},
        {"_id": 0}
    ).to_list(20)

    results = []
    for integration in integrations:
        erp_name = integration.get("integration_type")
        if erp_name not in ERP_SYNC_MAP:
            continue
        sync_fn = ERP_SYNC_MAP[erp_name]
        result  = await sync_fn(company_id, periodo, integration)

        for mov in result.ingresos + result.egresos:
            existing = await db.cashflow_movements.find_one({
                "company_id": company_id,
                "referencia": mov["referencia"],
            })
            if not existing:
                await db.cashflow_movements.insert_one({
                    **mov,
                    "company_id": company_id,
                    "periodo":    periodo,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
        results.append(result.to_dict())

    return {"success": True, "periodo": periodo, "results": results}


@router.get("/movements")
async def get_cashflow_movements(
    periodo: Optional[str] = None,
    tipo: Optional[str] = None,
    source: Optional[str] = None,
    current_user: Dict = Depends(get_current_user)
):
    """Lista movimientos sincronizados del cashflow"""
    company_id = current_user["company_id"]
    query: dict = {"company_id": company_id}
    if periodo: query["periodo"] = periodo
    if tipo:    query["tipo"]    = tipo
    if source:  query["source"]  = source

    movs = await db.cashflow_movements.find(
        query, {"_id": 0}
    ).sort("fecha", -1).to_list(1000)

    total_ingresos = sum(m["monto"] for m in movs if m.get("tipo") == "ingreso" or m in [m2 for m2 in movs if m2.get("categoria_code", "").startswith("ING")])
    total_egresos  = sum(m["monto"] for m in movs if m.get("categoria_code", "").startswith("EGR"))

    return {
        "movements":      movs,
        "total_ingresos": total_ingresos,
        "total_egresos":  total_egresos,
        "flujo_neto":     total_ingresos - total_egresos,
        "count":          len(movs),
    }


# ══════════════════════════════════════════════════════════════════════
# AUTO-CATEGORIZACIÓN CON IA (Claude API)
# ══════════════════════════════════════════════════════════════════════

class CategorizationOverride(BaseModel):
    """Para corrección manual de categoría de un pago"""
    payment_id:   str
    category_id:  str


@router.post("/auto-categorize")
async def auto_categorize_payments(
    current_user: Dict = Depends(get_current_user),
    limit: int = 100,
    solo_sin_categoria: bool = True,
):
    """
    Toma los pagos sin categoría y usa Claude API para asignarles
    la categoría más apropiada del catálogo.

    - limit: máximo de pagos a procesar por llamada (default 100)
    - solo_sin_categoria: si False, re-categoriza todos los pagos
    """
    import httpx, os, json

    company_id = current_user["company_id"]

    # 1. Cargar categorías disponibles
    custom_cats = await db.cashflow_categories.find(
        {"company_id": company_id, "activa": True}, {"_id": 0}
    ).to_list(200)
    custom_codes = {c["code"] for c in custom_cats}

    all_categories = list(custom_cats)
    for cat in DEFAULT_CATEGORIES:
        if cat["code"] not in custom_codes:
            all_categories.append(cat)

    cat_list_text = "\n".join(
        f'- id="{cat["code"]}" | nombre="{cat["nombre"]}" | tipo={cat["tipo"]}'
        for cat in all_categories
    )

    # 2. Cargar payments a categorizar
    query: dict = {"company_id": company_id}
    if solo_sin_categoria:
        query["$or"] = [
            {"category_id": None},
            {"category_id": {"$exists": False}},
        ]

    payments_raw = await db.payments.find(query, {"_id": 0}).limit(limit).to_list(limit)

    if not payments_raw:
        return {"success": True, "message": "No hay pagos para categorizar", "updated": 0}

    # 3. Construir prompt para Claude
    payments_text = "\n".join(
        f'[{i}] id="{p["id"]}" | tipo={p.get("tipo","?")} | '
        f'concepto="{p.get("concepto","")}" | '
        f'beneficiario="{p.get("beneficiario","")}" | '
        f'monto={p.get("monto",0)} {p.get("moneda","MXN")}'
        for i, p in enumerate(payments_raw)
    )

    prompt = f"""Eres un experto en contabilidad y finanzas mexicanas.
Tu tarea es categorizar movimientos de flujo de efectivo de una empresa mexicana.

CATEGORÍAS DISPONIBLES:
{cat_list_text}

MOVIMIENTOS A CATEGORIZAR:
{payments_text}

INSTRUCCIONES:
- Para cada movimiento, elige la categoría más apropiada de la lista.
- Los cobros (tipo=cobro) son ingresos → usa categorías de tipo ingreso.
- Los pagos (tipo=pago) son egresos → usa categorías de tipo egreso.
- Si el concepto menciona "Cobranza" o es de un cliente → ING-001 (Ventas de productos).
- Si el beneficiario es un banco → EGR-018 (Comisiones bancarias).
- Si el concepto menciona nómina, salarios, IMSS → EGR-001 o EGR-002.
- Si no puedes determinar → ING-099 para ingresos, EGR-099 para egresos.

Responde ÚNICAMENTE con un JSON array sin texto adicional ni backticks:
[{{"id": "payment_id", "category_code": "ING-001"}}, ...]
"""

    # 4. Llamar a Claude API
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY no configurada en Railway")

    try:
        async with httpx.AsyncClient(timeout=60) as http:
            res = await http.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            res.raise_for_status()
            data = res.json()
            raw_text = data["content"][0]["text"].strip()
    except Exception as e:
        logger.error(f"auto_categorize Claude API error: {e}")
        raise HTTPException(status_code=500, detail=f"Error llamando a Claude API: {str(e)}")

    # 5. Parsear respuesta
    try:
        # Limpiar posibles backticks
        clean = raw_text.replace("```json", "").replace("```", "").strip()
        assignments = json.loads(clean)
    except Exception as e:
        logger.error(f"auto_categorize JSON parse error: {e} — raw: {raw_text[:500]}")
        raise HTTPException(status_code=500, detail=f"Error parseando respuesta de IA: {str(e)}")

    # 6. Construir mapa code → category doc
    cat_by_code = {c["code"]: c for c in all_categories}

    # 7. Actualizar payments en MongoDB
    updated = 0
    errors = []
    results = []

    for assignment in assignments:
        payment_id   = assignment.get("id")
        category_code = assignment.get("category_code")

        if not payment_id or not category_code:
            continue

        cat_doc = cat_by_code.get(category_code)
        if not cat_doc:
            errors.append(f"Código desconocido: {category_code} para payment {payment_id}")
            continue

        try:
            await db.payments.update_one(
                {"id": payment_id, "company_id": company_id},
                {"$set": {
                    "category_id":   category_code,
                    "category_name": cat_doc["nombre"],
                    "categorized_by": "ai",
                    "categorized_at": datetime.now(timezone.utc).isoformat(),
                }}
            )
            updated += 1
            results.append({
                "payment_id":   payment_id,
                "category_code": category_code,
                "category_name": cat_doc["nombre"],
            })
        except Exception as e:
            errors.append(f"Error actualizando {payment_id}: {str(e)}")

    logger.info(f"auto_categorize: company={company_id} processed={len(payments_raw)} updated={updated} errors={len(errors)}")

    return {
        "success":   True,
        "processed": len(payments_raw),
        "updated":   updated,
        "errors":    errors,
        "results":   results,
    }


@router.post("/recategorize")
async def recategorize_payment(
    data: CategorizationOverride,
    current_user: Dict = Depends(get_current_user),
):
    """
    Corrección manual de categoría para un pago específico.
    El usuario puede corregir lo que asignó la IA.
    """
    company_id = current_user["company_id"]

    # Buscar categoría
    cat_doc = await db.cashflow_categories.find_one(
        {"code": data.category_id, "company_id": company_id}, {"_id": 0}
    )
    if not cat_doc:
        # Buscar en defaults
        cat_doc = next((c for c in DEFAULT_CATEGORIES if c["code"] == data.category_id), None)
    if not cat_doc:
        raise HTTPException(status_code=404, detail=f"Categoría '{data.category_id}' no encontrada")

    result = await db.payments.update_one(
        {"id": data.payment_id, "company_id": company_id},
        {"$set": {
            "category_id":   data.category_id,
            "category_name": cat_doc["nombre"],
            "categorized_by": "manual",
            "categorized_at": datetime.now(timezone.utc).isoformat(),
        }}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    return {
        "success":       True,
        "payment_id":    data.payment_id,
        "category_code": data.category_id,
        "category_name": cat_doc["nombre"],
    }


@router.get("/categorization-status")
async def get_categorization_status(
    current_user: Dict = Depends(get_current_user),
):
    """Muestra cuántos pagos están categorizados vs sin categoría"""
    company_id = current_user["company_id"]

    total = await db.payments.count_documents({"company_id": company_id})
    sin_cat = await db.payments.count_documents({
        "company_id": company_id,
        "$or": [{"category_id": None}, {"category_id": {"$exists": False}}]
    })
    por_ia = await db.payments.count_documents({
        "company_id": company_id, "categorized_by": "ai"
    })
    manual = await db.payments.count_documents({
        "company_id": company_id, "categorized_by": "manual"
    })

    return {
        "total":           total,
        "categorizados":   total - sin_cat,
        "sin_categoria":   sin_cat,
        "por_ia":          por_ia,
        "manual":          manual,
        "pct_completado":  round((total - sin_cat) / max(total, 1) * 100, 1),
    }
