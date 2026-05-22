"""
TaxnFin — Endpoints de CxC y CxP desde Contalink
backend/routes/contalink_cxc_cxp.py

Dos fuentes:
1. API balanza (automático)  → /contalink/cxc  /contalink/cxp
2. Excel upload (manual)     → /contalink/upload-cxc  /contalink/upload-cxp
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, UploadFile, File
from typing import Dict, Optional
from datetime import date, datetime, timezone
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
    """Convierte '$1,234.56' o 1234.56 a float."""
    if val is None:
        return 0.0
    try:
        return float(str(val).replace("$", "").replace(",", "").strip() or 0)
    except Exception:
        return 0.0


def _parse_cxp_excel(content: bytes) -> dict:
    """
    Parsea el Excel de CxP de Contalink.
    Row 0: empresa / RFC / fecha
    Row 2: headers (#, Proveedor, Nota, Por vencer, 1-30, 31-60, 61-90, >90, TOTAL)
    Row 3..N-3: datos por proveedor
    Row N-2: TOTAL
    """
    import xlrd
    wb = xlrd.open_workbook(file_contents=content)
    ws = wb.sheet_by_index(0)

    empresa = str(ws.cell_value(0, 0)).strip()
    rfc     = str(ws.cell_value(0, 1)).strip()
    fecha   = str(ws.cell_value(0, 2)).strip()

    proveedores = []
    total_por_vencer = total_1_30 = total_31_60 = total_61_90 = total_mas90 = total_general = 0.0

    for r in range(3, ws.nrows):
        num_cell = ws.cell_value(r, 0)
        nombre   = str(ws.cell_value(r, 1)).strip()
        if not nombre or nombre.upper() in ("TOTAL", "PORCENTAJES", "PORCENTAJES TOTALES"):
            break

        por_vencer = _parse_currency(ws.cell_value(r, 3))
        d1_30      = _parse_currency(ws.cell_value(r, 4))
        d31_60     = _parse_currency(ws.cell_value(r, 5))
        d61_90     = _parse_currency(ws.cell_value(r, 6))
        mas90      = _parse_currency(ws.cell_value(r, 7))
        total      = _parse_currency(ws.cell_value(r, 8))

        if total == 0:
            continue
        if total < 0:
            total_general += total  # NC: resta del total, no mostrar como fila
            continue

        # Calcular días vencido aproximado (peor bucket)
        if mas90 > 0:      dias_vencido = 91
        elif d61_90 > 0:   dias_vencido = 61
        elif d31_60 > 0:   dias_vencido = 31
        elif d1_30 > 0:    dias_vencido = 1
        else:              dias_vencido = 0

        proveedores.append({
            "nombre":          nombre,
            "proveedor_nombre": nombre,
            "proveedor_rfc":   "",
            "saldo_pendiente": total,
            "por_vencer":      por_vencer,
            "vencido_1_30":    d1_30,
            "vencido_31_60":   d31_60,
            "vencido_61_90":   d61_90,
            "vencido_mas90":   mas90,
            "total":           total,
            "moneda":          "MXN",
            "dias_vencido":    dias_vencido,
            "fecha_emision":   "",
            "fecha_vencimiento": "",
            "uuid":            "",
        })

        total_por_vencer += por_vencer
        total_1_30       += d1_30
        total_31_60      += d31_60
        total_61_90      += d61_90
        total_mas90      += mas90
        total_general    += total

    aging = {
        "corriente":     round(total_por_vencer, 2),
        "vencido_30":    round(total_1_30, 2),
        "vencido_60":    round(total_31_60, 2),
        "vencido_90":    round(total_61_90, 2),
        "vencido_mas90": round(total_mas90, 2),
    }

    return {
        "empresa": empresa, "rfc": rfc, "fecha_reporte": fecha,
        "facturas": proveedores,
        "aging": aging,
        "total_pendiente": round(total_general, 2),
        "num_proveedores": len(proveedores),
        "num_facturas": len(proveedores),
        "pct_vencido": round(
            (total_1_30 + total_31_60 + total_61_90 + total_mas90) /
            max(total_general, 1) * 100, 1),
    }


def _parse_cxc_excel(content: bytes) -> dict:
    """
    Parsea el Excel de CxC (saldos-por-cobrar).
    Row 1: Empresa
    Row 2: RFC
    Row 3: headers (Clave, Cliente, Crédito, Por Vencer, Vencido, 1-30, [blank], 31-60, 61-90, [blank], 91-120, Sobre120, Total, LímiteCredito)
    Row 4..N-3: datos
    Row N-2: Total de Reporte
    """
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

        if total == 0:
            continue
        if total < 0:
            total_general += total  # NC: resta del total, no mostrar como fila
            continue

        if mas120 > 0:     dias_vencido = 121
        elif d91_120 > 0:  dias_vencido = 91
        elif d61_90 > 0:   dias_vencido = 61
        elif d31_60 > 0:   dias_vencido = 31
        elif d1_30 > 0:    dias_vencido = 1
        else:              dias_vencido = 0

        clientes.append({
            "nombre":          nombre,
            "cliente_nombre":  nombre,
            "cliente_rfc":     "",
            "saldo_pendiente": total,
            "por_vencer":      por_vencer,
            "vencido_1_30":    d1_30,
            "vencido_31_60":   d31_60,
            "vencido_61_90":   d61_90,
            "vencido_91_120":  d91_120,
            "vencido_mas120":  mas120,
            "total":           total,
            "moneda":          "MXN",
            "dias_vencido":    dias_vencido,
            "fecha_emision":   "",
            "fecha_vencimiento": "",
            "uuid":            "",
        })

        total_por_vencer += por_vencer
        total_1_30       += d1_30
        total_31_60      += d31_60
        total_61_90      += d61_90
        total_91_120     += d91_120
        total_mas120     += mas120
        total_general    += total

    aging = {
        "corriente":     round(total_por_vencer, 2),
        "vencido_30":    round(total_1_30, 2),
        "vencido_60":    round(total_31_60, 2),
        "vencido_90":    round(total_61_90, 2),
        "vencido_mas90": round(total_91_120 + total_mas120, 2),
    }

    return {
        "empresa": empresa, "rfc": rfc, "fecha_reporte": date.today().isoformat(),
        "facturas": clientes,
        "aging": aging,
        "total_pendiente": round(total_general, 2),
        "num_clientes": len(clientes),
        "num_facturas": len(clientes),
        "pct_vencido": round(
            (total_1_30 + total_31_60 + total_61_90 + total_91_120 + total_mas120) /
            max(total_general, 1) * 100, 1),
    }


# ══════════════════════════════════════════════════════════════════════
# UPLOAD CxP EXCEL
# ══════════════════════════════════════════════════════════════════════

@router.post("/upload-cxp")
async def upload_cxp_excel(
    request: Request,
    file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user),
):
    """Sube el Excel de Cuentas por Pagar exportado desde Contalink."""
    company_id = await get_active_company_id(request, current_user)

    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="El archivo debe ser .xls o .xlsx")

    content = await file.read()
    try:
        result = _parse_cxp_excel(content)
    except Exception as e:
        logger.error(f"Error parseando CxP Excel: {e}")
        raise HTTPException(status_code=400, detail=f"Error leyendo el archivo: {str(e)}")

    result.update({
        "cut_date":   date.today().isoformat(),
        "source":     "excel_upload",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    })

    cache_key = f"cxp_{company_id}_latest"
    await db.contalink_cache.update_one(
        {"key": cache_key},
        {"$set": {"key": cache_key, "data": result,
                  "created_at": datetime.now(timezone.utc)}},
        upsert=True)

    logger.info(f"CxP Excel upload: company={company_id} proveedores={result['num_proveedores']} total={result['total_pendiente']}")
    return result


# ══════════════════════════════════════════════════════════════════════
# UPLOAD CxC EXCEL
# ══════════════════════════════════════════════════════════════════════

@router.post("/upload-cxc")
async def upload_cxc_excel(
    request: Request,
    file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user),
):
    """Sube el Excel de Cuentas por Cobrar exportado desde Contalink."""
    company_id = await get_active_company_id(request, current_user)

    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="El archivo debe ser .xls o .xlsx")

    content = await file.read()
    try:
        result = _parse_cxc_excel(content)
    except Exception as e:
        logger.error(f"Error parseando CxC Excel: {e}")
        raise HTTPException(status_code=400, detail=f"Error leyendo el archivo: {str(e)}")

    result.update({
        "cut_date":   date.today().isoformat(),
        "source":     "excel_upload",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    })

    cache_key = f"cxc_{company_id}_latest"
    await db.contalink_cache.update_one(
        {"key": cache_key},
        {"$set": {"key": cache_key, "data": result,
                  "created_at": datetime.now(timezone.utc)}},
        upsert=True)

    logger.info(f"CxC Excel upload: company={company_id} clientes={result['num_clientes']} total={result['total_pendiente']}")
    return result


# ══════════════════════════════════════════════════════════════════════
# GET /contalink/cxc  (desde caché — llena por API o por Excel)
# ══════════════════════════════════════════════════════════════════════

@router.get("/cxc")
async def get_cuentas_por_cobrar(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    refresh: bool = Query(False),
):
    company_id = await get_active_company_id(request, current_user)
    today = date.today()
    cache_key = f"cxc_{company_id}_latest"

    if not refresh:
        cached = await db.contalink_cache.find_one({"key": cache_key})
        if cached:
            return cached["data"]

    # Intentar desde balanza
    try:
        import calendar as cal
        client   = await _get_client(company_id)
        start    = f"{today.year}-{today.month:02d}-01"
        last_day = cal.monthrange(today.year, today.month)[1]
        end      = f"{today.year}-{today.month:02d}-{last_day:02d}"
        raw      = await client.get_trial_balance(start, end)

        if raw.get("status"):
            accounts = raw.get("data", {}).get("accounts", [])
            facturas, total_p, terceros = [], 0.0, set()
            aging = {"corriente":0,"vencido_30":0,"vencido_60":0,"vencido_90":0,"vencido_mas90":0}

            for acc in accounts:
                num = str(acc.get("account_number","") or "")
                if not any(num.startswith(p) for p in ["105","113","1050","1130"]):
                    continue
                debit  = float(acc.get("ending_debit")  or acc.get("period_debit")  or 0)
                credit = float(acc.get("ending_credit") or acc.get("period_credit") or 0)
                saldo  = debit - credit
                if saldo <= 0: continue
                nombre = acc.get("account_name","") or ""
                total_p += saldo; terceros.add(nombre)
                aging["corriente"] += saldo
                facturas.append({"cuenta":num,"nombre":nombre,"cliente_nombre":nombre,
                    "cliente_rfc":"","saldo_pendiente":round(saldo,2),"moneda":"MXN",
                    "dias_vencido":0,"total":round(saldo,2),"uuid":""})

            # Solo sobreescribir caché si la balanza tiene datos reales
            if total_p > 0:
                result = {
                    "cut_date":today.isoformat(),"num_facturas":len(facturas),
                    "num_clientes":len(terceros),"total_pendiente":round(total_p,2),
                    "aging":{k:round(v,2) for k,v in aging.items()},"pct_vencido":0.0,
                    "facturas":facturas,"source":"contalink_balanza",
                    "fetched_at":datetime.now(timezone.utc).isoformat(),
                }
                await db.contalink_cache.update_one({"key":cache_key},
                    {"$set":{"key":cache_key,"data":result,"created_at":datetime.now(timezone.utc)}},upsert=True)
                logger.info(f"CxC balanza: {len(facturas)} cuentas, total={round(total_p,2)}")
                return result
            else:
                logger.info("CxC balanza vacía — preservando caché de Excel")
                cached_excel = await db.contalink_cache.find_one({"key": cache_key})
                if cached_excel:
                    return cached_excel["data"]
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"CxC balanza falló: {e} — devolviendo caché o vacío")

    # Fallback: caché aunque sea viejo
    cached = await db.contalink_cache.find_one({"key": cache_key})
    if cached:
        return cached["data"]

    return {"cut_date":today.isoformat(),"num_facturas":0,"num_clientes":0,
            "total_pendiente":0,"aging":{"corriente":0,"vencido_30":0,"vencido_60":0,
            "vencido_90":0,"vencido_mas90":0},"pct_vencido":0,"facturas":[],
            "source":"empty","fetched_at":datetime.now(timezone.utc).isoformat()}


# ══════════════════════════════════════════════════════════════════════
# GET /contalink/cxp
# ══════════════════════════════════════════════════════════════════════

@router.get("/cxp")
async def get_cuentas_por_pagar(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    refresh: bool = Query(False),
):
    company_id = await get_active_company_id(request, current_user)
    today = date.today()
    cache_key = f"cxp_{company_id}_latest"

    if not refresh:
        cached = await db.contalink_cache.find_one({"key": cache_key})
        if cached:
            return cached["data"]

    try:
        import calendar as cal
        client   = await _get_client(company_id)
        start    = f"{today.year}-{today.month:02d}-01"
        last_day = cal.monthrange(today.year, today.month)[1]
        end      = f"{today.year}-{today.month:02d}-{last_day:02d}"
        raw      = await client.get_trial_balance(start, end)

        if raw.get("status"):
            accounts = raw.get("data", {}).get("accounts", [])
            facturas, total_p, terceros = [], 0.0, set()
            aging = {"corriente":0,"vencido_30":0,"vencido_60":0,"vencido_90":0,"vencido_mas90":0}

            for acc in accounts:
                num = str(acc.get("account_number","") or "")
                if not any(num.startswith(p) for p in ["201","205","2010","2050"]):
                    continue
                debit  = float(acc.get("ending_debit")  or acc.get("period_debit")  or 0)
                credit = float(acc.get("ending_credit") or acc.get("period_credit") or 0)
                saldo  = credit - debit
                if saldo <= 0: continue
                nombre = acc.get("account_name","") or ""
                total_p += saldo; terceros.add(nombre)
                aging["corriente"] += saldo
                facturas.append({"cuenta":num,"nombre":nombre,"proveedor_nombre":nombre,
                    "proveedor_rfc":"","saldo_pendiente":round(saldo,2),"moneda":"MXN",
                    "dias_vencido":0,"total":round(saldo,2),"uuid":""})

            # Solo sobreescribir caché si la balanza tiene datos reales
            if total_p > 0:
                result = {
                    "cut_date":today.isoformat(),"num_facturas":len(facturas),
                    "num_proveedores":len(terceros),"total_pendiente":round(total_p,2),
                    "aging":{k:round(v,2) for k,v in aging.items()},"pct_vencido":0.0,
                    "facturas":facturas,"source":"contalink_balanza",
                    "fetched_at":datetime.now(timezone.utc).isoformat(),
                }
                await db.contalink_cache.update_one({"key":cache_key},
                    {"$set":{"key":cache_key,"data":result,"created_at":datetime.now(timezone.utc)}},upsert=True)
                logger.info(f"CxP balanza: {len(facturas)} cuentas, total={round(total_p,2)}")
                return result
            else:
                logger.info("CxP balanza vacía — preservando caché de Excel")
                cached_excel = await db.contalink_cache.find_one({"key": cache_key})
                if cached_excel:
                    return cached_excel["data"]
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"CxP balanza falló: {e} — devolviendo caché o vacío")

    cached = await db.contalink_cache.find_one({"key": cache_key})
    if cached:
        return cached["data"]

    return {"cut_date":today.isoformat(),"num_facturas":0,"num_proveedores":0,
            "total_pendiente":0,"aging":{"corriente":0,"vencido_30":0,"vencido_60":0,
            "vencido_90":0,"vencido_mas90":0},"pct_vencido":0,"facturas":[],
            "source":"empty","fetched_at":datetime.now(timezone.utc).isoformat()}


# ══════════════════════════════════════════════════════════════════════
# GET /contalink/cxc-cxp-summary
# ══════════════════════════════════════════════════════════════════════

@router.get("/cxc-cxp-summary")
async def get_cxc_cxp_summary(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    today = date.today()
    cxc_key = f"cxc_{company_id}_latest"
    cxp_key = f"cxp_{company_id}_latest"

    cxc_cached = await db.contalink_cache.find_one({"key": cxc_key})
    cxp_cached = await db.contalink_cache.find_one({"key": cxp_key})

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


# ══════════════════════════════════════════════════════════════════════
# ALIAS: /contalink/aging-summary  (usado por PaymentsModule)
# ══════════════════════════════════════════════════════════════════════

@router.get("/aging-summary")
async def get_aging_summary_alias(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Alias de /cxc-cxp-summary para compatibilidad con PaymentsModule."""
    return await get_cxc_cxp_summary(request, current_user)
