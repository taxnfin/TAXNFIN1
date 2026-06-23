"""
TaxnFin — Gestión de Usuarios
Invitar, rolar, asignar empresas y desactivar usuarios dentro del scope del CFO.
Regla de oro: ningún usuario puede ver ni tocar datos de empresas que no le pertenecen.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, Request

from core.auth import get_current_user, hash_password
from core.database import db

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])

PLATFORM_ADMIN_EMAIL = "hola@taxnfin.com"
ASSIGNABLE_ROLES     = {"cfo", "contador", "viewer"}


# ── Guards ─────────────────────────────────────────────────────────────────────

def _require_cfo(current_user: Dict) -> None:
    if current_user.get("role") not in ("cfo", "admin"):
        raise HTTPException(status_code=403, detail="Solo el CFO puede realizar esta acción")


def _cfo_company_ids(current_user: Dict) -> set:
    return set(current_user.get("company_ids") or [current_user.get("company_id", "")])


def _require_all_companies_owned(company_ids: List[str], current_user: Dict) -> None:
    owned = _cfo_company_ids(current_user)
    for cid in company_ids:
        if cid not in owned:
            raise HTTPException(
                status_code=403,
                detail=f"No tienes acceso a la empresa {cid[:8]}…",
            )


async def _require_user_in_cfo_scope(user_id: str, current_user: Dict) -> Dict:
    """Target user must share at least one company with the requesting CFO."""
    target = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    target_companies = set(
        target.get("empresas_asignadas") or target.get("company_ids") or [target.get("company_id", "")]
    )
    if not target_companies.intersection(_cfo_company_ids(current_user)):
        raise HTTPException(status_code=403, detail="No tienes permisos sobre este usuario")
    return target


def _serialize(u: Dict) -> Dict:
    return {
        "user_id":            u.get("id"),
        "nombre":             u.get("nombre"),
        "email":              u.get("email"),
        "rol":                u.get("role"),
        "empresas_asignadas": u.get("empresas_asignadas") or u.get("company_ids") or [],
        "invited_by":         u.get("invited_by"),
        "activo":             u.get("activo", True),
        "created_at":         u.get("created_at"),
    }


# ── GET /usuarios/mis-empresas ─────────────────────────────────────────────────

@router.get("/mis-empresas")
async def mis_empresas(current_user: Dict = Depends(get_current_user)):
    role = current_user.get("role")
    if role in ("cfo", "admin"):
        ids = list(_cfo_company_ids(current_user))
    else:
        ids = (
            current_user.get("empresas_asignadas")
            or current_user.get("company_ids")
            or [current_user.get("company_id", "")]
        )

    companies = await db.companies.find(
        {"id": {"$in": ids}, "activo": True},
        {"_id": 0, "id": 1, "nombre": 1, "rfc": 1},
    ).to_list(200)
    return {"empresas": companies}


# ── GET /usuarios/mis-usuarios ─────────────────────────────────────────────────

@router.get("/mis-usuarios")
async def mis_usuarios(current_user: Dict = Depends(get_current_user)):
    _require_cfo(current_user)
    cfo_ids = list(_cfo_company_ids(current_user))

    users = await db.users.find(
        {
            "$or": [
                {"company_ids":        {"$in": cfo_ids}},
                {"empresas_asignadas": {"$in": cfo_ids}},
                {"company_id":         {"$in": cfo_ids}},
            ]
        },
        {"_id": 0, "password_hash": 0},
    ).to_list(500)

    # Exclude platform admin and self
    users = [
        u for u in users
        if u.get("email") != PLATFORM_ADMIN_EMAIL
        and u.get("id") != current_user.get("id")
    ]

    activos   = [_serialize(u) for u in users if u.get("activo", True)]
    inactivos = [_serialize(u) for u in users if not u.get("activo", True)]
    return {"activos": activos, "inactivos": inactivos}


# ── GET /usuarios/empresa/{company_id} ────────────────────────────────────────

@router.get("/empresa/{company_id}")
async def listar_por_empresa(
    company_id: str,
    current_user: Dict = Depends(get_current_user),
):
    _require_cfo(current_user)
    _require_all_companies_owned([company_id], current_user)

    users = await db.users.find(
        {
            "activo": True,
            "$or": [
                {"company_ids":        company_id},
                {"empresas_asignadas": company_id},
                {"company_id":         company_id},
            ],
        },
        {"_id": 0, "password_hash": 0},
    ).to_list(200)

    return {"usuarios": [_serialize(u) for u in users]}


# ── POST /usuarios/invitar ─────────────────────────────────────────────────────

@router.post("/invitar")
async def invitar_usuario(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    _require_cfo(current_user)
    body = await request.json()

    email:       str       = (body.get("email") or "").strip().lower()
    nombre:      str       = (body.get("nombre") or "").strip()
    rol:         str       = (body.get("rol") or "viewer").lower()
    company_ids: List[str] = body.get("company_ids") or []

    if not email or not nombre:
        raise HTTPException(status_code=400, detail="Email y nombre son obligatorios")
    if rol not in ("contador", "viewer"):
        raise HTTPException(status_code=400, detail="Rol debe ser 'contador' o 'viewer'")
    if not company_ids:
        raise HTTPException(status_code=400, detail="Debes asignar al menos una empresa")

    _require_all_companies_owned(company_ids, current_user)

    existing = await db.users.find_one({"email": email}, {"_id": 0, "id": 1})
    if existing:
        raise HTTPException(status_code=400, detail="Este email ya está registrado")

    temp_password = str(uuid.uuid4()).replace("-", "")[:8].upper()
    user_id       = str(uuid.uuid4())
    now           = datetime.now(timezone.utc).isoformat()

    user_doc = {
        "id":                   user_id,
        "email":                email,
        "nombre":               nombre,
        "role":                 rol,
        "company_id":           company_ids[0],
        "company_ids":          company_ids,
        "empresas_asignadas":   company_ids,
        "invited_by":           current_user["id"],
        "activo":               True,
        "must_change_password": True,
        "password_hash":        hash_password(temp_password),
        "created_at":           now,
    }
    await db.users.insert_one(user_doc)

    await db.invitaciones.insert_one({
        "id":          str(uuid.uuid4()),
        "token":       str(uuid.uuid4()),
        "email":       email,
        "user_id":     user_id,
        "company_ids": company_ids,
        "invited_by":  current_user["id"],
        "rol":         rol,
        "expires_at":  (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at":  now,
    })

    # Create indexes on first use (idempotent)
    await db.users.create_index("email", unique=True, background=True)
    await db.users.create_index("invited_by", background=True)

    return {
        "success":       True,
        "user_id":       user_id,
        "temp_password": temp_password,
        "nombre":        nombre,
        "email":         email,
    }


# ── PUT /usuarios/{user_id}/rol ────────────────────────────────────────────────

@router.put("/{user_id}/rol")
async def cambiar_rol(
    user_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    _require_cfo(current_user)
    target = await _require_user_in_cfo_scope(user_id, current_user)
    if target.get("email") == PLATFORM_ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="No puedes modificar al administrador de la plataforma")

    body      = await request.json()
    nuevo_rol = (body.get("rol") or "").lower()

    if nuevo_rol not in ASSIGNABLE_ROLES:
        raise HTTPException(status_code=400, detail="Rol inválido. Use: cfo, contador o viewer")
    if nuevo_rol == "admin":
        raise HTTPException(status_code=403, detail="No se puede asignar rol admin")

    await db.users.update_one({"id": user_id}, {"$set": {"role": nuevo_rol}})
    return {"success": True, "rol": nuevo_rol}


# ── PUT /usuarios/{user_id}/empresas ──────────────────────────────────────────

@router.put("/{user_id}/empresas")
async def actualizar_empresas(
    user_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    _require_cfo(current_user)
    await _require_user_in_cfo_scope(user_id, current_user)

    body:        Dict      = await request.json()
    company_ids: List[str] = body.get("company_ids") or []

    if not company_ids:
        raise HTTPException(status_code=400, detail="Debes asignar al menos una empresa")
    _require_all_companies_owned(company_ids, current_user)

    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "empresas_asignadas": company_ids,
            "company_ids":        company_ids,
            "company_id":         company_ids[0],
        }},
    )
    return {"success": True, "company_ids": company_ids}


# ── DELETE /usuarios/{user_id} (soft delete) ──────────────────────────────────

@router.delete("/{user_id}")
async def desactivar_usuario(
    user_id: str,
    current_user: Dict = Depends(get_current_user),
):
    _require_cfo(current_user)
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="No puedes desactivarte a ti mismo")
    target = await _require_user_in_cfo_scope(user_id, current_user)
    if target.get("email") == PLATFORM_ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="No puedes desactivar al administrador de la plataforma")

    await db.users.update_one({"id": user_id}, {"$set": {"activo": False}})
    return {"success": True}


# ── PUT /usuarios/{user_id}/reactivar ─────────────────────────────────────────

@router.put("/{user_id}/reactivar")
async def reactivar_usuario(
    user_id: str,
    current_user: Dict = Depends(get_current_user),
):
    _require_cfo(current_user)
    target = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    target_companies = set(
        target.get("empresas_asignadas") or target.get("company_ids") or [target.get("company_id", "")]
    )
    if not target_companies.intersection(_cfo_company_ids(current_user)):
        raise HTTPException(status_code=403, detail="No tienes permisos sobre este usuario")

    await db.users.update_one({"id": user_id}, {"$set": {"activo": True}})
    return {"success": True}
