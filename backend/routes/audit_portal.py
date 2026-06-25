"""Portal de Auditoría y Fiscal — expedientes, solicitudes, archivos R2."""
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Query
from fastapi.responses import RedirectResponse

from core.auth import get_current_user, get_active_company_id
from core.database import db
from modules.r2_storage import upload_file, delete_file, generate_presigned_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["Auditoría y Fiscal"])

VALID_CATEGORIAS = [
    "General", "Fiscal/SAT", "Bancos", "Nómina",
    "CxC", "CxP", "Inventario", "Contratos", "PP&E", "Otro",
]

# ─── helpers ──────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_company(cid: str) -> str:
    return cid  # full UUID already; prefix resolution done at query time


def _r2_key(company_id: str, engagement_id: str, request_id: str, filename: str) -> str:
    return f"audit/{company_id[:8]}/{engagement_id[:8]}/{request_id[:8]}/{filename}"


# ─── EXPEDIENTES ──────────────────────────────────────────────────────────────

@router.get("/engagements")
async def list_engagements(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    docs = await db.audit_engagements.find(
        {"company_id": {"$regex": f"^{company_id[:8]}"},
         "status": {"$ne": "archivado"}},
        {"_id": 0}
    ).sort("creado_at", -1).to_list(200)
    # Enrich with request counts
    for doc in docs:
        counts = await db.audit_requests.aggregate([
            {"$match": {"engagement_id": doc["id"]}},
            {"$group": {"_id": "$status", "n": {"$sum": 1}}},
        ]).to_list(20)
        doc["request_counts"] = {r["_id"]: r["n"] for r in counts}
        total = sum(r["n"] for r in counts)
        accepted = sum(r["n"] for r in counts if r["_id"] == "aceptada")
        doc["progreso_pct"] = round(accepted / total * 100) if total else 0
    return docs


@router.post("/engagements")
async def create_engagement(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    body = await request.json()
    doc = {
        "id": str(uuid.uuid4()),
        "company_id": company_id,
        "nombre": body.get("nombre", "Expediente sin nombre"),
        "descripcion": body.get("descripcion", ""),
        "año": body.get("año", datetime.now().year),
        "tipo": body.get("tipo", "Auditoría externa"),
        "status": "activo",
        "creado_por": current_user["id"],
        "creado_at": _now(),
        "actualizado_at": _now(),
        "invitados": [],
        "link_publico": str(uuid.uuid4()),
        "categorias": body.get("categorias", VALID_CATEGORIAS),
    }
    await db.audit_engagements.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/engagements/{engagement_id}")
async def get_engagement(
    engagement_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    eng = await db.audit_engagements.find_one(
        {"id": engagement_id, "company_id": {"$regex": f"^{company_id[:8]}"}},
        {"_id": 0}
    )
    if not eng:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")

    requests_raw = await db.audit_requests.find(
        {"engagement_id": engagement_id}, {"_id": 0}
    ).sort("creado_at", 1).to_list(1000)

    by_category = {}
    for cat in eng.get("categorias", VALID_CATEGORIAS):
        by_category[cat] = [r for r in requests_raw if r.get("categoria") == cat]

    return {**eng, "solicitudes_por_categoria": by_category, "total_solicitudes": len(requests_raw)}


@router.put("/engagements/{engagement_id}")
async def update_engagement(
    engagement_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    body = await request.json()
    allowed = {"nombre", "descripcion", "año", "tipo", "status", "categorias"}
    update = {k: v for k, v in body.items() if k in allowed}
    update["actualizado_at"] = _now()
    res = await db.audit_engagements.update_one(
        {"id": engagement_id, "company_id": {"$regex": f"^{company_id[:8]}"}},
        {"$set": update}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return {"success": True}


@router.delete("/engagements/{engagement_id}")
async def archive_engagement(
    engagement_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    res = await db.audit_engagements.update_one(
        {"id": engagement_id, "company_id": {"$regex": f"^{company_id[:8]}"}},
        {"$set": {"status": "archivado", "actualizado_at": _now()}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return {"success": True}


@router.post("/engagements/{engagement_id}/invite")
async def invite_to_engagement(
    engagement_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    body = await request.json()
    email = body.get("email", "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email requerido")
    invitado = {
        "email": email,
        "nombre": body.get("nombre", email),
        "rol": body.get("rol", "solicitante"),
        "token_acceso": str(uuid.uuid4()),
        "invitado_at": _now(),
    }
    res = await db.audit_engagements.update_one(
        {"id": engagement_id, "company_id": {"$regex": f"^{company_id[:8]}"}},
        {"$push": {"invitados": invitado}, "$set": {"actualizado_at": _now()}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return {"success": True, "token_acceso": invitado["token_acceso"]}


@router.get("/engagements/{engagement_id}/link")
async def get_public_link(
    engagement_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    eng = await db.audit_engagements.find_one(
        {"id": engagement_id, "company_id": {"$regex": f"^{company_id[:8]}"}},
        {"_id": 0, "link_publico": 1}
    )
    if not eng:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return {"link_publico": eng["link_publico"]}


# ─── SOLICITUDES ──────────────────────────────────────────────────────────────

@router.get("/engagements/{engagement_id}/requests")
async def list_requests(
    engagement_id: str,
    request: Request,
    status: Optional[str] = Query(None),
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    q: dict = {"engagement_id": engagement_id, "company_id": {"$regex": f"^{company_id[:8]}"}}
    if status:
        q["status"] = status
    docs = await db.audit_requests.find(q, {"_id": 0}).sort("creado_at", 1).to_list(1000)
    return docs


@router.post("/engagements/{engagement_id}/requests")
async def create_request(
    engagement_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    eng = await db.audit_engagements.find_one(
        {"id": engagement_id, "company_id": {"$regex": f"^{company_id[:8]}"}},
        {"_id": 0, "id": 1}
    )
    if not eng:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    body = await request.json()
    doc = {
        "id": str(uuid.uuid4()),
        "engagement_id": engagement_id,
        "company_id": company_id,
        "categoria": body.get("categoria", "General"),
        "nombre": body.get("nombre", ""),
        "descripcion": body.get("descripcion", ""),
        "prioridad": body.get("prioridad", "media"),
        "status": "pendiente",
        "asignado_a": body.get("asignado_a", ""),
        "fecha_limite": body.get("fecha_limite", ""),
        "creado_at": _now(),
        "actualizado_at": _now(),
        "archivos": [],
        "comentarios": [],
        "motivo_rechazo": "",
    }
    await db.audit_requests.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/requests/{request_id}")
async def update_request(
    request_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    body = await request.json()
    allowed = {"status", "asignado_a", "fecha_limite", "prioridad", "nombre",
               "descripcion", "categoria", "motivo_rechazo"}
    update = {k: v for k, v in body.items() if k in allowed}
    update["actualizado_at"] = _now()
    res = await db.audit_requests.update_one(
        {"id": request_id, "company_id": {"$regex": f"^{company_id[:8]}"}},
        {"$set": update}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return {"success": True}


@router.put("/requests/{request_id}/status")
async def change_request_status(
    request_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    body = await request.json()
    new_status = body.get("status")
    valid = {"pendiente", "enviada", "en_revision", "aceptada", "rechazada"}
    if new_status not in valid:
        raise HTTPException(status_code=400, detail=f"Status inválido. Use: {valid}")
    update: dict = {"status": new_status, "actualizado_at": _now()}
    if new_status == "rechazada":
        update["motivo_rechazo"] = body.get("motivo_rechazo", "")
    res = await db.audit_requests.update_one(
        {"id": request_id, "company_id": {"$regex": f"^{company_id[:8]}"}},
        {"$set": update}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return {"success": True}


@router.post("/requests/{request_id}/upload")
async def upload_file_to_request(
    request_id: str,
    request: Request,
    file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    req_doc = await db.audit_requests.find_one(
        {"id": request_id, "company_id": {"$regex": f"^{company_id[:8]}"}},
        {"_id": 0, "engagement_id": 1}
    )
    if not req_doc:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    file_bytes = await file.read()
    key = _r2_key(company_id, req_doc["engagement_id"], request_id, file.filename)
    upload_file(file_bytes, key, file.content_type or "application/octet-stream")

    archivo = {
        "nombre": file.filename,
        "key_r2": key,
        "tamaño": len(file_bytes),
        "tipo": file.content_type or "application/octet-stream",
        "subido_por": current_user["id"],
        "subido_at": _now(),
    }
    await db.audit_requests.update_one(
        {"id": request_id},
        {"$push": {"archivos": archivo}, "$set": {"actualizado_at": _now()}}
    )
    return {"success": True, "archivo": archivo}


@router.delete("/requests/{request_id}/files/{key:path}")
async def delete_file_from_request(
    request_id: str,
    key: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    delete_file(key)
    await db.audit_requests.update_one(
        {"id": request_id, "company_id": {"$regex": f"^{company_id[:8]}"}},
        {"$pull": {"archivos": {"key_r2": key}}, "$set": {"actualizado_at": _now()}}
    )
    return {"success": True}


@router.get("/requests/{request_id}/files/{key:path}/download")
async def download_file_url(
    request_id: str,
    key: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    url = generate_presigned_url(key, expires=3600)
    return {"url": url}


@router.post("/requests/{request_id}/comments")
async def add_comment(
    request_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    body = await request.json()
    comment = {
        "id": str(uuid.uuid4()),
        "texto": body.get("texto", ""),
        "autor": current_user["id"],
        "autor_nombre": current_user.get("email", ""),
        "fecha": _now(),
        "tipo": body.get("tipo", "interno"),
    }
    res = await db.audit_requests.update_one(
        {"id": request_id, "company_id": {"$regex": f"^{company_id[:8]}"}},
        {"$push": {"comentarios": comment}, "$set": {"actualizado_at": _now()}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return {"success": True, "comment": comment}


# ─── ACCESO PÚBLICO (sin JWT) ─────────────────────────────────────────────────

@router.get("/public/{link_publico}")
async def public_get_engagement(link_publico: str):
    eng = await db.audit_engagements.find_one(
        {"link_publico": link_publico, "status": {"$ne": "archivado"}},
        {"_id": 0}
    )
    if not eng:
        raise HTTPException(status_code=404, detail="Expediente no encontrado o inactivo")

    requests_raw = await db.audit_requests.find(
        {"engagement_id": eng["id"]}, {"_id": 0, "comentarios": 0}
    ).sort("creado_at", 1).to_list(1000)

    return {
        "engagement": {k: v for k, v in eng.items() if k != "invitados"},
        "solicitudes": requests_raw,
    }


@router.post("/public/{link_publico}/requests/{request_id}/upload")
async def public_upload_file(
    link_publico: str,
    request_id: str,
    request: Request,
    file: UploadFile = File(...),
    nombre_externo: str = Query("Externo"),
):
    eng = await db.audit_engagements.find_one(
        {"link_publico": link_publico, "status": {"$ne": "archivado"}},
        {"_id": 0, "id": 1, "company_id": 1}
    )
    if not eng:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")

    req_doc = await db.audit_requests.find_one(
        {"id": request_id, "engagement_id": eng["id"]}, {"_id": 0}
    )
    if not req_doc:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    file_bytes = await file.read()
    key = _r2_key(eng["company_id"], eng["id"], request_id, file.filename)
    upload_file(file_bytes, key, file.content_type or "application/octet-stream")

    archivo = {
        "nombre": file.filename,
        "key_r2": key,
        "tamaño": len(file_bytes),
        "tipo": file.content_type or "application/octet-stream",
        "subido_por": f"externo:{nombre_externo}",
        "subido_at": _now(),
    }
    await db.audit_requests.update_one(
        {"id": request_id},
        {"$push": {"archivos": archivo},
         "$set": {"status": "enviada", "actualizado_at": _now()}}
    )
    return {"success": True, "archivo": archivo}


@router.post("/public/{link_publico}/requests/{request_id}/comments")
async def public_add_comment(
    link_publico: str,
    request_id: str,
    request: Request,
):
    eng = await db.audit_engagements.find_one(
        {"link_publico": link_publico, "status": {"$ne": "archivado"}},
        {"_id": 0, "id": 1}
    )
    if not eng:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")

    body = await request.json()
    comment = {
        "id": str(uuid.uuid4()),
        "texto": body.get("texto", ""),
        "autor": "externo",
        "autor_nombre": body.get("autor_nombre", "Externo"),
        "fecha": _now(),
        "tipo": "externo",
    }
    res = await db.audit_requests.update_one(
        {"id": request_id, "engagement_id": eng["id"]},
        {"$push": {"comentarios": comment}, "$set": {"actualizado_at": _now()}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return {"success": True}
