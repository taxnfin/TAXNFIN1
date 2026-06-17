"""
TaxnFin — Proyecciones manuales de CxC/CxP por semana
backend/routes/cxc_proyecciones.py

Registrar en server.py:
    from routes.cxc_proyecciones import router as cxc_proyecciones_router
    api_router.include_router(cxc_proyecciones_router)
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Dict, Optional, List
from datetime import datetime, timezone, date, timedelta
from pydantic import BaseModel
import logging, uuid

from core.database import db
from core.auth import get_current_user, get_active_company_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cxc-proyecciones", tags=["CxC/CxP Proyecciones"])

MAX_ROLLS = 8


def _compute_week_info(week_start_day: int = 1):
    """Returns (model_start, current_week_num) matching semanas-modelo logic."""
    today = date.today()
    year_start = date(today.year, 1, 1)
    if week_start_day == 0:
        model_offset = (year_start.weekday() + 1) % 7
        curr_offset  = (today.weekday() + 1) % 7
    else:
        model_offset = year_start.weekday()
        curr_offset  = today.weekday()
    model_start = year_start - timedelta(days=model_offset)
    current_week_start = today - timedelta(days=curr_offset)
    current_week_num = (current_week_start - model_start).days // 7 + 1
    return model_start, current_week_num


async def _apply_rolling(company_id: str, docs: List[Dict], current_week_num: int) -> List[Dict]:
    """
    Roll past-due projections to the next upcoming week.
    Writes updates to MongoDB. Returns docs with updated fields.
    Stops rolling at MAX_ROLLS weeks past the original assignment.
    """
    now = datetime.now(timezone.utc)
    updated = []
    for doc in docs:
        semana = doc.get("semana")
        if not semana or not semana.startswith("S"):
            updated.append(doc)
            continue
        try:
            doc_week_num = int(semana[1:])
        except ValueError:
            updated.append(doc)
            continue

        if doc_week_num >= current_week_num:
            updated.append(doc)
            continue

        # Past due — compute roll
        rolled_from  = doc.get("rolled_from", semana)
        rolled_count = doc.get("rolled_count", 0)
        new_count    = rolled_count + 1

        if new_count > MAX_ROLLS:
            if doc.get("rolled_count") != MAX_ROLLS:
                await db.cxc_proyecciones.update_one(
                    {"company_id": company_id, "nombre": doc["nombre"], "tipo": doc["tipo"]},
                    {"$set": {"rolled_count": MAX_ROLLS, "auto_rolled": True,
                               "rolled_from": rolled_from, "updated_at": now}},
                )
                doc["rolled_count"] = MAX_ROLLS
                doc["auto_rolled"]  = True
                doc["rolled_from"]  = rolled_from
            updated.append(doc)
            continue

        new_semana = f"S{current_week_num + 1}"
        await db.cxc_proyecciones.update_one(
            {"company_id": company_id, "nombre": doc["nombre"], "tipo": doc["tipo"]},
            {"$set": {"semana": new_semana, "auto_rolled": True, "rolled_from": rolled_from,
                       "rolled_count": new_count, "updated_at": now}},
        )
        logger.info(
            f"[ROLLING] {doc['nombre']} ({doc['tipo']}) {semana}→{new_semana} "
            f"roll#{new_count} company={company_id}"
        )
        doc = {**doc, "semana": new_semana, "auto_rolled": True,
               "rolled_from": rolled_from, "rolled_count": new_count}
        updated.append(doc)

    return updated


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
    """Devuelve todas las asignaciones de semana para CxC y CxP, aplicando rolling automático."""
    company_id = await get_active_company_id(request, current_user)
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    week_start_day = int(company.get("inicio_semana", 1)) if company else 1
    _, current_week_num = _compute_week_info(week_start_day)

    docs = await db.cxc_proyecciones.find(
        {"company_id": company_id}, {"_id": 0}
    ).to_list(1000)
    docs = await _apply_rolling(company_id, docs, current_week_num)
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


# ── DELETE /cxc-proyecciones/bulk ────────────────────────────────────
@router.delete("/bulk")
async def delete_proyecciones_bulk(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    source: str = Query(None, description="Filtrar por source (alegra, contalink, manual)"),
):
    """Elimina múltiples proyecciones filtradas por source."""
    company_id = await get_active_company_id(request, current_user)
    query: dict = {"company_id": company_id}
    if source:
        query["source"] = source
    result = await db.cxc_proyecciones.delete_many(query)
    return {"ok": True, "deleted": result.deleted_count}


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
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    week_start_day = int(company.get("inicio_semana", 1)) if company else 1
    _, current_week_num = _compute_week_info(week_start_day)

    docs = await db.cxc_proyecciones.find(
        {"company_id": company_id, "semana": {"$ne": None}}, {"_id": 0}
    ).to_list(1000)
    docs = await _apply_rolling(company_id, docs, current_week_num)

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
        moneda = doc.get("moneda", "MXN")
        if not semana:
            continue

        cat_name = cat_map.get((nombre, tipo), "")
        if not cat_name:
            source = doc.get("source", "")
            if tipo == "cxc":
                cat_name = "CxC Alegra" if source == "alegra" else "CxC Contalink" if source == "contalink" else "CxC"
            else:
                cat_name = "CxP Alegra" if source == "alegra" else "CxP Contalink" if source == "contalink" else "CxP"

        if semana not in result:
            result[semana] = {"cxc": 0.0, "cxp": 0.0, "byCategory": {}}

        result[semana][tipo] = round(result[semana][tipo] + monto, 2)

        if cat_name not in result[semana]["byCategory"]:
            result[semana]["byCategory"][cat_name] = {"cxc": 0.0, "cxp": 0.0, "items": []}
        result[semana]["byCategory"][cat_name][tipo] = round(
            result[semana]["byCategory"][cat_name][tipo] + monto, 2
        )
        # Guardar ítem individual para que el drill-down muestre el beneficiario real
        result[semana]["byCategory"][cat_name]["items"].append({
            "nombre": nombre,
            "tipo":   tipo,
            "monto":  monto,
            "moneda": moneda,
        })

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


# ── POST /cxc-proyecciones/sincronizar ──────────────────────────────
@router.post("/sincronizar")
async def sincronizar_montos_con_aging(
    request: Request,
    tipo: str = Query(..., description='"cxc" | "cxp"'),
    current_user: Dict = Depends(get_current_user),
):
    """Re-alinea los montos guardados con el Aging actual (caché de Contalink).

    - Proveedor/cliente que ya NO está en el Aging → se asume pagado/cobrado:
      archiva la diferencia y elimina la asignación.
    - Monto guardado ≠ pendiente actual → archiva la diferencia y actualiza
      el monto al pendiente vigente.

    Cada cambio queda en cxc_proyecciones_hist para el comparativo
    proyectado vs pagado por semana.
    """
    if tipo not in ("cxc", "cxp"):
        raise HTTPException(status_code=400, detail="tipo debe ser 'cxc' o 'cxp'")
    company_id = await get_active_company_id(request, current_user)

    cache = await db.contalink_cache.find_one({"key": f"{tipo}_{company_id}_latest"})
    facturas = (cache or {}).get("data", {}).get("facturas", [])
    if not facturas:
        raise HTTPException(status_code=404,
            detail="No hay datos de Aging en caché para sincronizar. Sube primero el Excel.")

    # Pendiente actual por nombre (las filas de Contalink son una por proveedor/cliente)
    pend_map: Dict[str, float] = {}
    for f in facturas:
        nombre = (f.get("nombre") or f.get("cliente_nombre") or f.get("proveedor_nombre") or "").strip()
        if not nombre:
            continue
        pend_map[nombre] = pend_map.get(nombre, 0.0) + float(f.get("saldo_pendiente") or f.get("total") or 0)

    docs = await db.cxc_proyecciones.find(
        {"company_id": company_id, "tipo": tipo, "semana": {"$ne": None}}, {"_id": 0}
    ).to_list(2000)

    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    week_start_day = int(company.get("inicio_semana", 1)) if company else 1
    _, current_week_num = _compute_week_info(week_start_day)
    docs = await _apply_rolling(company_id, docs, current_week_num)

    now = datetime.now(timezone.utc)
    eliminados = actualizados = sin_cambio = 0
    cambios = []
    for doc in docs:
        nombre = doc.get("nombre", "")
        monto_guardado = float(doc.get("monto", 0) or 0)
        pendiente = pend_map.get(nombre)
        if pendiente is not None and abs(pendiente - monto_guardado) <= 1:
            sin_cambio += 1
            continue
        hist = {
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "tipo": tipo,
            "nombre": nombre,
            "semana": doc.get("semana"),
            "monto_proyectado": round(monto_guardado, 2),
            "pendiente_actual": round(pendiente, 2) if pendiente is not None else 0.0,
            # diferencia > 0 = dejó de estar pendiente (pagado/cobrado estimado)
            "diferencia": round(monto_guardado - (pendiente or 0.0), 2),
            "accion": "eliminado" if pendiente is None else "actualizado",
            "sync_at": now,
            "sync_by": current_user["id"],
        }
        await db.cxc_proyecciones_hist.insert_one(hist)
        hist.pop("_id", None)
        if pendiente is None:
            await db.cxc_proyecciones.delete_one(
                {"company_id": company_id, "nombre": nombre, "tipo": tipo})
            eliminados += 1
        else:
            await db.cxc_proyecciones.update_one(
                {"company_id": company_id, "nombre": nombre, "tipo": tipo},
                {"$set": {"monto": round(pendiente, 2), "updated_at": now}})
            actualizados += 1
        cambios.append(hist)

    logger.info(f"[SYNC PROYECCIONES] {tipo} company={company_id}: "
                f"{actualizados} actualizados, {eliminados} eliminados, {sin_cambio} sin cambio")
    return {"ok": True, "tipo": tipo, "eliminados": eliminados,
            "actualizados": actualizados, "sin_cambio": sin_cambio, "cambios": cambios}


# ── DELETE /cxc-proyecciones/clear ──────────────────────────────────
@router.delete("/clear")
async def clear_cxc_proyecciones(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Elimina todas las proyecciones manuales CxC/CxP de la empresa activa."""
    company_id = await get_active_company_id(request, current_user)
    result = await db.cxc_proyecciones.delete_many({"company_id": company_id})
    return {"deleted": result.deleted_count, "company_id": company_id}


# ── GET /cxc-proyecciones/historial-sync ────────────────────────────
@router.get("/historial-sync")
async def get_historial_sync(
    request: Request,
    tipo: Optional[str] = Query(None, description='Filtrar por "cxc" | "cxp"'),
    current_user: Dict = Depends(get_current_user),
):
    """Histórico de diferencias registradas por las sincronizaciones:
    qué se proyectó por semana vs qué dejó de estar pendiente (pagado estimado)."""
    company_id = await get_active_company_id(request, current_user)
    q: Dict = {"company_id": company_id}
    if tipo:
        q["tipo"] = tipo
    docs = await db.cxc_proyecciones_hist.find(q, {"_id": 0}).sort("sync_at", -1).to_list(5000)
    return docs
