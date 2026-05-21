"""
TaxnFin — Endpoints de CxC y CxP desde Contalink
Agrega al router existente de contalink o al server.py

Ruta sugerida: backend/routes/contalink_cxc_cxp.py
Registrar en server.py:
    from routes.contalink_cxc_cxp import router as cxc_cxp_router
    app.include_router(cxc_cxp_router)
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Dict, Optional
from datetime import date, datetime, timezone
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contalink", tags=["Contalink CxC/CxP"])


async def _get_contalink_client(company_id: str):
    """Obtiene el ContalinkClient para la empresa activa."""
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
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key de Contalink no configurada.")

    from services.contalink import ContalinkClient
    return ContalinkClient(api_key)


# ══════════════════════════════════════════════════════════════════════
# CUENTAS POR COBRAR
# ══════════════════════════════════════════════════════════════════════

@router.get("/cxc")
async def get_cuentas_por_cobrar(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    cut_date: Optional[str] = Query(None, description="Fecha de corte YYYY-MM-DD (default: hoy)"),
    start_date: Optional[str] = Query(None, description="Inicio periodo emisión YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Fin periodo emisión YYYY-MM-DD"),
    refresh: bool = Query(False, description="Forzar recarga desde Contalink (ignora caché)"),
):
    """
    Cuentas por Cobrar desde Contalink.
    Devuelve facturas emitidas con saldo pendiente, agrupadas con KPIs de aging.
    """
    company_id = await get_active_company_id(request, current_user)
    cut = cut_date or date.today().isoformat()

    # ── Caché en MongoDB (TTL 4 horas) ──────────────────────────────
    cache_key = f"cxc_{company_id}_{cut}"
    if not refresh:
        cached = await db.contalink_cache.find_one({"key": cache_key})
        if cached:
            edad_horas = (datetime.now(timezone.utc) - cached["created_at"]).seconds / 3600
            if edad_horas < 4:
                return cached["data"]

    # ── Traer de Contalink ───────────────────────────────────────────
    try:
        client = await _get_contalink_client(company_id)
        facturas = await client.get_cuentas_por_cobrar(
            cut_date=cut,
            start_date=start_date,
            end_date=end_date,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo CxC de Contalink: {e}")
        raise HTTPException(status_code=500, detail=f"Error consultando Contalink: {str(e)}")

    # ── Calcular KPIs de aging ───────────────────────────────────────
    aging = {"corriente": 0, "vencido_30": 0, "vencido_60": 0, "vencido_90": 0, "vencido_mas90": 0}
    total_pendiente = 0
    clientes_unicos = set()

    for f in facturas:
        saldo = f.get("saldo_pendiente", 0)
        dias  = f.get("dias_vencido", 0)
        total_pendiente += saldo
        clientes_unicos.add(f.get("cliente_rfc") or f.get("cliente_nombre", ""))

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

    result = {
        "cut_date":         cut,
        "total_pendiente":  round(total_pendiente, 2),
        "num_facturas":     len(facturas),
        "num_clientes":     len(clientes_unicos),
        "aging":            {k: round(v, 2) for k, v in aging.items()},
        "pct_vencido":      round((total_pendiente - aging["corriente"]) / max(total_pendiente, 1) * 100, 1),
        "facturas":         facturas,
        "source":           "contalink",
        "fetched_at":       datetime.now(timezone.utc).isoformat(),
    }

    # Guardar caché
    await db.contalink_cache.update_one(
        {"key": cache_key},
        {"$set": {"key": cache_key, "data": result, "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )

    return result


# ══════════════════════════════════════════════════════════════════════
# CUENTAS POR PAGAR
# ══════════════════════════════════════════════════════════════════════

@router.get("/cxp")
async def get_cuentas_por_pagar(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    cut_date: Optional[str] = Query(None, description="Fecha de corte YYYY-MM-DD (default: hoy)"),
    start_date: Optional[str] = Query(None, description="Inicio periodo emisión YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Fin periodo emisión YYYY-MM-DD"),
    refresh: bool = Query(False, description="Forzar recarga desde Contalink"),
):
    """
    Cuentas por Pagar desde Contalink.
    Devuelve facturas recibidas con saldo pendiente, agrupadas con KPIs de aging.
    """
    company_id = await get_active_company_id(request, current_user)
    cut = cut_date or date.today().isoformat()

    cache_key = f"cxp_{company_id}_{cut}"
    if not refresh:
        cached = await db.contalink_cache.find_one({"key": cache_key})
        if cached:
            edad_horas = (datetime.now(timezone.utc) - cached["created_at"]).seconds / 3600
            if edad_horas < 4:
                return cached["data"]

    try:
        client = await _get_contalink_client(company_id)
        facturas = await client.get_cuentas_por_pagar(
            cut_date=cut,
            start_date=start_date,
            end_date=end_date,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo CxP de Contalink: {e}")
        raise HTTPException(status_code=500, detail=f"Error consultando Contalink: {str(e)}")

    aging = {"corriente": 0, "vencido_30": 0, "vencido_60": 0, "vencido_90": 0, "vencido_mas90": 0}
    total_pendiente = 0
    proveedores_unicos = set()

    for f in facturas:
        saldo = f.get("saldo_pendiente", 0)
        dias  = f.get("dias_vencido", 0)
        total_pendiente += saldo
        proveedores_unicos.add(f.get("proveedor_rfc") or f.get("proveedor_nombre", ""))

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

    result = {
        "cut_date":          cut,
        "total_pendiente":   round(total_pendiente, 2),
        "num_facturas":      len(facturas),
        "num_proveedores":   len(proveedores_unicos),
        "aging":             {k: round(v, 2) for k, v in aging.items()},
        "pct_vencido":       round((total_pendiente - aging["corriente"]) / max(total_pendiente, 1) * 100, 1),
        "facturas":          facturas,
        "source":            "contalink",
        "fetched_at":        datetime.now(timezone.utc).isoformat(),
    }

    await db.contalink_cache.update_one(
        {"key": cache_key},
        {"$set": {"key": cache_key, "data": result, "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )

    return result


# ══════════════════════════════════════════════════════════════════════
# RESUMEN COMBINADO (para TreasuryDecisions)
# ══════════════════════════════════════════════════════════════════════

@router.get("/cxc-cxp-summary")
async def get_cxc_cxp_summary(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    cut_date: Optional[str] = Query(None),
):
    """
    Resumen combinado CxC + CxP para el dashboard de Tesorería.
    Un solo call que devuelve los totales y aging de ambas.
    """
    company_id = await get_active_company_id(request, current_user)
    cut = cut_date or date.today().isoformat()

    try:
        client = await _get_contalink_client(company_id)
        cxc_facturas, cxp_facturas = await __import__("asyncio").gather(
            client.get_cuentas_por_cobrar(cut_date=cut),
            client.get_cuentas_por_pagar(cut_date=cut),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    def _summarize(facturas, saldo_key="saldo_pendiente"):
        total = sum(f.get(saldo_key, 0) for f in facturas)
        vencido = sum(f.get(saldo_key, 0) for f in facturas if f.get("dias_vencido", 0) > 0)
        return {
            "total":     round(total, 2),
            "vencido":   round(vencido, 2),
            "corriente": round(total - vencido, 2),
            "count":     len(facturas),
            "pct_vencido": round(vencido / max(total, 1) * 100, 1),
        }

    return {
        "cut_date": cut,
        "cxc": _summarize(cxc_facturas),
        "cxp": _summarize(cxp_facturas),
        "flujo_neto_esperado": round(
            sum(f.get("saldo_pendiente", 0) for f in cxc_facturas) -
            sum(f.get("saldo_pendiente", 0) for f in cxp_facturas),
            2
        ),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
