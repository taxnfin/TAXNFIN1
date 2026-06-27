"""
TaxnFin — Gestión de Usuarios
Invitar, rolar, asignar empresas y desactivar usuarios dentro del scope del CFO.
Regla de oro: ningún usuario puede ver ni tocar datos de empresas que no le pertenecen.
"""
import uuid
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, Request

from core.auth import get_current_user, hash_password
from core.database import db

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])
logger = logging.getLogger(__name__)


async def _send_welcome_email(
    email: str,
    nombre: str,
    temp_password: str,
    empresas: List[str],
    invited_by_nombre: str,
) -> None:
    """Envía email de bienvenida al usuario invitado con sus credenciales de acceso."""
    try:
        import resend
        api_key = os.environ.get('RESEND_API_KEY', '')
        if not api_key:
            logger.warning(
                "[RESEND] Sin API key — credenciales para %s: pass=%s",
                email, temp_password
            )
            return

        resend.api_key = api_key
        from_address = os.environ.get('RESEND_FROM', 'TaxnFin <noreply@taxnfin.com>')
        frontend_url = os.environ.get('FRONTEND_URL', 'https://cashflow.taxnfin.com')
        empresas_html = ''.join(f'<li style="margin:4px 0">{e}</li>' for e in empresas)

        html_body = f"""
<!DOCTYPE html>
<html lang="es">
<body style="font-family:Arial,sans-serif;background:#F8F9FA;margin:0;padding:24px">
  <div style="max-width:560px;margin:0 auto;background:#FFF;border-radius:8px;padding:32px;border:1px solid #E2E8F0">
    <div style="text-align:center;margin-bottom:24px">
      <span style="font-size:28px;font-weight:800;color:#1B3A6B">T$</span>
      <span style="font-size:18px;font-weight:700;color:#1B3A6B;margin-left:8px">TaxnFin Cashflow</span>
    </div>
    <h2 style="color:#1B3A6B;font-size:20px;margin:0 0 16px">¡Hola {nombre}! 👋</h2>
    <p style="color:#374151;font-size:14px;line-height:1.6;margin:0 0 16px">
      <strong>{invited_by_nombre}</strong> te ha dado acceso a <strong>TaxnFin CFO Intelligence</strong>.
      Ya puedes ver el flujo de caja e información financiera de:
    </p>
    <ul style="color:#374151;font-size:14px;margin:0 0 24px;padding-left:20px">
      {empresas_html}
    </ul>
    <div style="background:#F1F5F9;border-radius:6px;padding:16px;margin:0 0 24px">
      <p style="color:#64748B;font-size:12px;margin:0 0 8px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em">Tus credenciales de acceso</p>
      <p style="margin:4px 0;font-size:13px;color:#374151">📧 <strong>Email:</strong> {email}</p>
      <p style="margin:4px 0;font-size:13px;color:#374151">🔑 <strong>Contraseña temporal:</strong>
        <span style="font-family:monospace;font-size:16px;font-weight:700;color:#1B3A6B;letter-spacing:0.1em">{temp_password}</span>
      </p>
      <p style="color:#EF4444;font-size:12px;margin:8px 0 0">⚠️ Deberás cambiar tu contraseña en el primer inicio de sesión.</p>
    </div>
    <p style="text-align:center;margin:0 0 24px">
      <a href="{frontend_url}/login"
         style="background:#1B3A6B;color:#FFF;text-decoration:none;padding:12px 32px;
                border-radius:6px;display:inline-block;font-weight:600;font-size:14px">
        Acceder a TaxnFin →
      </a>
    </p>
    <p style="color:#94A3B8;font-size:11px;text-align:center;margin:0">
      TaxnFin CFO Intelligence · Si tienes problemas para acceder escríbenos a hola@taxnfin.com
    </p>
  </div>
</body>
</html>"""

        text_body = (
            f"¡Hola {nombre}!\n\n"
            f"{invited_by_nombre} te ha dado acceso a TaxnFin CFO Intelligence.\n\n"
            f"Empresas con acceso:\n" + "\n".join(f"- {e}" for e in empresas) + "\n\n"
            f"Credenciales:\n"
            f"Email: {email}\n"
            f"Contraseña temporal: {temp_password}\n\n"
            f"Deberás cambiar tu contraseña al iniciar sesión.\n\n"
            f"Accede en: {frontend_url}/login"
        )

        params = {
            "from": from_address,
            "to": [email],
            "subject": f"Tu acceso a TaxnFin CFO Intelligence — {', '.join(empresas[:2])}",
            "html": html_body,
            "text": text_body,
        }

        result = await asyncio.wait_for(
            asyncio.to_thread(resend.Emails.send, params),
            timeout=30.0,
        )
        logger.info("[RESEND] Welcome email enviado a %s — %s", email, result)

    except Exception as e:
        logger.error("[RESEND] Error enviando welcome email a %s: %s", email, e)
        # No re-raise — el usuario ya fue creado, el email es best-effort


async def _send_access_update_email(
    email: str,
    nombre: str,
    empresas_nuevas: List[str],
    empresas_todas: List[str],
) -> None:
    """Envía email notificando que se agregaron nuevas empresas al acceso del usuario."""
    try:
        import resend
        api_key = os.environ.get('RESEND_API_KEY', '')
        if not api_key:
            return

        resend.api_key = api_key
        from_address = os.environ.get('RESEND_FROM', 'TaxnFin <noreply@taxnfin.com>')
        frontend_url = os.environ.get('FRONTEND_URL', 'https://cashflow.taxnfin.com')
        nuevas_html = ''.join(f'<li style="margin:4px 0;color:#1E7145"><strong>{e}</strong></li>' for e in empresas_nuevas)

        html_body = f"""
<!DOCTYPE html>
<html lang="es">
<body style="font-family:Arial,sans-serif;background:#F8F9FA;margin:0;padding:24px">
  <div style="max-width:560px;margin:0 auto;background:#FFF;border-radius:8px;padding:32px;border:1px solid #E2E8F0">
    <div style="text-align:center;margin-bottom:24px">
      <span style="font-size:28px;font-weight:800;color:#1B3A6B">T$</span>
      <span style="font-size:18px;font-weight:700;color:#1B3A6B;margin-left:8px">TaxnFin Cashflow</span>
    </div>
    <h2 style="color:#1B3A6B;font-size:20px;margin:0 0 16px">Nuevo acceso disponible</h2>
    <p style="color:#374151;font-size:14px;line-height:1.6;margin:0 0 16px">
      Hola <strong>{nombre}</strong>, se ha actualizado tu acceso en TaxnFin.
      Ahora también puedes ver información financiera de:
    </p>
    <ul style="margin:0 0 24px;padding-left:20px">
      {nuevas_html}
    </ul>
    <p style="text-align:center;margin:0 0 24px">
      <a href="{frontend_url}"
         style="background:#1B3A6B;color:#FFF;text-decoration:none;padding:12px 32px;
                border-radius:6px;display:inline-block;font-weight:600;font-size:14px">
        Ir a TaxnFin →
      </a>
    </p>
    <p style="color:#94A3B8;font-size:11px;text-align:center;margin:0">
      TaxnFin CFO Intelligence · hola@taxnfin.com
    </p>
  </div>
</body>
</html>"""

        params = {
            "from": from_address,
            "to": [email],
            "subject": f"Nuevo acceso en TaxnFin — {', '.join(empresas_nuevas[:2])}",
            "html": html_body,
            "text": f"Hola {nombre}, se agregaron nuevas empresas a tu acceso: {', '.join(empresas_nuevas)}. Accede en {frontend_url}",
        }

        await asyncio.wait_for(
            asyncio.to_thread(resend.Emails.send, params),
            timeout=30.0,
        )
        logger.info("[RESEND] Access update email enviado a %s", email)

    except Exception as e:
        logger.error("[RESEND] Error enviando access update email a %s: %s", email, e)


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

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        # Usuario ya registrado — agregar las empresas nuevas a las que ya tiene
        existing_company_ids = set(existing.get("company_ids") or existing.get("empresas_asignadas") or [existing.get("company_id", "")])
        nuevas = [cid for cid in company_ids if cid not in existing_company_ids]
        if not nuevas:
            raise HTTPException(
                status_code=400,
                detail=f"El usuario ya tiene acceso a todas las empresas seleccionadas"
            )
        merged = list(existing_company_ids) + nuevas
        await db.users.update_one(
            {"email": email},
            {"$set": {
                "company_ids":        merged,
                "empresas_asignadas": merged,
                "updated_at":         datetime.now(timezone.utc).isoformat(),
            }}
        )
        # Obtener nombres de empresas nuevas para el email
        nuevas_docs = await db.companies.find(
            {"id": {"$in": nuevas}}, {"_id": 0, "nombre": 1}
        ).to_list(10)
        nuevas_nombres = [d["nombre"] for d in nuevas_docs]
        asyncio.create_task(_send_access_update_email(
            email=email,
            nombre=existing["nombre"],
            empresas_nuevas=nuevas_nombres,
            empresas_todas=[],
        ))
        return {
            "success":        True,
            "user_id":        existing["id"],
            "nombre":         existing["nombre"],
            "email":          email,
            "empresas_nuevas": nuevas,
            "message":        f"Se agregaron {len(nuevas)} empresa(s) al acceso de {existing['nombre']}",
            "ya_registrado":  True,
        }

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

    # Enviar email de bienvenida con credenciales (best-effort, no bloquea)
    empresa_docs = await db.companies.find(
        {"id": {"$in": company_ids}}, {"_id": 0, "nombre": 1}
    ).to_list(10)
    empresa_nombres = [d["nombre"] for d in empresa_docs]
    asyncio.create_task(_send_welcome_email(
        email=email,
        nombre=nombre,
        temp_password=temp_password,
        empresas=empresa_nombres,
        invited_by_nombre=current_user.get("nombre", "Tu administrador"),
    ))

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


# ── POST /usuarios/{user_id}/reset-password ───────────────────────────────────

@router.post("/{user_id}/reset-password")
async def reset_password_usuario(
    user_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """CFO puede resetear la contraseña de un usuario de su empresa."""
    _require_cfo(current_user)
    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    target_companies = set(
        target.get("empresas_asignadas") or target.get("company_ids") or [target.get("company_id", "")]
    )
    if not target_companies.intersection(_cfo_company_ids(current_user)):
        raise HTTPException(status_code=403, detail="No tienes permisos sobre este usuario")

    # Generar nueva contraseña temporal
    temp_password = str(uuid.uuid4()).replace("-", "")[:8].upper()
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "password_hash":        hash_password(temp_password),
            "must_change_password": True,
            "updated_at":           datetime.now(timezone.utc).isoformat(),
        }}
    )

    # Notificar por email (best-effort)
    empresa_docs = await db.companies.find(
        {"id": {"$in": list(target_companies)}}, {"_id": 0, "nombre": 1}
    ).to_list(10)
    empresa_nombres = [d["nombre"] for d in empresa_docs]
    asyncio.create_task(_send_welcome_email(
        email=target["email"],
        nombre=target["nombre"],
        temp_password=temp_password,
        empresas=empresa_nombres,
        invited_by_nombre=current_user.get("nombre", "Tu administrador"),
    ))

    return {
        "success":       True,
        "user_id":       user_id,
        "nombre":        target["nombre"],
        "email":         target["email"],
        "temp_password": temp_password,
        "message":       f"Contraseña reseteada para {target['nombre']}",
    }
