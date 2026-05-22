"""
TaxnFin — Endpoints de CxC y CxP desde Contalink
backend/routes/contalink_cxc_cxp.py

FUENTE: Balanza de comprobación (get_trial_balance) — misma que usa el sync exitoso.
Cuentas 105* = Clientes (CxC), 201* = Proveedores (CxP)
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Dict, Optional
from datetime import date, datetime, timezone, timedelta
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contalink", tags=["Contalink CxC/CxP"])


async def _get_client_and_creds(company_id: str):
    integration = await db.integrations.find_one({
        "company_id": company_id, "type": "contalink", "active": True,
    })
    if not integration:
        raise HTTPException(status_code=404,
            detail="No tienes Contalink conectado. Ve a Integraciones.")
    api_key = integration.get("api_key", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key de Contalink no configurada.")
    from routes.contalink import ContalinkClient
    return ContalinkClient(api_key)


def _build_aging_from_balance(accounts: list, prefixes: list, tipo: str) -> dict:
    """
    Construye CxC o CxP desde la balanza de comprobación.
    prefixes: lista de prefijos de cuenta a incluir, ej ["105", "113"] para CxC
    tipo: "cxc" | "cxp"
    """
    facturas = []
    total_pendiente = 0
    terceros = set()

    for acc in accounts:
        num = str(acc.get("account_number", "") or "")
        if not any(num.startswith(p) for p in prefixes):
            continue

        nombre = acc.get("account_name", "") or ""
        # Para CxC: saldo deudor (debit) = lo que nos deben
        # Para CxP: saldo acreedor (credit) = lo que debemos
        debit  = float(acc.get("ending_debit")  or acc.get("period_debit")  or acc.get("debit")  or 0)
        credit = float(acc.get("ending_credit") or acc.get("period_credit") or acc.get("credit") or 0)

        if tipo == "cxc":
            saldo = debit - credit   # saldo deudor neto
        else:
            saldo = credit - debit   # saldo acreedor neto

        if saldo <= 0:
            continue

        total_pendiente += saldo
        terceros.add(nombre)

        facturas.append({
            "cuenta":          num,
            "nombre":          nombre,
            "saldo_pendiente": round(saldo, 2),
            "moneda":          "MXN",
            "debit":           round(debit, 2),
            "credit":          round(credit, 2),
            # Sin fecha de vencimiento desde balanza — clasificamos como vigente
            "dias_vencido":    0,
            "fecha_emision":   "",
            "fecha_vencimiento": "",
        })

    # Aging simplificado — todo corriente (la balanza no da fechas por factura)
    aging = {
        "corriente":    round(total_pendiente, 2),
        "vencido_30":   0,
        "vencido_60":   0,
        "vencido_90":   0,
        "vencido_mas90":0,
    }

    return {
        "facturas":        facturas,
        "aging":           aging,
        "total_pendiente": round(total_pendiente, 2),
        "num_terceros":    len(terceros),
        "pct_vencido":     0.0,
    }


async def _get_balance(client, year: int, month: int) -> list:
    """Obtiene la balanza del mes indicado."""
    import calendar as cal
    start = f"{year}-{month:02d}-01"
    last  = cal.monthrange(year, month)[1]
    end   = f"{year}-{month:02d}-{last:02d}"

    raw = await client.get_trial_balance(start, end)
    if not raw.get("status"):
        raise Exception(f"Error balanza Contalink: {raw.get('message')}")

    accounts = raw.get("data", {}).get("accounts", [])
    logger.info(f"Balanza {start}→{end}: {len(accounts)} cuentas")
    return accounts


# ══════════════════════════════════════════════════════════════════════
# GET /contalink/cxc
# ══════════════════════════════════════════════════════════════════════

@router.get("/cxc")
async def get_cuentas_por_cobrar(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    refresh: bool = Query(False),
):
    """CxC desde balanza de comprobación — cuentas 105* (Clientes)."""
    company_id = await get_active_company_id(request, current_user)
    today = date.today()
    cache_key = f"cxc_{company_id}_{today.isoformat()}"

    if not refresh:
        cached = await db.contalink_cache.find_one({"key": cache_key})
        if cached and (datetime.now(timezone.utc) - cached["created_at"]).total_seconds() < 14400:
            return cached["data"]

    try:
        client   = await _get_client_and_creds(company_id)
        accounts = await _get_balance(client, today.year, today.month)
        # Cuentas de clientes: 105* (Deudores/Clientes) y 113* (Documentos por cobrar)
        stats    = _build_aging_from_balance(accounts, ["105", "113", "1050", "1130"], "cxc")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CxC error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    result = {
        "cut_date":        today.isoformat(),
        "num_facturas":    len(stats["facturas"]),
        "num_clientes":    stats["num_terceros"],
        "total_pendiente": stats["total_pendiente"],
        "aging":           stats["aging"],
        "pct_vencido":     stats["pct_vencido"],
        "facturas":        stats["facturas"],
        "source":          "contalink_balanza",
        "fetched_at":      datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"CxC company={company_id}: {result['num_facturas']} cuentas, total={result['total_pendiente']}")

    await db.contalink_cache.update_one(
        {"key": cache_key},
        {"$set": {"key": cache_key, "data": result,
                  "created_at": datetime.now(timezone.utc)}},
        upsert=True)
    return result


# ══════════════════════════════════════════════════════════════════════
# GET /contalink/cxp
# ══════════════════════════════════════════════════════════════════════

@router.get("/cxp")
async def get_cuentas_por_pagar(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    refresh: bool = Query(False),
):
    """CxP desde balanza de comprobación — cuentas 201* (Proveedores)."""
    company_id = await get_active_company_id(request, current_user)
    today = date.today()
    cache_key = f"cxp_{company_id}_{today.isoformat()}"

    if not refresh:
        cached = await db.contalink_cache.find_one({"key": cache_key})
        if cached and (datetime.now(timezone.utc) - cached["created_at"]).total_seconds() < 14400:
            return cached["data"]

    try:
        client   = await _get_client_and_creds(company_id)
        accounts = await _get_balance(client, today.year, today.month)
        # Cuentas de proveedores: 201* (Proveedores) y 205* (Documentos por pagar)
        stats    = _build_aging_from_balance(accounts, ["201", "205", "2010", "2050"], "cxp")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CxP error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    result = {
        "cut_date":         today.isoformat(),
        "num_facturas":     len(stats["facturas"]),
        "num_proveedores":  stats["num_terceros"],
        "total_pendiente":  stats["total_pendiente"],
        "aging":            stats["aging"],
        "pct_vencido":      stats["pct_vencido"],
        "facturas":         stats["facturas"],
        "source":           "contalink_balanza",
        "fetched_at":       datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"CxP company={company_id}: {result['num_facturas']} cuentas, total={result['total_pendiente']}")

    await db.contalink_cache.update_one(
        {"key": cache_key},
        {"$set": {"key": cache_key, "data": result,
                  "created_at": datetime.now(timezone.utc)}},
        upsert=True)
    return result


# ══════════════════════════════════════════════════════════════════════
# GET /contalink/cxc-cxp-summary
# ══════════════════════════════════════════════════════════════════════

@router.get("/cxc-cxp-summary")
async def get_cxc_cxp_summary(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Resumen combinado CxC + CxP para TreasuryDecisions."""
    import asyncio
    company_id = await get_active_company_id(request, current_user)
    today = date.today()

    try:
        client   = await _get_client_and_creds(company_id)
        accounts = await _get_balance(client, today.year, today.month)
        cxc_stats = _build_aging_from_balance(accounts, ["105", "113", "1050", "1130"], "cxc")
        cxp_stats = _build_aging_from_balance(accounts, ["201", "205", "2010", "2050"], "cxp")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    def _s(stats):
        t = stats["total_pendiente"]
        return {"total": t, "vencido": 0, "corriente": t,
                "count": stats["num_terceros"], "pct_vencido": 0}

    return {
        "cut_date": today.isoformat(),
        "cxc": _s(cxc_stats),
        "cxp": _s(cxp_stats),
        "flujo_neto_esperado": round(cxc_stats["total_pendiente"] - cxp_stats["total_pendiente"], 2),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
