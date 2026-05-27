"""
TaxnFin — Endpoints de CxC y CxP desde Contalink
backend/routes/contalink_cxc_cxp.py
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, UploadFile, File
from typing import Dict, Optional
from datetime import date, datetime, timezone
from pydantic import BaseModel
import logging, io

from core.database import db
from core.auth import get_current_user, get_active_company_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contalink", tags=["Contalink CxC/CxP"])


# ══════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════

async def _get_client(company_id: str):
    integration = await db.integrations.find_one({
        "company_id": company_id, "type": "contalink", "active": True,
    })
    if not integration:
        raise HTTPException(status_code=404, detail="No tienes Contalink conectado.")
    api_key = integration.get("api_key", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key de Contalink no configurada.")
    from routes.contalink import ContalinkClient
    return ContalinkClient(api_key)


def _parse_currency(val) -> float:
    if val is None:
        return 0.0
    try:
        return float(str(val).replace("$", "").replace(",", "").strip() or 0)
    except Exception:
        return 0.0


def _parse_cxp_excel(content: bytes) -> dict:
    import xlrd
    wb = xlrd.open_workbook(file_contents=content)
    ws = wb.sheet_by_index(0)
    empresa = str(ws.cell_value(0, 0)).strip()
    rfc     = str(ws.cell_value(0, 1)).strip()
    fecha   = str(ws.cell_value(0, 2)).strip()
    proveedores = []
    total_por_vencer = total_1_30 = total_31_60 = total_61_90 = total_mas90 = total_general = 0.0
    for r in range(3, ws.nrows):
        nombre = str(ws.cell_value(r, 1)).strip()
        if not nombre or nombre.upper() in ("TOTAL", "PORCENTAJES", "PORCENTAJES TOTALES"):
            break
        por_vencer = _parse_currency(ws.cell_value(r, 3))
        d1_30      = _parse_currency(ws.cell_value(r, 4))
        d31_60     = _parse_currency(ws.cell_value(r, 5))
        d61_90     = _parse_currency(ws.cell_value(r, 6))
        mas90      = _parse_currency(ws.cell_value(r, 7))
        total      = _parse_currency(ws.cell_value(r, 8))
        if total == 0: continue
        if total < 0:
            total_general += total
            continue
        if mas90 > 0:    dias_vencido = 91
        elif d61_90 > 0: dias_vencido = 61
        elif d31_60 > 0: dias_vencido = 31
        elif d1_30 > 0:  dias_vencido = 1
        else:            dias_vencido = 0
        proveedores.append({"nombre": nombre, "proveedor_nombre": nombre, "proveedor_rfc": "",
            "saldo_pendiente": total, "por_vencer": por_vencer, "vencido_1_30": d1_30,
            "vencido_31_60": d31_60, "vencido_61_90": d61_90, "vencido_mas90": mas90,
            "total": total, "moneda": "MXN", "dias_vencido": dias_vencido,
            "fecha_emision": "", "fecha_vencimiento": "", "uuid": ""})
        total_por_vencer += por_vencer; total_1_30 += d1_30; total_31_60 += d31_60
        total_61_90 += d61_90; total_mas90 += mas90; total_general += total
    return {"empresa": empresa, "rfc": rfc, "fecha_reporte": fecha, "facturas": proveedores,
        "aging": {"corriente": round(total_por_vencer,2), "vencido_30": round(total_1_30,2),
            "vencido_60": round(total_31_60,2), "vencido_90": round(total_61_90,2),
            "vencido_mas90": round(total_mas90,2)},
        "total_pendiente": round(total_general,2), "num_proveedores": len(proveedores),
        "num_facturas": len(proveedores),
        "pct_vencido": round((total_1_30+total_31_60+total_61_90+total_mas90)/max(total_general,1)*100,1)}


def _parse_cxc_excel(content: bytes) -> dict:
    import xlrd
    wb = xlrd.open_workbook(file_contents=content)
    ws = wb.sheet_by_index(0)
    empresa = str(ws.cell_value(1, 3)).strip()
    rfc     = str(ws.cell_value(2, 3)).strip()
    clientes = []
    total_por_vencer = total_1_30 = total_31_60 = total_61_90 = 0.0
    total_91_120 = total_mas120 = total_general = 0.0
    for r in range(4, ws.nrows):
        nombre = str(ws.cell_value(r, 1)).strip()
        if not nombre or nombre.lower().startswith("total") or nombre.lower().startswith("porcentaje"):
            break
        por_vencer = _parse_currency(ws.cell_value(r, 3))
        d1_30      = _parse_currency(ws.cell_value(r, 5))
        d31_60     = _parse_currency(ws.cell_value(r, 7))
        d61_90     = _parse_currency(ws.cell_value(r, 8))
        d91_120    = _parse_currency(ws.cell_value(r, 10))
        mas120     = _parse_currency(ws.cell_value(r, 11))
        total      = _parse_currency(ws.cell_value(r, 12))
        if total == 0: continue
        # NC (total negativo): incluir como fila real para que aparezca en Aging
        # y el usuario pueda asignarle semana al cliente específico
        if mas120 > 0:    dias_vencido = 121
        elif d91_120 > 0: dias_vencido = 91
        elif d61_90 > 0:  dias_vencido = 61
        elif d31_60 > 0:  dias_vencido = 31
        elif d1_30 > 0:   dias_vencido = 1
        else:             dias_vencido = 0
        clientes.append({"nombre": nombre, "cliente_nombre": nombre, "cliente_rfc": "",
            "saldo_pendiente": total, "por_vencer": por_vencer, "vencido_1_30": d1_30,
            "vencido_31_60": d31_60, "vencido_61_90": d61_90, "vencido_91_120": d91_120,
            "vencido_mas120": mas120, "total": total, "moneda": "MXN",
            "dias_vencido": dias_vencido, "fecha_emision": "", "fecha_vencimiento": "", "uuid": ""})
        total_por_vencer += por_vencer; total_1_30 += d1_30; total_31_60 += d31_60
        total_61_90 += d61_90; total_91_120 += d91_120; total_mas120 += mas120; total_general += total
    return {"empresa": empresa, "rfc": rfc, "fecha_reporte": date.today().isoformat(),
        "facturas": clientes,
        "aging": {"corriente": round(total_por_vencer,2), "vencido_30": round(total_1_30,2),
            "vencido_60": round(total_31_60,2), "vencido_90": round(total_61_90,2),
            "vencido_mas90": round(total_91_120+total_mas120,2)},
        "total_pendiente": round(total_general,2), "num_clientes": len(clientes),
        "num_facturas": len(clientes),
        "pct_vencido": round((total_1_30+total_31_60+total_61_90+total_91_120+total_mas120)/max(total_general,1)*100,1)}


# ══════════════════════════════════════════════════════════════════════
# UPLOAD CxP / CxC EXCEL
# ══════════════════════════════════════════════════════════════════════

@router.post("/upload-cxp")
async def upload_cxp_excel(request: Request, file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="El archivo debe ser .xls o .xlsx")
    content = await file.read()
    try:
        result = _parse_cxp_excel(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo el archivo: {str(e)}")
    result.update({"cut_date": date.today().isoformat(), "source": "excel_upload",
        "fetched_at": datetime.now(timezone.utc).isoformat()})
    cache_key = f"cxp_{company_id}_latest"
    await db.contalink_cache.update_one({"key": cache_key},
        {"$set": {"key": cache_key, "data": result, "created_at": datetime.now(timezone.utc)}}, upsert=True)
    return result


@router.post("/upload-cxc")
async def upload_cxc_excel(request: Request, file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="El archivo debe ser .xls o .xlsx")
    content = await file.read()
    try:
        result = _parse_cxc_excel(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo el archivo: {str(e)}")
    result.update({"cut_date": date.today().isoformat(), "source": "excel_upload",
        "fetched_at": datetime.now(timezone.utc).isoformat()})
    cache_key = f"cxc_{company_id}_latest"
    await db.contalink_cache.update_one({"key": cache_key},
        {"$set": {"key": cache_key, "data": result, "created_at": datetime.now(timezone.utc)}}, upsert=True)
    return result


# ══════════════════════════════════════════════════════════════════════
# GET /contalink/cxc
# ══════════════════════════════════════════════════════════════════════

@router.get("/cxc")
async def get_cuentas_por_cobrar(request: Request,
    current_user: Dict = Depends(get_current_user), refresh: bool = Query(False)):
    company_id = await get_active_company_id(request, current_user)
    today = date.today()
    cache_key = f"cxc_{company_id}_latest"
    if not refresh:
        cached = await db.contalink_cache.find_one({"key": cache_key})
        if cached:
            return cached["data"]
    try:
        import calendar as cal
        client = await _get_client(company_id)
        start = f"{today.year}-{today.month:02d}-01"
        last_day = cal.monthrange(today.year, today.month)[1]
        end = f"{today.year}-{today.month:02d}-{last_day:02d}"
        raw = await client.get_trial_balance(start, end)
        if raw.get("status"):
            accounts = raw.get("data", {}).get("accounts", [])
            facturas, total_p, terceros = [], 0.0, set()
            aging = {"corriente":0,"vencido_30":0,"vencido_60":0,"vencido_90":0,"vencido_mas90":0}
            for acc in accounts:
                num = str(acc.get("account_number","") or "")
                if not any(num.startswith(p) for p in ["105","113","1050","1130"]): continue
                debit = float(acc.get("ending_debit") or acc.get("period_debit") or 0)
                credit = float(acc.get("ending_credit") or acc.get("period_credit") or 0)
                saldo = debit - credit
                if saldo <= 0: continue
                nombre = acc.get("account_name","") or ""
                total_p += saldo; terceros.add(nombre); aging["corriente"] += saldo
                facturas.append({"cuenta":num,"nombre":nombre,"cliente_nombre":nombre,
                    "cliente_rfc":"","saldo_pendiente":round(saldo,2),"moneda":"MXN",
                    "dias_vencido":0,"total":round(saldo,2),"uuid":""})
            if total_p > 0:
                result = {"cut_date":today.isoformat(),"num_facturas":len(facturas),
                    "num_clientes":len(terceros),"total_pendiente":round(total_p,2),
                    "aging":{k:round(v,2) for k,v in aging.items()},"pct_vencido":0.0,
                    "facturas":facturas,"source":"contalink_balanza",
                    "fetched_at":datetime.now(timezone.utc).isoformat()}
                await db.contalink_cache.update_one({"key":cache_key},
                    {"$set":{"key":cache_key,"data":result,"created_at":datetime.now(timezone.utc)}},upsert=True)
                return result
            else:
                cached_excel = await db.contalink_cache.find_one({"key": cache_key})
                if cached_excel: return cached_excel["data"]
    except Exception as e:
        logger.warning(f"CxC balanza falló (sin Contalink o error): {e}")
    cached = await db.contalink_cache.find_one({"key": cache_key})
    if cached: return cached["data"]
    return {"cut_date":today.isoformat(),"num_facturas":0,"num_clientes":0,"total_pendiente":0,
        "aging":{"corriente":0,"vencido_30":0,"vencido_60":0,"vencido_90":0,"vencido_mas90":0},
        "pct_vencido":0,"facturas":[],"source":"empty","fetched_at":datetime.now(timezone.utc).isoformat()}


# ══════════════════════════════════════════════════════════════════════
# GET /contalink/cxp
# ══════════════════════════════════════════════════════════════════════

@router.get("/cxp")
async def get_cuentas_por_pagar(request: Request,
    current_user: Dict = Depends(get_current_user), refresh: bool = Query(False)):
    company_id = await get_active_company_id(request, current_user)
    today = date.today()
    cache_key = f"cxp_{company_id}_latest"
    if not refresh:
        cached = await db.contalink_cache.find_one({"key": cache_key})
        if cached: return cached["data"]
    try:
        import calendar as cal
        client = await _get_client(company_id)
        start = f"{today.year}-{today.month:02d}-01"
        last_day = cal.monthrange(today.year, today.month)[1]
        end = f"{today.year}-{today.month:02d}-{last_day:02d}"
        raw = await client.get_trial_balance(start, end)
        if raw.get("status"):
            accounts = raw.get("data", {}).get("accounts", [])
            facturas, total_p, terceros = [], 0.0, set()
            aging = {"corriente":0,"vencido_30":0,"vencido_60":0,"vencido_90":0,"vencido_mas90":0}
            for acc in accounts:
                num = str(acc.get("account_number","") or "")
                if not any(num.startswith(p) for p in ["201","205","2010","2050"]): continue
                debit = float(acc.get("ending_debit") or acc.get("period_debit") or 0)
                credit = float(acc.get("ending_credit") or acc.get("period_credit") or 0)
                saldo = credit - debit
                if saldo <= 0: continue
                nombre = acc.get("account_name","") or ""
                total_p += saldo; terceros.add(nombre); aging["corriente"] += saldo
                facturas.append({"cuenta":num,"nombre":nombre,"proveedor_nombre":nombre,
                    "proveedor_rfc":"","saldo_pendiente":round(saldo,2),"moneda":"MXN",
                    "dias_vencido":0,"total":round(saldo,2),"uuid":""})
            if total_p > 0:
                result = {"cut_date":today.isoformat(),"num_facturas":len(facturas),
                    "num_proveedores":len(terceros),"total_pendiente":round(total_p,2),
                    "aging":{k:round(v,2) for k,v in aging.items()},"pct_vencido":0.0,
                    "facturas":facturas,"source":"contalink_balanza",
                    "fetched_at":datetime.now(timezone.utc).isoformat()}
                await db.contalink_cache.update_one({"key":cache_key},
                    {"$set":{"key":cache_key,"data":result,"created_at":datetime.now(timezone.utc)}},upsert=True)
                return result
            else:
                cached_excel = await db.contalink_cache.find_one({"key": cache_key})
                if cached_excel: return cached_excel["data"]
    except Exception as e:
        logger.warning(f"CxP balanza falló (sin Contalink o error): {e}")
    cached = await db.contalink_cache.find_one({"key": cache_key})
    if cached: return cached["data"]
    return {"cut_date":today.isoformat(),"num_facturas":0,"num_proveedores":0,"total_pendiente":0,
        "aging":{"corriente":0,"vencido_30":0,"vencido_60":0,"vencido_90":0,"vencido_mas90":0},
        "pct_vencido":0,"facturas":[],"source":"empty","fetched_at":datetime.now(timezone.utc).isoformat()}


# ══════════════════════════════════════════════════════════════════════
# SUMMARIES
# ══════════════════════════════════════════════════════════════════════

@router.get("/cxc-cxp-summary")
async def get_cxc_cxp_summary(request: Request,
    current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    today = date.today()
    cxc_cached = await db.contalink_cache.find_one({"key": f"cxc_{company_id}_latest"})
    cxp_cached = await db.contalink_cache.find_one({"key": f"cxp_{company_id}_latest"})
    cxc_total = cxc_cached["data"]["total_pendiente"] if cxc_cached else 0
    cxp_total = cxp_cached["data"]["total_pendiente"] if cxp_cached else 0
    return {
        "cut_date": today.isoformat(),
        "cxc": {"total": cxc_total, "vencido": 0, "corriente": cxc_total,
            "count": cxc_cached["data"].get("num_clientes",0) if cxc_cached else 0,
            "pct_vencido": cxc_cached["data"].get("pct_vencido",0) if cxc_cached else 0},
        "cxp": {"total": cxp_total, "vencido": 0, "corriente": cxp_total,
            "count": cxp_cached["data"].get("num_proveedores",0) if cxp_cached else 0,
            "pct_vencido": cxp_cached["data"].get("pct_vencido",0) if cxp_cached else 0},
        "flujo_neto_esperado": round(cxc_total - cxp_total, 2),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/aging-summary")
async def get_aging_summary_alias(request: Request,
    current_user: Dict = Depends(get_current_user)):
    return await get_cxc_cxp_summary(request, current_user)


# ══════════════════════════════════════════════════════════════════════
# CATEGORIZACIÓN IA — CxC/CxP
# ══════════════════════════════════════════════════════════════════════

CXC_CATEGORIES = [
    {"code": "ING-001", "nombre": "Ventas de productos"},
    {"code": "ING-002", "nombre": "Prestación de servicios"},
    {"code": "ING-003", "nombre": "Honorarios profesionales"},
    {"code": "ING-004", "nombre": "Arrendamiento cobrado"},
    {"code": "ING-005", "nombre": "Cobro de anticipos"},
    {"code": "ING-007", "nombre": "Intereses cobrados"},
    {"code": "ING-099", "nombre": "Otros ingresos por cobrar"},
]

CXP_CATEGORIES = [
    {"code": "EGR-001", "nombre": "Nómina y salarios"},
    {"code": "EGR-002", "nombre": "IMSS / INFONAVIT"},
    {"code": "EGR-003", "nombre": "ISR (pago provisional)"},
    {"code": "EGR-004", "nombre": "IVA (pago mensual)"},
    {"code": "EGR-005", "nombre": "Renta / arrendamiento"},
    {"code": "EGR-006", "nombre": "Proveedores de materia prima"},
    {"code": "EGR-007", "nombre": "Servicios (luz, agua, gas)"},
    {"code": "EGR-008", "nombre": "Telefonía e internet"},
    {"code": "EGR-009", "nombre": "Publicidad y marketing"},
    {"code": "EGR-010", "nombre": "Honorarios externos"},
    {"code": "EGR-011", "nombre": "Viáticos y gastos de viaje"},
    {"code": "EGR-012", "nombre": "Seguros y fianzas"},
    {"code": "EGR-013", "nombre": "Mantenimiento y reparaciones"},
    {"code": "EGR-015", "nombre": "Software y suscripciones"},
    {"code": "EGR-016", "nombre": "Pago de crédito bancario"},
    {"code": "EGR-017", "nombre": "Intereses pagados"},
    {"code": "EGR-018", "nombre": "Comisiones bancarias"},
    {"code": "EGR-020", "nombre": "Compra de activo fijo"},
    {"code": "EGR-099", "nombre": "Otros egresos por pagar"},
]


class CategoriaManual(BaseModel):
    nombre:        str
    tipo:          str   # "cxc" | "cxp"
    category_code: str
    category_name: str


@router.get("/categorias-cxc")
async def get_categorias_cxc(request: Request,
    current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    docs = await db.cxc_categorias.find({"company_id": company_id}, {"_id": 0}).to_list(1000)
    return {"categorias_guardadas": docs, "catalogo_cxc": CXC_CATEGORIES, "catalogo_cxp": CXP_CATEGORIES}


@router.post("/categoria-cxc")
async def save_categoria_manual(request: Request, item: CategoriaManual,
    current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    doc = {"company_id": company_id, "nombre": item.nombre, "tipo": item.tipo,
        "category_code": item.category_code, "category_name": item.category_name,
        "categorized_by": "manual", "updated_at": datetime.now(timezone.utc)}
    await db.cxc_categorias.update_one(
        {"company_id": company_id, "nombre": item.nombre, "tipo": item.tipo},
        {"$set": doc}, upsert=True)
    return {"ok": True, "nombre": item.nombre, "category_name": item.category_name}


@router.post("/auto-categorize-cxc")
async def auto_categorize_cxc(request: Request,
    current_user: Dict = Depends(get_current_user),
    solo_sin_categoria: bool = Query(True)):
    import httpx, os, json
    company_id = await get_active_company_id(request, current_user)

    cxc_cached = await db.contalink_cache.find_one({"key": f"cxc_{company_id}_latest"})
    cxp_cached = await db.contalink_cache.find_one({"key": f"cxp_{company_id}_latest"})
    cxc_facturas = cxc_cached["data"].get("facturas", []) if cxc_cached else []
    cxp_facturas = cxp_cached["data"].get("facturas", []) if cxp_cached else []

    if not cxc_facturas and not cxp_facturas:
        return {"success": True, "message": "No hay datos de CxC/CxP para categorizar", "updated": 0}

    if solo_sin_categoria:
        ya = await db.cxc_categorias.find({"company_id": company_id},
            {"nombre": 1, "tipo": 1, "_id": 0}).to_list(1000)
        ya_set = {(d["nombre"], d["tipo"]) for d in ya}
        cxc_facturas = [f for f in cxc_facturas
            if (f.get("nombre") or f.get("cliente_nombre",""), "cxc") not in ya_set]
        cxp_facturas = [f for f in cxp_facturas
            if (f.get("nombre") or f.get("proveedor_nombre",""), "cxp") not in ya_set]

    if not cxc_facturas and not cxp_facturas:
        return {"success": True, "message": "Todos ya tienen categoría", "updated": 0}

    items, seen = [], set()
    for f in cxc_facturas:
        n = (f.get("nombre") or f.get("cliente_nombre","")).strip()
        if n and n not in seen:
            seen.add(n); items.append({"nombre": n, "tipo": "cxc", "monto": f.get("saldo_pendiente",0)})
    for f in cxp_facturas:
        n = (f.get("nombre") or f.get("proveedor_nombre","")).strip()
        if n and n not in seen:
            seen.add(n); items.append({"nombre": n, "tipo": "cxp", "monto": f.get("saldo_pendiente",0)})

    if not items:
        return {"success": True, "message": "No hay elementos nuevos", "updated": 0}

    cat_cxc_txt = "\n".join(f'  code="{c["code"]}" | nombre="{c["nombre"]}"' for c in CXC_CATEGORIES)
    cat_cxp_txt = "\n".join(f'  code="{c["code"]}" | nombre="{c["nombre"]}"' for c in CXP_CATEGORIES)
    items_txt   = "\n".join(f'[{i}] nombre="{it["nombre"]}" | tipo={it["tipo"]} | monto={it["monto"]:.2f}'
        for i, it in enumerate(items))

    prompt = f"""Eres experto en contabilidad de empresas mexicanas.
Categoriza cuentas por cobrar (CxC) y cuentas por pagar (CxP).

CATEGORÍAS CxC (ingresos pendientes):
{cat_cxc_txt}

CATEGORÍAS CxP (egresos pendientes):
{cat_cxp_txt}

ELEMENTOS A CATEGORIZAR:
{items_txt}

REGLAS:
- tipo "cxc" → usa ING-xxx; tipo "cxp" → usa EGR-xxx.
- Infiere por el nombre: BIMBO→EGR-006, TELMEX/TELCEL→EGR-008, IMSS→EGR-002, SAT/HACIENDA→EGR-003.
- Sin pista clara → ING-099 para cxc, EGR-099 para cxp.

Responde SOLO un JSON array sin texto ni backticks:
[{{"nombre":"NOMBRE","tipo":"cxc","category_code":"ING-001"}}]"""

    api_key = os.environ.get("ANTHROPIC_API_KEY","")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY no configurada")

    try:
        async with httpx.AsyncClient(timeout=60) as http:
            res = await http.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                    "content-type": "application/json"},
                json={"model": "claude-sonnet-4-5", "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}]})
            res.raise_for_status()
            raw_text = res.json()["content"][0]["text"].strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error Claude API: {str(e)}")

    try:
        assignments = json.loads(raw_text.replace("```json","").replace("```","").strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parseando respuesta IA: {str(e)}")

    all_cats = {c["code"]: c for c in CXC_CATEGORIES + CXP_CATEGORIES}
    updated, errors = 0, []

    for a in assignments:
        nombre = a.get("nombre","").strip()
        tipo   = a.get("tipo","cxc")
        code   = a.get("category_code","")
        if not nombre or not code: continue
        cat = all_cats.get(code)
        if not cat:
            errors.append(f"Código desconocido: {code}"); continue
        try:
            await db.cxc_categorias.update_one(
                {"company_id": company_id, "nombre": nombre, "tipo": tipo},
                {"$set": {"company_id": company_id, "nombre": nombre, "tipo": tipo,
                    "category_code": code, "category_name": cat["nombre"],
                    "categorized_by": "ai", "updated_at": datetime.now(timezone.utc)}},
                upsert=True)
            updated += 1
        except Exception as e:
            errors.append(f"Error {nombre}: {str(e)}")

    return {"success": True, "processed": len(items), "updated": updated, "errors": errors,
        "message": f"✅ {updated} de {len(items)} clientes/proveedores categorizados con IA"}
