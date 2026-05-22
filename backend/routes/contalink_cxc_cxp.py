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
        return (date.today() - date.fromisoformat(str(fecha_str)[:10])).days
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


async def _fetch(client, rfc, transaction_type, document_type, start_date, end_date) -> list:
    """Pagina sobre /invoices/list/ para una combinación de transaction_type + document_type."""
    items, page = [], 0
    while True:
        raw = await client.get_invoices(
            rfc=rfc, transaction_type=transaction_type,
            document_type=document_type,
            start_date=start_date, end_date=end_date, page=page,
        )
        if isinstance(raw, dict) and raw.get("status") == 0:
            logger.warning(f"Contalink {transaction_type}/{document_type} status=0: {raw.get('message')}")
            break
        batch = _parse_list(raw)
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 50:
            break
        page += 1
    return items


async def _fetch_cxc(client, rfc, start_date, end_date) -> list:
    """
    CxC = facturas EMITIDAS (issued) tipo I.
    Igual que hace el sync/all exitoso: ("issued", "I")
    """
    return await _fetch(client, rfc, "issued", "I", start_date, end_date)


async def _fetch_cxp(client, rfc, start_date, end_date) -> list:
    """
    CxP = facturas RECIBIDAS (received) tipo I + tipo E.
    Igual que hace el sync/all exitoso: ("received","I") + ("received","E")
    """
    import asyncio
    r1, r2 = await asyncio.gather(
        _fetch(client, rfc, "received", "I", start_date, end_date),
        _fetch(client, rfc, "received", "E", start_date, end_date),
    )
    # Deduplicar por uuid
    seen, result = set(), []
    for inv in r1 + r2:
        uid = (inv.get("uuid") or inv.get("UUID") or inv.get("folio_fiscal") or
               str(inv.get("id", ""))).strip()
        if uid and uid not in seen:
            seen.add(uid)
            result.append(inv)
        elif not uid:
            result.append(inv)
    return result


def _map_inv(inv: dict, tipo: str) -> Optional[dict]:
    """Mapea una factura al formato CxC o CxP usando los campos reales de Contalink."""
    total = float(inv.get("total") or inv.get("monto") or 0)
    if total <= 0:
        return None

    # Excluir canceladas
    cancelado = inv.get("cancelado") or (inv.get("estado_cancelacion") == "cancelado")
    estatus   = (inv.get("estatus") or inv.get("status") or "vigente").lower()
    if cancelado or estatus in ("cancelado", "cancelada"):
        return None

    fecha_emision = (inv.get("fecha") or inv.get("fecha_emision") or
                     inv.get("issue_date") or "")
    metodo_pago   = inv.get("metodo_pago") or "PUE"
    fecha_venc    = inv.get("fecha_vencimiento") or inv.get("due_date") or ""
    if not fecha_venc and fecha_emision:
        dias_plazo = 30 if metodo_pago == "PPD" else 0
        try:
            fecha_venc = (date.fromisoformat(fecha_emision[:10]) +
                          timedelta(days=dias_plazo)).isoformat()
        except Exception:
            fecha_venc = fecha_emision

    uuid = (inv.get("uuid") or inv.get("UUID") or
            inv.get("folio_fiscal") or "").strip()

    base = {
        "uuid":             uuid,
        "folio":            inv.get("folio") or "",
        "fecha_emision":    fecha_emision,
        "fecha_vencimiento": fecha_venc,
        "moneda":           inv.get("moneda") or "MXN",
        "metodo_pago":      metodo_pago,
        "total":            total,
        "saldo_pendiente":  total,   # Contalink no devuelve monto pagado en el listado
        "estatus":          estatus,
        "dias_vencido":     _dias_vencido(fecha_venc),
    }

    if tipo == "cxc":
        base.update({
            "cliente_rfc":    inv.get("receptor_rfc") or inv.get("rfc_receptor") or "",
            "cliente_nombre": inv.get("receptor_nombre") or inv.get("nombre_receptor") or "",
            "monto_cobrado":  0,
        })
    else:
        base.update({
            "proveedor_rfc":   inv.get("emisor_rfc") or inv.get("rfc_emisor") or "",
            "proveedor_nombre":inv.get("emisor_nombre") or inv.get("nombre_emisor") or "",
            "monto_pagado":    0,
        })
    return base


def _aging_stats(facturas: list, tipo: str) -> dict:
    aging = {"corriente": 0, "vencido_30": 0, "vencido_60": 0,
             "vencido_90": 0, "vencido_mas90": 0}
    total_p = 0
    terceros = set()
    key_nombre = "cliente_nombre" if tipo == "cxc" else "proveedor_nombre"
    key_rfc    = "cliente_rfc"    if tipo == "cxc" else "proveedor_rfc"

    for f in facturas:
        s = f["saldo_pendiente"]
        d = f["dias_vencido"]
        total_p += s
        terceros.add(f.get(key_rfc) or f.get(key_nombre, ""))
        if d <= 0:     aging["corriente"]    += s
        elif d <= 30:  aging["vencido_30"]   += s
        elif d <= 60:  aging["vencido_60"]   += s
        elif d <= 90:  aging["vencido_90"]   += s
        else:          aging["vencido_mas90"] += s

    return {
        "aging":           {k: round(v, 2) for k, v in aging.items()},
        "total_pendiente": round(total_p, 2),
        "num_terceros":    len(terceros),
        "pct_vencido":     round(
            (total_p - aging["corriente"]) / max(total_p, 1) * 100, 1),
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
        if cached and (datetime.now(timezone.utc) - cached["created_at"]).total_seconds() < 14400:
            return cached["data"]

    try:
        client, rfc = await _get_client_and_creds(company_id)
        end_date   = date.today().isoformat()
        start_date = (date.today() - timedelta(days=days_back)).isoformat()
        raw      = await _fetch_cxc(client, rfc, start_date, end_date)
        facturas = [m for inv in raw if (m := _map_inv(inv, "cxc"))]
        logger.info(f"CxC company={company_id}: {len(raw)} raw → {len(facturas)} vigentes")
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
        if cached and (datetime.now(timezone.utc) - cached["created_at"]).total_seconds() < 14400:
            return cached["data"]

    try:
        client, rfc = await _get_client_and_creds(company_id)
        end_date   = date.today().isoformat()
        start_date = (date.today() - timedelta(days=days_back)).isoformat()
        raw      = await _fetch_cxp(client, rfc, start_date, end_date)
        facturas = [m for inv in raw if (m := _map_inv(inv, "cxp"))]
        logger.info(f"CxP company={company_id}: {len(raw)} raw → {len(facturas)} vigentes")
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
            _fetch_cxc(client, rfc, start_date, end_date),
            _fetch_cxp(client, rfc, start_date, end_date),
        )
        cxc = [m for i in raw_cxc if (m := _map_inv(i, "cxc"))]
        cxp = [m for i in raw_cxp if (m := _map_inv(i, "cxp"))]
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
