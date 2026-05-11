"""
TaxnFin — Conekta Subscription & Payments
Planes: Basic $890 MXN/mes | Pro $1,900 MXN/mes
Trial: 14 días gratis
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Optional
from datetime import datetime, timezone, timedelta
import httpx
import os
import logging

from core.database import db
from core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing")

# ── Conekta config ──────────────────────────────────────────────────
CONEKTA_API_KEY     = os.environ.get("CONEKTA_API_KEY", "")
CONEKTA_API_URL     = "https://api.conekta.io"
CONEKTA_API_VERSION = "2.1.0"

# ── Planes ──────────────────────────────────────────────────────────
PLANS = {
    "basic": {
        "name":          "TaxnFin Basic",
        "price_mxn":     890,
        "interval":      "month",
        "trial_days":    14,
        "max_empresas":  1,
        "features": [
            "Dashboard + Cashflow 13 semanas",
            "Cobranza y Pagos",
            "Aging CxC / CxP",
            "SAT y Fiscal (CFDIs)",
            "Importación Contalink / Alegra",
            "Reporte Board PDF",
            "Soporte por email",
        ],
    },
    "pro": {
        "name":          "TaxnFin Pro",
        "price_mxn":     1900,
        "interval":      "month",
        "trial_days":    14,
        "max_empresas":  5,
        "features": [
            "Todo lo de Basic",
            "Hasta 5 empresas (modo despacho)",
            "IA Ejecutiva",
            "Métricas financieras avanzadas (DuPont, ROE, EBITDA)",
            "Decisiones y Alertas automáticas",
            "Escenarios what-if",
            "Estados Financieros completos",
            "TaxnFin Insights newsletter",
            "Soporte prioritario",
        ],
    },
}

# ── Conekta helpers ─────────────────────────────────────────────────
def conekta_headers():
    import base64
    token = base64.b64encode(f"{CONEKTA_API_KEY}:".encode()).decode()
    return {
        "Authorization":      f"Basic {token}",
        "Content-Type":       "application/json",
        "Accept":             "application/vnd.conekta-v2.1.0+json",
        "Accept-Language":    "es",
        "Conekta-Client-User-Agent": "TaxnFin/1.0",
    }

async def conekta_post(path: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{CONEKTA_API_URL}{path}",
            json=body,
            headers=conekta_headers(),
        )
        if r.status_code not in (200, 201):
            logger.error(f"Conekta error {r.status_code}: {r.text}")
            raise HTTPException(
                status_code=400,
                detail=f"Error Conekta: {r.json().get('details', [{}])[0].get('message', r.text)}"
            )
        return r.json()

async def conekta_get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{CONEKTA_API_URL}{path}",
            headers=conekta_headers(),
        )
        if r.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Error Conekta: {r.text}")
        return r.json()

# ── Models ──────────────────────────────────────────────────────────
class StartTrialRequest(BaseModel):
    plan_id: str  # "basic" | "pro"

class CreateSubscriptionRequest(BaseModel):
    plan_id:       str
    token_id:      str           # Token de tarjeta desde Conekta.js
    payment_method: str = "card" # "card" | "spei"

class WebhookEvent(BaseModel):
    type: str
    data: dict

# ── Endpoints ───────────────────────────────────────────────────────

@router.get("/plans")
async def get_plans():
    """Planes disponibles — público, no requiere auth"""
    return {
        "plans": [
            {
                "id":           plan_id,
                "name":         info["name"],
                "price_mxn":    info["price_mxn"],
                "interval":     info["interval"],
                "trial_days":   info["trial_days"],
                "max_empresas": info["max_empresas"],
                "features":     info["features"],
            }
            for plan_id, info in PLANS.items()
        ]
    }


@router.post("/trial/start")
async def start_trial(
    data: StartTrialRequest,
    current_user: Dict = Depends(get_current_user)
):
    """Inicia trial de 14 días para el usuario actual"""
    if data.plan_id not in PLANS:
        raise HTTPException(status_code=400, detail="Plan no válido")

    company_id = current_user["company_id"]
    existing = await db.subscriptions.find_one({"company_id": company_id})

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Esta empresa ya tiene una suscripción o trial activo"
        )

    plan   = PLANS[data.plan_id]
    now    = datetime.now(timezone.utc)
    trial_end = now + timedelta(days=plan["trial_days"])

    sub_doc = {
        "company_id":       company_id,
        "user_id":          current_user["id"],
        "plan_id":          data.plan_id,
        "plan_name":        plan["name"],
        "status":           "trialing",
        "trial_start":      now.isoformat(),
        "trial_end":        trial_end.isoformat(),
        "price_mxn":        plan["price_mxn"],
        "max_empresas":     plan["max_empresas"],
        "conekta_customer_id":     None,
        "conekta_subscription_id": None,
        "current_period_end":      trial_end.isoformat(),
        "created_at":       now.isoformat(),
    }
    await db.subscriptions.insert_one(sub_doc)

    # Actualizar empresa con plan
    await db.companies.update_one(
        {"id": company_id},
        {"$set": {
            "plan_id":    data.plan_id,
            "plan_status": "trialing",
            "trial_end":  trial_end.isoformat(),
        }}
    )

    return {
        "success":    True,
        "status":     "trialing",
        "plan_id":    data.plan_id,
        "trial_end":  trial_end.isoformat(),
        "message":    f"Trial de {plan['trial_days']} días iniciado. Vence el {trial_end.strftime('%d/%m/%Y')}.",
    }


@router.post("/subscribe")
async def create_subscription(
    data: CreateSubscriptionRequest,
    current_user: Dict = Depends(get_current_user)
):
    """Crea suscripción en Conekta con tarjeta o genera orden SPEI"""
    if data.plan_id not in PLANS:
        raise HTTPException(status_code=400, detail="Plan no válido")

    plan       = PLANS[data.plan_id]
    company_id = current_user["company_id"]
    email      = current_user.get("email", "")
    nombre     = current_user.get("nombre", "Cliente TaxnFin")

    # 1. Crear o recuperar customer en Conekta
    sub_doc = await db.subscriptions.find_one({"company_id": company_id})
    conekta_customer_id = sub_doc.get("conekta_customer_id") if sub_doc else None

    if not conekta_customer_id:
        customer = await conekta_post("/customers", {
            "name":  nombre,
            "email": email,
            "phone": "+5200000000",
        })
        conekta_customer_id = customer["id"]

    # 2. Agregar método de pago
    if data.payment_method == "card":
        await conekta_post(
            f"/customers/{conekta_customer_id}/payment_sources",
            {"type": "card", "token_id": data.token_id}
        )
        payment_method_type = "card"

    elif data.payment_method == "spei":
        # SPEI — generar orden de pago
        order = await conekta_post("/orders", {
            "currency": "MXN",
            "customer_info": {
                "customer_id": conekta_customer_id
            },
            "line_items": [{
                "name":       plan["name"],
                "unit_price": plan["price_mxn"] * 100,  # centavos
                "quantity":   1,
            }],
            "charges": [{
                "payment_method": {
                    "type":       "spei",
                    "expires_at": int((datetime.now(timezone.utc) + timedelta(days=3)).timestamp()),
                }
            }],
            "metadata": {
                "company_id": company_id,
                "plan_id":    data.plan_id,
            }
        })
        # Retornar datos SPEI para que el cliente transfiera
        charge = order.get("charges", {}).get("data", [{}])[0]
        spei   = charge.get("payment_method", {})
        return {
            "success":        True,
            "payment_method": "spei",
            "spei": {
                "clabe":      spei.get("clabe"),
                "bank":       spei.get("bank"),
                "amount":     plan["price_mxn"],
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
                "reference":  order.get("id"),
            },
            "message": "Realiza la transferencia SPEI con los datos indicados. Tu cuenta se activará automáticamente al confirmar el pago.",
        }

    # 3. Crear plan en Conekta si no existe
    conekta_plan_id = f"taxnfin_{data.plan_id}_monthly"
    try:
        await conekta_get(f"/plans/{conekta_plan_id}")
    except HTTPException:
        await conekta_post("/plans", {
            "id":            conekta_plan_id,
            "name":          plan["name"],
            "amount":        plan["price_mxn"] * 100,
            "currency":      "MXN",
            "interval":      "month",
            "frequency":     1,
            "trial_period_days": 0,
        })

    # 4. Crear suscripción recurrente
    conekta_sub = await conekta_post(
        f"/customers/{conekta_customer_id}/subscription",
        {"plan_id": conekta_plan_id}
    )

    # 5. Guardar en MongoDB
    now = datetime.now(timezone.utc)
    period_end = now + timedelta(days=30)

    update = {
        "status":                    "active",
        "plan_id":                   data.plan_id,
        "plan_name":                 plan["name"],
        "price_mxn":                 plan["price_mxn"],
        "max_empresas":              plan["max_empresas"],
        "conekta_customer_id":       conekta_customer_id,
        "conekta_subscription_id":   conekta_sub.get("id"),
        "payment_method_type":       payment_method_type,
        "current_period_end":        period_end.isoformat(),
        "activated_at":              now.isoformat(),
    }

    if sub_doc:
        await db.subscriptions.update_one(
            {"company_id": company_id},
            {"$set": update}
        )
    else:
        update["company_id"]  = company_id
        update["user_id"]     = current_user["id"]
        update["created_at"]  = now.isoformat()
        await db.subscriptions.insert_one(update)

    await db.companies.update_one(
        {"id": company_id},
        {"$set": {
            "plan_id":    data.plan_id,
            "plan_status": "active",
        }}
    )

    return {
        "success": True,
        "status":  "active",
        "plan_id": data.plan_id,
        "message": f"Suscripción {plan['name']} activada exitosamente.",
    }


@router.get("/subscription/status")
async def get_subscription_status(current_user: Dict = Depends(get_current_user)):
    """Estado actual de la suscripción de la empresa"""
    company_id = current_user["company_id"]
    sub = await db.subscriptions.find_one(
        {"company_id": company_id},
        {"_id": 0, "conekta_customer_id": 0}
    )

    if not sub:
        return {
            "status":      "none",
            "plan_id":     None,
            "trial_end":   None,
            "message":     "Sin suscripción activa. Inicia tu trial gratuito.",
        }

    # Verificar si el trial venció
    if sub["status"] == "trialing":
        trial_end = datetime.fromisoformat(sub["trial_end"])
        if datetime.now(timezone.utc) > trial_end:
            await db.subscriptions.update_one(
                {"company_id": company_id},
                {"$set": {"status": "trial_expired"}}
            )
            sub["status"] = "trial_expired"

    days_left = None
    if sub.get("current_period_end"):
        end = datetime.fromisoformat(sub["current_period_end"])
        days_left = max(0, (end - datetime.now(timezone.utc)).days)

    return {
        "status":          sub["status"],
        "plan_id":         sub.get("plan_id"),
        "plan_name":       sub.get("plan_name"),
        "price_mxn":       sub.get("price_mxn"),
        "max_empresas":    sub.get("max_empresas", 1),
        "trial_end":       sub.get("trial_end"),
        "period_end":      sub.get("current_period_end"),
        "days_left":       days_left,
        "payment_method":  sub.get("payment_method_type"),
    }


@router.post("/webhook/conekta")
async def conekta_webhook(request: Request):
    """Webhook de Conekta — actualiza estado de suscripciones automáticamente"""
    try:
        payload = await request.json()
        event_type = payload.get("type", "")
        data       = payload.get("data", {}).get("object", {})

        logger.info(f"Conekta webhook: {event_type}")

        if event_type == "subscription.paid":
            # Pago exitoso — renovar período
            conekta_sub_id = data.get("id")
            period_end = datetime.now(timezone.utc) + timedelta(days=30)
            await db.subscriptions.update_one(
                {"conekta_subscription_id": conekta_sub_id},
                {"$set": {
                    "status":             "active",
                    "current_period_end": period_end.isoformat(),
                    "last_payment_at":    datetime.now(timezone.utc).isoformat(),
                }}
            )

        elif event_type == "subscription.payment_failed":
            conekta_sub_id = data.get("id")
            await db.subscriptions.update_one(
                {"conekta_subscription_id": conekta_sub_id},
                {"$set": {"status": "past_due"}}
            )

        elif event_type == "subscription.canceled":
            conekta_sub_id = data.get("id")
            await db.subscriptions.update_one(
                {"conekta_subscription_id": conekta_sub_id},
                {"$set": {"status": "canceled"}}
            )

        elif event_type == "order.paid":
            # SPEI pagado — activar suscripción
            metadata   = data.get("metadata", {})
            company_id = metadata.get("company_id")
            plan_id    = metadata.get("plan_id")
            if company_id and plan_id:
                period_end = datetime.now(timezone.utc) + timedelta(days=30)
                plan = PLANS.get(plan_id, {})
                await db.subscriptions.update_one(
                    {"company_id": company_id},
                    {"$set": {
                        "status":             "active",
                        "payment_method_type": "spei",
                        "current_period_end": period_end.isoformat(),
                        "activated_at":       datetime.now(timezone.utc).isoformat(),
                    }},
                    upsert=True,
                )
                await db.companies.update_one(
                    {"id": company_id},
                    {"$set": {"plan_id": plan_id, "plan_status": "active"}}
                )

        return {"received": True}

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse(status_code=200, content={"received": True})


@router.post("/cancel")
async def cancel_subscription(current_user: Dict = Depends(get_current_user)):
    """Cancelar suscripción al final del período actual"""
    company_id = current_user["company_id"]
    sub = await db.subscriptions.find_one({"company_id": company_id})

    if not sub or sub["status"] not in ("active", "trialing"):
        raise HTTPException(status_code=400, detail="No hay suscripción activa para cancelar")

    conekta_sub_id = sub.get("conekta_subscription_id")
    if conekta_sub_id:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                await client.delete(
                    f"{CONEKTA_API_URL}/customers/{sub['conekta_customer_id']}/subscription",
                    headers=conekta_headers(),
                )
        except Exception as e:
            logger.warning(f"Error cancelando en Conekta: {e}")

    await db.subscriptions.update_one(
        {"company_id": company_id},
        {"$set": {"status": "canceled", "canceled_at": datetime.now(timezone.utc).isoformat()}}
    )

    return {
        "success": True,
        "message": "Suscripción cancelada. Tendrás acceso hasta el fin del período actual.",
    }
