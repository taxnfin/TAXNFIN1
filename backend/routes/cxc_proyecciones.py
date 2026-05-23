"""
TaxnFin — Proyecciones manuales de CxC/CxP por semana
backend/routes/cxc_proyecciones.py

Registrar en server.py:
    from routes.cxc_proyecciones import router as cxc_proyecciones_router
    api_router.include_router(cxc_proyecciones_router)
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Optional, List
from datetime import datetime, timezone, date, timedelta
from pydantic import BaseModel
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cxc-proyecciones", tags=["CxC/CxP Proyecciones"])


class ProyeccionItem(BaseModel):
    nombre:   str
    tipo:     str           # "cxc" | "cxp"
    semana:   Optional[str] # "S1".."S52" | None = sin asignar
    monto:    float
    moneda:   str = "MXN"


class ProyeccionBatch(BaseModel):
    items: List[ProyeccionItem]


# ── GET /cxc-proyecciones ────────────────────────────────────────────
@router.get("")
async def get_proyecciones(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Devuelve todas las asignaciones de semana para CxC y CxP."""
    company_id = await get_active_company_id(request, current_user)
    docs = await db.cxc_proyecciones.find(
        {"company_id": company_id}, {"_id": 0}
    ).to_list(1000)
    return docs


# ── POST /cxc-proyecciones ───────────────────────────────────────────
@router.post("")
async def save_proyeccion(
    request: Request,
    item: ProyeccionItem,
    current_user: Dict = Depends(get_current_user),
):
    """Guarda o actualiza la semana asignada a un cliente/proveedor."""
    company_id = await get_active_company_id(request, current_user)

    doc = {
        "company_id": company_id,
        "nombre":     item.nombre,
        "tipo":       item.tipo,
        "semana":     item.semana,
        "monto":      item.monto,
        "moneda":     item.moneda,
        "updated_at": datetime.now(timezone.utc),
    }

    await db.cxc_proyecciones.update_one(
        {"company_id": company_id, "nombre": item.nombre, "tipo": item.tipo},
        {"$set": doc},
        upsert=True,
    )
    return {"ok": True, "semana": item.semana, "nombre": item.nombre}


# ── DELETE /cxc-proyecciones/{tipo}/{nombre} ─────────────────────────
@router.delete("/{tipo}/{nombre}")
async def delete_proyeccion(
    tipo: str,
    nombre: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Elimina la asignación de semana de un cliente/proveedor."""
    company_id = await get_active_company_id(request, current_user)
    await db.cxc_proyecciones.delete_one(
        {"company_id": company_id, "nombre": nombre, "tipo": tipo}
    )
    return {"ok": True}


# ── GET /cxc-proyecciones/por-semana ────────────────────────────────
@router.get("/por-semana")
async def get_proyecciones_por_semana(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """
    Devuelve ingresos y egresos proyectados agrupados por semana Y categoría.
    Incluye NC (montos negativos) correctamente por cliente.

    Formato:
    {
      "S14": {
        "cxc": 1234.56,
        "cxp": 789.00,
        "byCategory": {
          "Ventas de productos": { "cxc": 1000.0, "cxp": 0 }
        }
      }
    }
    """
    company_id = await get_active_company_id(request, current_user)

    docs = await db.cxc_proyecciones.find(
        {"company_id": company_id, "semana": {"$ne": None}}, {"_id": 0}
    ).to_list(1000)

    cat_docs = await db.cxc_categorias.find(
        {"company_id": company_id}, {"_id": 0}
    ).to_list(1000)
    cat_map = {(c["nombre"], c["tipo"]): c.get("category_name", "") for c in cat_docs}

    # Cada cliente tiene su monto exacto (incluyendo NC negativa por cliente)
    result = {}
    for doc in docs:
        semana = doc.get("semana")
        tipo   = doc.get("tipo", "cxc")
        monto  = doc.get("monto", 0)
        nombre = doc.get("nombre", "")
        if not semana:
            continue

        cat_name = cat_map.get((nombre, tipo), "")
        if not cat_name:
            cat_name = "CxC Contalink" if tipo == "cxc" else "CxP Contalink"

        if semana not in result:
            result[semana] = {"cxc": 0.0, "cxp": 0.0, "byCategory": {}}

        result[semana][tipo] = round(result[semana][tipo] + monto, 2)

        if cat_name not in result[semana]["byCategory"]:
            result[semana]["byCategory"][cat_name] = {"cxc": 0.0, "cxp": 0.0}
        result[semana]["byCategory"][cat_name][tipo] = round(
            result[semana]["byCategory"][cat_name][tipo] + monto, 2
        )

    return result


# ── GET /cxc-proyecciones/semanas-modelo ────────────────────────────
@router.get("/semanas-modelo")
async def get_semanas_modelo(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """
    Devuelve TODAS las semanas del año desde S1 (enero) hasta 18 semanas futuras.
    Incluye semanas pasadas para asignar cobros/pagos históricos.
    """
    company_id = await get_active_company_id(request, current_user)

    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    week_start_day = int(company.get("inicio_semana", 1)) if company else 1

    today = date.today()

    year_start = date(today.year, 1, 1)
    if week_start_day == 0:  # Domingo
        days_offset = (year_start.weekday() + 1) % 7
    else:  # Lunes (default)
        days_offset = year_start.weekday()

    model_start = year_start - timedelta(days=days_offset)

    if week_start_day == 0:
        curr_offset = (today.weekday() + 1) % 7
    else:
        curr_offset = today.weekday()
    current_week_start = today - timedelta(days=curr_offset)
    future_limit = current_week_start + timedelta(weeks=18)

    semanas = []
    i = 0
    ws = model_start
    while ws <= future_limit:
        we = ws + timedelta(weeks=1)
        is_current = ws <= today < we
        is_past    = we <= today and not is_current

        if is_past:
            data_type = "real"
        elif is_current:
            data_type = "actual"
        else:
            data_type = "proyectado"

        semanas.append({
            "label":      f"S{i + 1}",
            "dateLabel":  ws.strftime("%-d %b"),
            "weekStart":  ws.isoformat(),
            "weekEnd":    we.isoformat(),
            "dataType":   data_type,
        })
        ws = we
        i += 1

    return semanas
