# TaxnFin Admin Routes - v2
"""
TaxnFin — Panel de Administración de Plataforma
Solo accesible para hola@taxnfin.com (role=admin).
No expone ningún dato financiero de los clientes.
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, Request

from core.auth import get_current_user, hash_password
from core.database import db

router = APIRouter(prefix="/admin", tags=["Admin Plataforma"])

PLATFORM_ADMIN_EMAIL = "hola@taxnfin.com"

PLAN_PRICES_MXN = {
    "STARTER": 999,
    "GROWTH":  2499,
    "PRO":     4999,
}

VALID_PLANS = set(PLAN_PRICES_MXN.keys())


def _require_platform_admin(current_user: Dict) -> None:
    if current_user.get("role") != "admin" or current_user.get("email") != PLATFORM_ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Acceso exclusivo del administrador de plataforma")


def _user_estado(user: Dict) -> str:
    if user.get("estado") == "eliminado":
        return "eliminado"
    if not user.get("activo", True):
        return "pausado"
    return "activo"


# ── GET /admin/stats ───────────────────────────────────────────────────────────

@router.get("/stats")
async def admin_stats(current_user: Dict = Depends(get_current_user)):
    _require_platform_admin(current_user)

    now = datetime.now(timezone.utc)
    mes_inicio = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    cfos = await db.users.find({"role": "cfo"}, {"_id": 0, "activo": 1, "estado": 1, "plan": 1, "created_at": 1}).to_list(2000)

    activos   = [u for u in cfos if _user_estado(u) == "activo"]
    pausados  = [u for u in cfos if _user_estado(u) == "pausado"]
    eliminados= [u for u in cfos if _user_estado(u) == "eliminado"]

    mrr = sum(PLAN_PRICES_MXN.get(u.get("plan", "STARTER"), 999) for u in activos)

    nuevos = sum(
        1 for u in activos
        if (u.get("created_at") or "") >= mes_inicio
    )

    empresas_activas = await db.companies.count_documents({"activo": True})

    return {
        "despachos_activos":   len(activos),
        "despachos_pausados":  len(pausados),
        "despachos_eliminados":len(eliminados),
        "empresas_activas":    empresas_activas,
        "mrr_mxn":             mrr,
        "nuevos_este_mes":     nuevos,
    }


# ── GET /admin/despachos ───────────────────────────────────────────────────────

@router.get("/despachos")
async def listar_despachos(current_user: Dict = Depends(get_current_user)):
    _require_platform_admin(current_user)

    cfos = await db.users.find(
        {"role": "cfo"},
        {"_id": 0, "password_hash": 0},
    ).sort("created_at", 1).to_list(2000)

    result = []
    for cfo in cfos:
        cfo_id = cfo.get("id")

        # Count empresas activas (companies in their company_ids that are activo=True)
        cfo_company_ids = cfo.get("company_ids") or ([cfo.get("company_id")] if cfo.get("company_id") else [])
        empresas_activas = await db.companies.count_documents({"id": {"$in": cfo_company_ids}, "activo": True})

        # Count usuarios activos
        usuarios_activos = await db.users.count_documents({"invited_by": cfo_id, "activo": True})

        result.append({
            "user_id":          cfo_id,
            "nombre":           cfo.get("nombre"),
            "email":            cfo.get("email"),
            "plan":             cfo.get("plan", "STARTER"),
            "fecha_vencimiento_plan": cfo.get("fecha_vencimiento_plan"),
            "empresas_activas": empresas_activas,
            "usuarios_activos": usuarios_activos,
            "fecha_registro":   cfo.get("created_at"),
            "estado":           _user_estado(cfo),
            "motivo_pausa":     cfo.get("motivo_pausa"),
            "fecha_pausa":      cfo.get("fecha_pausa"),
            "ultimo_acceso":    cfo.get("ultimo_acceso"),
        })

    return {"despachos": result}


# ── PUT /admin/despachos/{user_id}/pausar ─────────────────────────────────────

@router.put("/despachos/{user_id}/pausar")
async def pausar_despacho(
    user_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    _require_platform_admin(current_user)

    cfo = await db.users.find_one({"id": user_id, "role": "cfo"}, {"_id": 0, "id": 1})
    if not cfo:
        raise HTTPException(status_code=404, detail="Despacho no encontrado")

    body   = await request.json()
    motivo = (body.get("motivo") or "").strip() or "Sin motivo especificado"
    now    = datetime.now(timezone.utc).isoformat()

    # Pause CFO
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "activo":       False,
            "estado":       "pausado",
            "motivo_pausa": motivo,
            "fecha_pausa":  now,
        }},
    )
    # Pause all team members invited by this CFO
    await db.users.update_many(
        {"invited_by": user_id},
        {"$set": {
            "activo":       False,
            "estado":       "pausado",
            "motivo_pausa": f"Despacho pausado: {motivo}",
            "fecha_pausa":  now,
        }},
    )

    return {"success": True, "motivo": motivo}


# ── PUT /admin/despachos/{user_id}/reactivar ──────────────────────────────────

@router.put("/despachos/{user_id}/reactivar")
async def reactivar_despacho(
    user_id: str,
    current_user: Dict = Depends(get_current_user),
):
    _require_platform_admin(current_user)

    cfo = await db.users.find_one({"id": user_id, "role": "cfo"}, {"_id": 0, "id": 1})
    if not cfo:
        raise HTTPException(status_code=404, detail="Despacho no encontrado")

    # Reactivate CFO
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"activo": True, "estado": "activo"}, "$unset": {"motivo_pausa": "", "fecha_pausa": ""}},
    )
    # Reactivate team members (only those paused by the CFO's pause, not manually deactivated)
    await db.users.update_many(
        {"invited_by": user_id, "estado": "pausado"},
        {"$set": {"activo": True, "estado": "activo"}, "$unset": {"motivo_pausa": "", "fecha_pausa": ""}},
    )

    return {"success": True}


# ── PUT /admin/despachos/{user_id}/plan ───────────────────────────────────────

@router.put("/despachos/{user_id}/plan")
async def cambiar_plan(
    user_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    _require_platform_admin(current_user)

    body              = await request.json()
    nuevo_plan: str   = (body.get("plan") or "").upper()
    fecha_venc: str   = body.get("fecha_vencimiento", "")

    if nuevo_plan not in VALID_PLANS:
        raise HTTPException(status_code=400, detail=f"Plan inválido. Use: {', '.join(VALID_PLANS)}")

    cfo = await db.users.find_one({"id": user_id, "role": "cfo"}, {"_id": 0, "plan": 1})
    if not cfo:
        raise HTTPException(status_code=404, detail="Despacho no encontrado")

    plan_anterior = cfo.get("plan", "STARTER")
    now           = datetime.now(timezone.utc).isoformat()

    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "plan":                    nuevo_plan,
            "fecha_vencimiento_plan":  fecha_venc or None,
        }},
    )

    await db.plan_historial.insert_one({
        "user_id":          user_id,
        "plan_anterior":    plan_anterior,
        "plan_nuevo":       nuevo_plan,
        "fecha_vencimiento":fecha_venc or None,
        "changed_by":       current_user["id"],
        "created_at":       now,
    })

    return {"success": True, "plan": nuevo_plan}


# ── DELETE /admin/despachos/{user_id} (soft delete) ───────────────────────────

@router.delete("/despachos/{user_id}")
async def eliminar_despacho(
    user_id: str,
    current_user: Dict = Depends(get_current_user),
):
    _require_platform_admin(current_user)

    cfo = await db.users.find_one({"id": user_id, "role": "cfo"}, {"_id": 0, "id": 1})
    if not cfo:
        raise HTTPException(status_code=404, detail="Despacho no encontrado")

    now = datetime.now(timezone.utc).isoformat()

    await db.users.update_one(
        {"id": user_id},
        {"$set": {"activo": False, "estado": "eliminado", "fecha_eliminado": now}},
    )
    # Soft-delete all team members
    await db.users.update_many(
        {"invited_by": user_id},
        {"$set": {"activo": False, "estado": "eliminado", "fecha_eliminado": now}},
    )

    return {"success": True}


# ── GET /admin/fix-admin-role (temporary) ─────────────────────────────────────

@router.get("/fix-admin-role")
async def fix_admin_role():
    """Temporary endpoint to fix hola@taxnfin.com role to admin"""
    result = await db.users.update_one(
        {"email": "hola@taxnfin.com"},
        {"$set": {"role": "admin"}}
    )
    user = await db.users.find_one({"email": "hola@taxnfin.com"}, {"_id": 0, "email": 1, "role": 1, "nombre": 1})
    return {"modified": result.modified_count, "user": user}


# ── POST /admin/setup-platform-admin (one-time, no auth) ──────────────────────

@router.get("/setup-platform-admin")
async def setup_platform_admin():
    """
    One-time bootstrap endpoint — creates hola@taxnfin.com with role=admin.
    Returns 409 if the user already exists, so it is safe to call multiple times.
    Remove or disable this endpoint after first use.
    """
    existing = await db.users.find_one({"email": PLATFORM_ADMIN_EMAIL}, {"_id": 0, "id": 1})
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"El administrador {PLATFORM_ADMIN_EMAIL} ya existe (id={existing['id']}). Endpoint desactivado.",
        )

    TEMP_PASSWORD = "TaxnFin2026!"
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    await db.users.insert_one({
        "id":                 user_id,
        "email":              PLATFORM_ADMIN_EMAIL,
        "nombre":             "TaxnFin Admin",
        "password_hash":      hash_password(TEMP_PASSWORD),
        "role":               "admin",
        "company_id":         user_id,
        "company_ids":        [],
        "empresas_asignadas": [],
        "activo":             True,
        "created_at":         now,
    })

    return {
        "success":  True,
        "message":  "Admin creado correctamente. Cambia la contraseña después del primer login.",
        "email":    PLATFORM_ADMIN_EMAIL,
        "password": TEMP_PASSWORD,
    }
