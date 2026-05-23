"""
TaxnFin — Endpoints de CxC y CxP desde Contalink
backend/routes/contalink_cxc_cxp.py
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, UploadFile, File
from typing import Dict, Optional
from datetime import date, datetime, timezone
import logging, io
from pydantic import BaseModel

from core.database import db
from core.auth import get_current_user, get_active_company_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contalink", tags=["Contalink CxC/CxP"])
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


# ══════════════════════════════════════════════════════════════════════
# CATEGORIZACIÓN IA — CxC/CxP
# ══════════════════════════════════════════════════════════════════════

# Categorías disponibles para CxC/CxP (reutiliza el catálogo de cashflow-sync)
CXC_CATEGORIES = [
    {"code": "ING-001", "nombre": "Ventas de productos",       "tipo": "cxc"},
    {"code": "ING-002", "nombre": "Prestación de servicios",   "tipo": "cxc"},
    {"code": "ING-003", "nombre": "Honorarios profesionales",  "tipo": "cxc"},
    {"code": "ING-004", "nombre": "Arrendamiento cobrado",     "tipo": "cxc"},
    {"code": "ING-005", "nombre": "Cobro de anticipos",        "tipo": "cxc"},
    {"code": "ING-007", "nombre": "Intereses cobrados",        "tipo": "cxc"},
    {"code": "ING-099", "nombre": "Otros ingresos por cobrar", "tipo": "cxc"},
]

CXP_CATEGORIES = [
    {"code": "EGR-001", "nombre": "Nómina y salarios",           "tipo": "cxp"},
    {"code": "EGR-002", "nombre": "IMSS / INFONAVIT",            "tipo": "cxp"},
    {"code": "EGR-003", "nombre": "ISR (pago provisional)",      "tipo": "cxp"},
    {"code": "EGR-004", "nombre": "IVA (pago mensual)",          "tipo": "cxp"},
    {"code": "EGR-005", "nombre": "Renta / arrendamiento",       "tipo": "cxp"},
    {"code": "EGR-006", "nombre": "Proveedores de materia prima","tipo": "cxp"},
    {"code": "EGR-007", "nombre": "Servicios (luz, agua, gas)",  "tipo": "cxp"},
    {"code": "EGR-008", "nombre": "Telefonía e internet",        "tipo": "cxp"},
    {"code": "EGR-009", "nombre": "Publicidad y marketing",      "tipo": "cxp"},
    {"code": "EGR-010", "nombre": "Honorarios externos",         "tipo": "cxp"},
    {"code": "EGR-011", "nombre": "Viáticos y gastos de viaje",  "tipo": "cxp"},
    {"code": "EGR-012", "nombre": "Seguros y fianzas",           "tipo": "cxp"},
    {"code": "EGR-013", "nombre": "Mantenimiento y reparaciones","tipo": "cxp"},
    {"code": "EGR-015", "nombre": "Software y suscripciones",    "tipo": "cxp"},
    {"code": "EGR-016", "nombre": "Pago de crédito bancario",    "tipo": "cxp"},
    {"code": "EGR-017", "nombre": "Intereses pagados",           "tipo": "cxp"},
    {"code": "EGR-018", "nombre": "Comisiones bancarias",        "tipo": "cxp"},
    {"code": "EGR-020", "nombre": "Compra de activo fijo",       "tipo": "cxp"},
    {"code": "EGR-099", "nombre": "Otros egresos por pagar",     "tipo": "cxp"},
]


class CategoriaManual(BaseModel):
    nombre:        str        # nombre del cliente o proveedor
    tipo:          str        # "cxc" | "cxp"
    category_code: str
    category_name: str


@router.get("/categorias-cxc")
async def get_categorias_cxc(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Devuelve todas las categorías guardadas para CxC/CxP de esta empresa."""
    company_id = await get_active_company_id(request, current_user)
    docs = await db.cxc_categorias.find(
        {"company_id": company_id}, {"_id": 0}
    ).to_list(1000)
    # Devolver también el catálogo disponible
    return {
        "categorias_guardadas": docs,
        "catalogo_cxc": CXC_CATEGORIES,
        "catalogo_cxp": CXP_CATEGORIES,
    }


@router.post("/categoria-cxc")
async def save_categoria_manual(
    request: Request,
    item: CategoriaManual,
    current_user: Dict = Depends(get_current_user),
):
    """Guarda o actualiza manualmente la categoría de un cliente/proveedor."""
    company_id = await get_active_company_id(request, current_user)
    doc = {
        "company_id":    company_id,
        "nombre":        item.nombre,
        "tipo":          item.tipo,
        "category_code": item.category_code,
        "category_name": item.category_name,
        "categorized_by": "manual",
        "updated_at":    datetime.now(timezone.utc),
    }
    await db.cxc_categorias.update_one(
        {"company_id": company_id, "nombre": item.nombre, "tipo": item.tipo},
        {"$set": doc},
        upsert=True,
    )
    return {"ok": True, "nombre": item.nombre, "category_name": item.category_name}


@router.post("/auto-categorize-cxc")
async def auto_categorize_cxc(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    solo_sin_categoria: bool = Query(True),
):
    """
    Categoriza clientes/proveedores de CxC y CxP usando Claude API.
    - Lee las facturas del caché de Contalink
    - Manda los nombres a Claude para que asigne categoría
    - Guarda en colección cxc_categorias
    - Solo procesa los que no tienen categoría (solo_sin_categoria=True por default)
    """
    import httpx, os, json

    company_id = await get_active_company_id(request, current_user)

    # 1. Leer facturas del caché
    cxc_cached = await db.contalink_cache.find_one({"key": f"cxc_{company_id}_latest"})
    cxp_cached = await db.contalink_cache.find_one({"key": f"cxp_{company_id}_latest"})

    cxc_facturas = cxc_cached["data"].get("facturas", []) if cxc_cached else []
    cxp_facturas = cxp_cached["data"].get("facturas", []) if cxp_cached else []

    if not cxc_facturas and not cxp_facturas:
        return {"success": True, "message": "No hay datos de CxC/CxP para categorizar", "updated": 0}

    # 2. Si solo_sin_categoria, filtrar los que ya tienen categoría guardada
    if solo_sin_categoria:
        ya_categorizados = await db.cxc_categorias.find(
            {"company_id": company_id}, {"nombre": 1, "tipo": 1, "_id": 0}
        ).to_list(1000)
        ya_set = {(d["nombre"], d["tipo"]) for d in ya_categorizados}

        cxc_facturas = [f for f in cxc_facturas if (f.get("nombre") or f.get("cliente_nombre",""), "cxc") not in ya_set]
        cxp_facturas = [f for f in cxp_facturas if (f.get("nombre") or f.get("proveedor_nombre",""), "cxp") not in ya_set]

    if not cxc_facturas and not cxp_facturas:
        return {"success": True, "message": "Todos los clientes/proveedores ya tienen categoría", "updated": 0}

    # 3. Construir lista para el prompt (deduplicar por nombre)
    items_cxc = []
    seen = set()
    for f in cxc_facturas:
        nombre = (f.get("nombre") or f.get("cliente_nombre","")).strip()
        if nombre and nombre not in seen:
            seen.add(nombre)
            items_cxc.append({"nombre": nombre, "tipo": "cxc", "monto": f.get("saldo_pendiente", 0)})

    items_cxp = []
    seen2 = set()
    for f in cxp_facturas:
        nombre = (f.get("nombre") or f.get("proveedor_nombre","")).strip()
        if nombre and nombre not in seen2:
            seen2.add(nombre)
            items_cxp.append({"nombre": nombre, "tipo": "cxp", "monto": f.get("saldo_pendiente", 0)})

    all_items = items_cxc + items_cxp
    if not all_items:
        return {"success": True, "message": "No hay elementos nuevos para categorizar", "updated": 0}

    # 4. Construir prompt
    cat_cxc_text = "\n".join(f'  code="{c["code"]}" | nombre="{c["nombre"]}"' for c in CXC_CATEGORIES)
    cat_cxp_text = "\n".join(f'  code="{c["code"]}" | nombre="{c["nombre"]}"' for c in CXP_CATEGORIES)

    items_text = "\n".join(
        f'[{i}] nombre="{it["nombre"]}" | tipo={it["tipo"]} | monto={it["monto"]:.2f} MXN'
        for i, it in enumerate(all_items)
    )

    prompt = f"""Eres experto en contabilidad de empresas mexicanas.
Tu tarea es categorizar cuentas por cobrar (CxC) y cuentas por pagar (CxP).

CATEGORÍAS PARA CxC (ingresos pendientes de cobro):
{cat_cxc_text}

CATEGORÍAS PARA CxP (egresos pendientes de pago):
{cat_cxp_text}

CLIENTES Y PROVEEDORES A CATEGORIZAR:
{items_text}

INSTRUCCIONES:
- Los de tipo "cxc" son clientes que nos deben → usa categorías CxC (ING-xxx).
- Los de tipo "cxp" son proveedores a los que debemos → usa categorías CxP (EGR-xxx).
- Infiere la categoría por el nombre del cliente/proveedor.
  Ejemplos: "BIMBO" → EGR-006 (Proveedores materia prima), "TELMEX" → EGR-008 (Telefonía),
  "IMSS" → EGR-002, "SAT" o "HACIENDA" → EGR-003, cliente genérico → ING-001.
- Si no puedes inferir → ING-099 para cxc, EGR-099 para cxp.

Responde ÚNICAMENTE con un JSON array, sin texto adicional ni backticks:
[{{"nombre": "NOMBRE_CLIENTE", "tipo": "cxc", "category_code": "ING-001"}}, ...]
"""

    # 5. Llamar Claude API
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY no configurada en Railway")

    try:
        async with httpx.AsyncClient(timeout=60) as http:
            res = await http.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-5",
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            res.raise_for_status()
            data = res.json()
            raw_text = data["content"][0]["text"].strip()
    except Exception as e:
        logger.error(f"auto_categorize_cxc Claude API error: {e}")
        raise HTTPException(status_code=500, detail=f"Error llamando a Claude API: {str(e)}")

    # 6. Parsear respuesta
    try:
        clean = raw_text.replace("```json", "").replace("```", "").strip()
        assignments = json.loads(clean)
    except Exception as e:
        logger.error(f"auto_categorize_cxc JSON parse error: {raw_text[:300]}")
        raise HTTPException(status_code=500, detail=f"Error parseando respuesta IA: {str(e)}")

    # 7. Construir mapa de categorías
    all_cats = {c["code"]: c for c in CXC_CATEGORIES + CXP_CATEGORIES}

    # 8. Guardar en MongoDB
    updated = 0
    errors = []

    for assignment in assignments:
        nombre        = assignment.get("nombre", "").strip()
        tipo          = assignment.get("tipo", "cxc")
        category_code = assignment.get("category_code", "")

        if not nombre or not category_code:
            continue

        cat_doc = all_cats.get(category_code)
        if not cat_doc:
            errors.append(f"Código desconocido: {category_code} para {nombre}")
            continue

        try:
            await db.cxc_categorias.update_one(
                {"company_id": company_id, "nombre": nombre, "tipo": tipo},
                {"$set": {
                    "company_id":    company_id,
                    "nombre":        nombre,
                    "tipo":          tipo,
                    "category_code": category_code,
                    "category_name": cat_doc["nombre"],
                    "categorized_by": "ai",
                    "updated_at":    datetime.now(timezone.utc),
                }},
                upsert=True,
            )
            updated += 1
        except Exception as e:
            errors.append(f"Error guardando {nombre}: {str(e)}")

    logger.info(f"auto_categorize_cxc: company={company_id} updated={updated} errors={len(errors)}")
    return {
        "success": True,
        "processed": len(all_items),
        "updated": updated,
        "errors": errors,
        "message": f"✅ {updated} de {len(all_items)} clientes/proveedores categorizados con IA",
    }
