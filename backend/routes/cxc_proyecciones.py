"""
TaxnFin — Proyecciones manuales de CxC/CxP por semana
backend/routes/cxc_proyecciones.py

Registrar en server.py:
    from routes.cxc_proyecciones import router as cxc_proyecciones_router
    api_router.include_router(cxc_proyecciones_router)
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cxc-proyecciones", tags=["CxC/CxP Proyecciones"])


class ProyeccionItem(BaseModel):
    nombre:   str           # Nombre del cliente o proveedor
    tipo:     str           # "cxc" | "cxp"
    semana:   Optional[str] # "S1".."S18" | None = sin asignar
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


# ── DELETE /cxc-proyecciones/{nombre} ───────────────────────────────
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
    Devuelve ingresos y egresos proyectados agrupados por semana.
    Usado por CashflowProjections para inyectar en el modelo.
    Formato: { "S1": { "cxc": 1234.56, "cxp": 789.00 }, ... }
    """
    company_id = await get_active_company_id(request, current_user)
    docs = await db.cxc_proyecciones.find(
        {"company_id": company_id, "semana": {"$ne": None}}, {"_id": 0}
    ).to_list(1000)

    result = {}
    for doc in docs:
        semana = doc.get("semana")
        tipo   = doc.get("tipo", "cxc")
        monto  = doc.get("monto", 0)
        if not semana:
            continue
        if semana not in result:
            result[semana] = {"cxc": 0.0, "cxp": 0.0}
        result[semana][tipo] = round(result[semana][tipo] + monto, 2)

    return result


# ── GET /cxc-proyecciones/semanas-modelo ────────────────────────────
@router.get("/semanas-modelo")
async def get_semanas_modelo(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """
    Devuelve las semanas proyectadas del modelo rolling actual.
    Calcula desde la semana actual hasta 18 semanas adelante.
    Formato: [{ label: "S14", dateLabel: "25 may", weekStart: "2026-05-25", weekEnd: "2026-06-01" }]
    """
    from datetime import date, timedelta
    import math

    company_id = await get_active_company_id(request, current_user)

    # Leer inicio_semana de la empresa (0=Dom, 1=Lun default)
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    week_start_day = int(company.get("inicio_semana", 1)) if company else 1

    today = date.today()

    # Calcular inicio de la semana actual
    days_since_start = (today.weekday() - (week_start_day - 1)) % 7
    current_week_start = today - timedelta(days=days_since_start)

    # Calcular desde cuándo empieza el modelo (17 semanas atrás para modelo de 30 semanas)
    model_start = current_week_start - timedelta(weeks=17)

    semanas = []
    for i in range(30):
        ws = model_start + timedelta(weeks=i)
        we = ws + timedelta(weeks=1)
        is_past    = we.isoformat() <= today.isoformat()
        is_current = ws <= today < we
        data_type  = 'real' if is_past else ('actual' if is_current else 'proyectado')

        if data_type == 'proyectado':
            semanas.append({
                "label":      f"S{i + 1}",
                "dateLabel":  ws.strftime("%d %b").lstrip("0"),
                "weekStart":  ws.isoformat(),
                "weekEnd":    we.isoformat(),
                "dataType":   data_type,
            })

    return semanas
