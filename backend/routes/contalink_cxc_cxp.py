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
    integration = await db.integrations.find_one({
        "company_id": company_id, "type": "contalink", "active": True,
    })
    if not integration:
        raise HTTPException(status_code=404,
            detail="No tienes Contalink conectado. Ve a Integraciones.")
    api_key = integration.get("api_key", "")
    rfc     = integration.get("rfc", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key de Contalink no configurada.")
    from routes.contalink import ContalinkClient
    return ContalinkClient(api_key), rfc


def _dias_vencido(fecha_str) -> int:
    if not fecha_str:
        return 0
    try:
        venc = date.fromisoformat(str(fecha_str)[:10])
        return (date.today() - venc).days
    except Exception:
        return 0


def _parse_list(raw) -> list:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for k in ("data", "invoices", "documents", "results"):
            v = raw.get(k)
            if isinstance(v, list):
                return v
    return []


async def _fetch_all(client, rfc, transaction_type, start_date, end_date) -> list:
    """Pagina automáticamente sobre /invoices/list/"""
    items, page = [], 0
    while True:
        raw = await client.get_invoices(
            rfc=rfc, transaction_type=transaction_type,
            document_type="I",   # CFDI de Ingreso
            start_date=start_date, end_date=end_date, page=page,
        )
        # status == 0 → error de Contalink
        if isinstance(raw, dict) and raw.get("status") == 0:
            logger.warning(f"Contalink get_invoices status=0: {raw.get('message')}")
            break
        batch = _parse_list(raw)
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 50:
            break
        page += 1
    return items


def _map_cxc(inv: dict) -> dict:
    """
    Mapea una factura EMITIDA (issued) al formato CxC.
    Contalink no devuelve amount_paid — usamos estatus para determinar si está vigente.
    """
    total = float(inv.get("total") or inv.get("monto") or 0)
    # Si está cancelada, saldo = 0 (la excluimos)
    cancelado = inv.get("cancelado") or inv.get("estado_cancelacion") == "cancelado"
    estatus   = (inv.get("estatus") or inv.get("status") or "vigente").lower()
    if cancelado or estatus in ("cancelado", "cancelada"):
        return None

    # Fecha de vencimiento: Contalink no siempre la da.
    # Para PPD usamos fecha + 30d; para PUE es contado.
    fecha_emision = inv.get("fecha") or inv.get("fecha_emision") or ""
    metodo_pago   = inv.get("metodo_pago", "PUE")
    fecha_venc    = inv.get("fecha_vencimiento") or inv.get("due_date") or ""
    if not fecha_venc and fecha_emision:
        dias_plazo = 30 if metodo_pago == "PPD" else 0
        try:
            fecha_venc = (date.fromisoformat(fecha_emision[:10]) +
                          timedelta(days=dias_plazo)).isoformat()
        except Exception:
            fecha_venc = fecha_emision

    return {
        "uuid":             (inv.get("uuid") or inv.get("UUID") or
                             inv.get("folio_fiscal") or "").strip(),
        "folio":            inv.get("folio") or "",
        "fecha_emision":    fecha_emision,
        "fecha_vencimiento": fecha_venc,
        "cliente_rfc":      inv.get("receptor_rfc") or inv.get("rfc_receptor") or "",
        "cliente_nombre":   inv.get("receptor_nombre") or inv.get("nombre_receptor") or "",
        "moneda":           inv.get("moneda") or "MXN",
        "metodo_pago":      metodo_pago,
        "total":            total,
        "monto_cobrado":    0,          # Contalink no lo devuelve en el listado
        "saldo_pendiente":  total,      # Asumimos vigente = pendiente
        "estatus":          estatus,
        "dias_vencido":     _dias_vencido(fecha_venc),
    }


def _map_cxp(inv: dict) -> dict:
    """Mapea una factura RECIBIDA (received) al formato CxP."""
    total = float(inv.get("total") or inv.get("monto") or 0)
    cancelado = inv.get("cancelado") or inv.get("estado_cancelacion") == "cancelado"
    estatus   = (inv.get("estatus") or inv.get("status") or "vigente").lower()
    if cancelado or estatus in ("cancelado", "cancelada"):
        return None

    fecha_emision = inv.get("fecha") or inv.get("fecha_emision") or ""
    metodo_pago   = inv.get("metodo_pago", "PUE")
    fecha_venc    = inv.get("fecha_vencimiento") or inv.get("due_date") or ""
    if not fecha_venc and fecha_emision:
        dias_plazo = 30 if metodo_pago == "PPD" else 0
        try:
            fecha_venc = (date.fromisoformat(fecha_emision[:10]) +
                          timedelta(days=dias_plazo)).isoformat()
        except Exception:
            fecha_venc = fecha_emision

    return {
        "uuid":              (inv.get("uuid") or inv.get("UUID") or
                              inv.get("folio_fiscal") or "").strip(),
        "folio":             inv.get("folio") or "",
        "fecha_emision":     fecha_emision,
        "fecha_vencimiento": fecha_venc,
        "proveedor_rfc":     inv.get("emisor_rfc") or inv.get("rfc_emisor") or "",
        "proveedor_nombre":  inv.get("emisor_nombre") or inv.get("nombre_emisor") or "",
        "moneda":            inv.get("moneda") or "MXN",
        "metodo_pago":       metodo_pago,
        "total":             total,
        "monto_pagado":      0,
        "saldo_pendiente":   total,
        "estatus":           estatus,
        "dias_vencido":      _dias_vencido(fecha_venc),
    }


def _aging_stats(facturas: list, tipo: str) -> dict:
    aging = {"corriente": 0, "vencido_30": 0, "vencido_60": 0,
             "vencido_90": 0, "vencido_mas90": 0}
    total_pendiente = 0
    terceros = set()

    for f in facturas:
        saldo = f["saldo_pendiente"]
        dias  = f["dias_vencido"]
        total_pendiente += saldo
        key = "cliente_rfc" if tipo == "cxc" else "proveedor_rfc"
        terceros.add(f.get(key) or f.get(
            "cliente_nombre" if tipo == "cxc" else "proveedor_nombre", ""))

        if dias <= 0:      aging["corriente"]    += saldo
        elif dias <= 30:   aging["vencido_30"]   += saldo
        elif dias <= 60:   aging["vencido_60"]   += saldo
        elif dias <= 90:   aging["vencido_90"]   += saldo
        else:              aging["vencido_mas90"] += saldo

    return {
        "aging":           {k: round(v, 2) for k, v in aging.items()},
        "total_pendiente": round(total_pendiente, 2),
        "num_terceros":    len(terceros),
        "pct_vencido":     round(
            (total_pendiente - aging["corriente"]) / max(total_pendiente, 1) * 100, 1),
    }


# ══════════════════════════════════════════════════════════════════════
# GET /contalink/cxc
# ══════════════════════════════════════════════════════════════════════

@router.get("/cxc")
async def get_cuentas_por_cobrar(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    days_back: int = Query(180),
    refresh: bool = Query(False),
):
    company_id = await get_active_company_id(request, current_user)
    cut = date.today().isoformat()
    cache_key = f"cxc_{company_id}_{cut}"

    if not refresh:
        cached = await db.contalink_cache.find_one({"key": cache_key})
        if cached:
            if (datetime.now(timezone.utc) - cached["created_at"]).total_seconds() < 14400:
                return cached["data"]

    try:
        client, rfc = await _get_client_and_creds(company_id)
        end_date   = date.today().isoformat()
        start_date = (date.today() - timedelta(days=days_back)).isoformat()
        raw = await _fetch_all(client, rfc, "issued", start_date, end_date)
        facturas = [m for inv in raw if (m := _map_cxc(inv)) and m["total"] > 0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CxC error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    stats = _aging_stats(facturas, "cxc")
    result = {
        "cut_date": cut, "num_facturas": len(facturas),
        "num_clientes": stats["num_terceros"],
        "total_pendiente": stats["total_pendiente"],
        "aging": stats["aging"], "pct_vencido": stats["pct_vencido"],
        "facturas": facturas, "source": "contalink",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
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
    days_back: int = Query(180),
    refresh: bool = Query(False),
):
    company_id = await get_active_company_id(request, current_user)
    cut = date.today().isoformat()
    cache_key = f"cxp_{company_id}_{cut}"

    if not refresh:
        cached = await db.contalink_cache.find_one({"key": cache_key})
        if cached:
            if (datetime.now(timezone.utc) - cached["created_at"]).total_seconds() < 14400:
                return cached["data"]

    try:
        client, rfc = await _get_client_and_creds(company_id)
        end_date   = date.today().isoformat()
        start_date = (date.today() - timedelta(days=days_back)).isoformat()
        raw = await _fetch_all(client, rfc, "received", start_date, end_date)
        facturas = [m for inv in raw if (m := _map_cxp(inv)) and m["total"] > 0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CxP error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    stats = _aging_stats(facturas, "cxp")
    result = {
        "cut_date": cut, "num_facturas": len(facturas),
        "num_proveedores": stats["num_terceros"],
        "total_pendiente": stats["total_pendiente"],
        "aging": stats["aging"], "pct_vencido": stats["pct_vencido"],
        "facturas": facturas, "source": "contalink",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
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
    days_back: int = Query(180),
):
    import asyncio
    company_id = await get_active_company_id(request, current_user)
    try:
        client, rfc = await _get_client_and_creds(company_id)
        end_date   = date.today().isoformat()
        start_date = (date.today() - timedelta(days=days_back)).isoformat()
        raw_cxc, raw_cxp = await asyncio.gather(
            _fetch_all(client, rfc, "issued",   start_date, end_date),
            _fetch_all(client, rfc, "received", start_date, end_date),
        )
        cxc = [m for i in raw_cxc if (m := _map_cxc(i)) and m["total"] > 0]
        cxp = [m for i in raw_cxp if (m := _map_cxp(i)) and m["total"] > 0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    def _s(lst):
        t = sum(f["saldo_pendiente"] for f in lst)
        v = sum(f["saldo_pendiente"] for f in lst if f["dias_vencido"] > 0)
        return {"total": round(t,2), "vencido": round(v,2),
                "corriente": round(t-v,2), "count": len(lst),
                "pct_vencido": round(v/max(t,1)*100,1)}

    return {
        "cut_date": date.today().isoformat(),
        "cxc": _s(cxc), "cxp": _s(cxp),
        "flujo_neto_esperado": round(
            sum(f["saldo_pendiente"] for f in cxc) -
            sum(f["saldo_pendiente"] for f in cxp), 2),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
