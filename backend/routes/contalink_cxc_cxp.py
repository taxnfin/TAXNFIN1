"""
TaxnFin — Endpoints de CxC y CxP desde Contalink
backend/routes/contalink_cxc_cxp.py
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
    """Obtiene ContalinkClient + rfc de la integración activa."""
    integration = await db.integrations.find_one({
        "company_id": company_id,
        "type": "contalink",
        "active": True,
    })
    if not integration:
        raise HTTPException(
            status_code=404,
            detail="No tienes Contalink conectado. Ve a Integraciones y guarda tu API Key."
        )
    api_key = integration.get("api_key", "")
    rfc     = integration.get("rfc", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key de Contalink no configurada.")

    # Importar el ContalinkClient que ya existe en routes/contalink.py
    from routes.contalink import ContalinkClient
    return ContalinkClient(api_key), rfc


def _calcular_dias_vencido(fecha_str: Optional[str]) -> int:
    if not fecha_str:
        return 0
    try:
        venc = date.fromisoformat(str(fecha_str)[:10])
        return (date.today() - venc).days
    except Exception:
        return 0


def _parse_invoices(raw) -> list:
    """Extrae la lista de facturas del response de Contalink (varios formatos posibles)."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("data", "invoices", "documents", "results"):
            val = raw.get(key)
            if isinstance(val, list):
                return val
    return []


async def _fetch_all_invoices(client, rfc: str, transaction_type: str,
                               start_date: str, end_date: str) -> list:
    """Pagina automáticamente y devuelve todas las facturas."""
    all_items = []
    page = 0
    while True:
        raw = await client.get_invoices(
            rfc=rfc,
            transaction_type=transaction_type,
            document_type="I",   # Ingreso (CFDI de ingreso)
            start_date=start_date,
            end_date=end_date,
            page=page,
        )
        if raw.get("status") == 0:
            break
        items = _parse_invoices(raw)
        if not items:
            break
        all_items.extend(items)
        if len(items) < 50:   # última página
            break
        page += 1
    return all_items


def _to_cxc(inv: dict) -> dict:
    """Convierte una factura emitida al formato CxC."""
    total   = float(inv.get("total") or inv.get("amount") or 0)
    cobrado = float(inv.get("amount_paid") or inv.get("monto_cobrado") or
                    inv.get("paid_amount") or 0)
    saldo   = round(total - cobrado, 2)

    fecha_venc = (inv.get("due_date") or inv.get("fecha_vencimiento") or
                  inv.get("payment_date") or "")

    return {
        "uuid":             (inv.get("uuid") or inv.get("UUID") or
                             inv.get("folio_fiscal") or "").strip(),
        "folio":            inv.get("folio") or inv.get("series", ""),
        "fecha_emision":    inv.get("date") or inv.get("fecha_emision") or inv.get("issue_date", ""),
        "fecha_vencimiento": fecha_venc,
        "cliente_rfc":      (inv.get("receiver_rfc") or inv.get("receptor_rfc") or
                             inv.get("rfc_receiver") or ""),
        "cliente_nombre":   (inv.get("receiver_name") or inv.get("receptor_nombre") or
                             inv.get("name_receiver") or ""),
        "moneda":           inv.get("currency") or inv.get("moneda") or "MXN",
        "total":            total,
        "monto_cobrado":    cobrado,
        "saldo_pendiente":  saldo,
        "estatus":          inv.get("status") or inv.get("estatus") or "",
        "dias_vencido":     _calcular_dias_vencido(fecha_venc),
    }


def _to_cxp(inv: dict) -> dict:
    """Convierte una factura recibida al formato CxP."""
    total  = float(inv.get("total") or inv.get("amount") or 0)
    pagado = float(inv.get("amount_paid") or inv.get("monto_pagado") or
                   inv.get("paid_amount") or 0)
    saldo  = round(total - pagado, 2)

    fecha_venc = (inv.get("due_date") or inv.get("fecha_vencimiento") or
                  inv.get("payment_date") or "")

    return {
        "uuid":             (inv.get("uuid") or inv.get("UUID") or
                             inv.get("folio_fiscal") or "").strip(),
        "folio":            inv.get("folio") or inv.get("series", ""),
        "fecha_emision":    inv.get("date") or inv.get("fecha_emision") or inv.get("issue_date", ""),
        "fecha_vencimiento": fecha_venc,
        "proveedor_rfc":    (inv.get("issuer_rfc") or inv.get("emisor_rfc") or
                             inv.get("rfc_issuer") or ""),
        "proveedor_nombre": (inv.get("issuer_name") or inv.get("emisor_nombre") or
                             inv.get("name_issuer") or ""),
        "moneda":           inv.get("currency") or inv.get("moneda") or "MXN",
        "total":            total,
        "monto_pagado":     pagado,
        "saldo_pendiente":  saldo,
        "estatus":          inv.get("status") or inv.get("estatus") or "",
        "dias_vencido":     _calcular_dias_vencido(fecha_venc),
    }


def _build_aging(facturas: list) -> dict:
    aging = {"corriente": 0, "vencido_30": 0, "vencido_60": 0,
             "vencido_90": 0, "vencido_mas90": 0}
    total_pendiente = 0
    terceros = set()

    for f in facturas:
        saldo = f.get("saldo_pendiente", 0)
        dias  = f.get("dias_vencido", 0)
        total_pendiente += saldo
        terceros.add(f.get("cliente_rfc") or f.get("proveedor_rfc") or
                     f.get("cliente_nombre") or f.get("proveedor_nombre", ""))

        if dias <= 0:
            aging["corriente"] += saldo
        elif dias <= 30:
            aging["vencido_30"] += saldo
        elif dias <= 60:
            aging["vencido_60"] += saldo
        elif dias <= 90:
            aging["vencido_90"] += saldo
        else:
            aging["vencido_mas90"] += saldo

    return {
        "aging":           {k: round(v, 2) for k, v in aging.items()},
        "total_pendiente": round(total_pendiente, 2),
        "num_terceros":    len(terceros),
        "pct_vencido":     round(
            (total_pendiente - aging["corriente"]) / max(total_pendiente, 1) * 100, 1
        ),
    }


# ══════════════════════════════════════════════════════════════════════
# GET /contalink/cxc
# ══════════════════════════════════════════════════════════════════════

@router.get("/cxc")
async def get_cuentas_por_cobrar(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    days_back: int = Query(180, description="Días hacia atrás para buscar facturas"),
    refresh: bool = Query(False, description="Ignorar caché"),
):
    company_id = await get_active_company_id(request, current_user)
    cut = date.today().isoformat()

    # Caché 4 horas
    cache_key = f"cxc_{company_id}_{cut}"
    if not refresh:
        cached = await db.contalink_cache.find_one({"key": cache_key})
        if cached:
            delta = (datetime.now(timezone.utc) - cached["created_at"]).total_seconds()
            if delta < 14400:
                return cached["data"]

    try:
        client, rfc = await _get_client_and_creds(company_id)
        end_date   = date.today().isoformat()
        start_date = (date.today() - timedelta(days=days_back)).isoformat()

        # Facturas emitidas (issued) = CxC
        raw = await _fetch_all_invoices(client, rfc, "issued", start_date, end_date)
        facturas = [_to_cxc(inv) for inv in raw if _to_cxc(inv)["saldo_pendiente"] > 0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo CxC de Contalink: {e}")
        raise HTTPException(status_code=500, detail=f"Error consultando Contalink: {str(e)}")

    stats = _build_aging(facturas)
    result = {
        "cut_date":        cut,
        "num_facturas":    len(facturas),
        "num_clientes":    stats["num_terceros"],
        "total_pendiente": stats["total_pendiente"],
        "aging":           stats["aging"],
        "pct_vencido":     stats["pct_vencido"],
        "facturas":        facturas,
        "source":          "contalink",
        "fetched_at":      datetime.now(timezone.utc).isoformat(),
    }

    await db.contalink_cache.update_one(
        {"key": cache_key},
        {"$set": {"key": cache_key, "data": result,
                  "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return result


# ══════════════════════════════════════════════════════════════════════
# GET /contalink/cxp
# ══════════════════════════════════════════════════════════════════════

@router.get("/cxp")
async def get_cuentas_por_pagar(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    days_back: int = Query(180, description="Días hacia atrás para buscar facturas"),
    refresh: bool = Query(False, description="Ignorar caché"),
):
    company_id = await get_active_company_id(request, current_user)
    cut = date.today().isoformat()

    cache_key = f"cxp_{company_id}_{cut}"
    if not refresh:
        cached = await db.contalink_cache.find_one({"key": cache_key})
        if cached:
            delta = (datetime.now(timezone.utc) - cached["created_at"]).total_seconds()
            if delta < 14400:
                return cached["data"]

    try:
        client, rfc = await _get_client_and_creds(company_id)
        end_date   = date.today().isoformat()
        start_date = (date.today() - timedelta(days=days_back)).isoformat()

        # Facturas recibidas (received) = CxP
        raw = await _fetch_all_invoices(client, rfc, "received", start_date, end_date)
        facturas = [_to_cxp(inv) for inv in raw if _to_cxp(inv)["saldo_pendiente"] > 0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo CxP de Contalink: {e}")
        raise HTTPException(status_code=500, detail=f"Error consultando Contalink: {str(e)}")

    stats = _build_aging(facturas)
    result = {
        "cut_date":         cut,
        "num_facturas":     len(facturas),
        "num_proveedores":  stats["num_terceros"],
        "total_pendiente":  stats["total_pendiente"],
        "aging":            stats["aging"],
        "pct_vencido":      stats["pct_vencido"],
        "facturas":         facturas,
        "source":           "contalink",
        "fetched_at":       datetime.now(timezone.utc).isoformat(),
    }

    await db.contalink_cache.update_one(
        {"key": cache_key},
        {"$set": {"key": cache_key, "data": result,
                  "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return result


# ══════════════════════════════════════════════════════════════════════
# GET /contalink/cxc-cxp-summary  (para TreasuryDecisions)
# ══════════════════════════════════════════════════════════════════════

@router.get("/cxc-cxp-summary")
async def get_cxc_cxp_summary(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    days_back: int = Query(180),
):
    import asyncio
    company_id = await get_active_company_id(request, current_user)

    try:
        client, rfc = await _get_client_and_creds(company_id)
        end_date   = date.today().isoformat()
        start_date = (date.today() - timedelta(days=days_back)).isoformat()

        raw_cxc, raw_cxp = await asyncio.gather(
            _fetch_all_invoices(client, rfc, "issued",   start_date, end_date),
            _fetch_all_invoices(client, rfc, "received", start_date, end_date),
        )
        cxc = [_to_cxc(i) for i in raw_cxc if _to_cxc(i)["saldo_pendiente"] > 0]
        cxp = [_to_cxp(i) for i in raw_cxp if _to_cxp(i)["saldo_pendiente"] > 0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    def _sum(lst):
        t = sum(f["saldo_pendiente"] for f in lst)
        v = sum(f["saldo_pendiente"] for f in lst if f["dias_vencido"] > 0)
        return {"total": round(t, 2), "vencido": round(v, 2),
                "corriente": round(t - v, 2), "count": len(lst),
                "pct_vencido": round(v / max(t, 1) * 100, 1)}

    return {
        "cut_date":            date.today().isoformat(),
        "cxc":                 _sum(cxc),
        "cxp":                 _sum(cxp),
        "flujo_neto_esperado": round(
            sum(f["saldo_pendiente"] for f in cxc) -
            sum(f["saldo_pendiente"] for f in cxp), 2
        ),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
