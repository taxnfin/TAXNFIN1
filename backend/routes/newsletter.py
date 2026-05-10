from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import re

router = APIRouter()

def is_valid_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

@router.post("/newsletter/subscribe")
async def subscribe(request: Request):
    try:
        body = await request.json()
        email = body.get("email", "").strip().lower()

        if not email or not is_valid_email(email):
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Email invalido"}
            )

        db = request.app.state.db

        # Verificar si ya existe
        existing = await db.newsletter_subscribers.find_one({"email": email})
        if existing:
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": "Ya estas suscrito", "already": True}
            )

        # Guardar nuevo suscriptor
        await db.newsletter_subscribers.insert_one({
            "email": email,
            "subscribed_at": datetime.now(timezone.utc),
            "source": "taxnfin.com",
            "active": True,
            "tags": ["insights", "newsletter"]
        })

        return JSONResponse(
            status_code=201,
            content={"success": True, "message": "Suscrito exitosamente"}
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error: {str(e)}"}
        )


@router.get("/newsletter/subscribers")
async def list_subscribers(request: Request):
    """Admin endpoint — lista todos los suscriptores"""
    try:
        db = request.app.state.db
        subs = await db.newsletter_subscribers.find(
            {"active": True},
            {"_id": 0, "email": 1, "subscribed_at": 1, "source": 1}
        ).sort("subscribed_at", -1).to_list(length=1000)

        return {
            "total": len(subs),
            "subscribers": subs
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.delete("/newsletter/unsubscribe")
async def unsubscribe(request: Request):
    """Marcar como inactivo (no borrar)"""
    try:
        body = await request.json()
        email = body.get("email", "").strip().lower()

        db = request.app.state.db
        result = await db.newsletter_subscribers.update_one(
            {"email": email},
            {"$set": {"active": False, "unsubscribed_at": datetime.now(timezone.utc)}}
        )

        if result.modified_count == 0:
            return JSONResponse(status_code=404, content={"success": False, "message": "Email no encontrado"})

        return {"success": True, "message": "Desuscrito correctamente"}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
