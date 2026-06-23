"""
TaxnFin — Consejo Estratégico IA
Analiza decisiones empresariales desde 5 perspectivas independientes usando Claude.
"""
import os
import anthropic
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from typing import Dict
from core.auth import get_current_user, get_active_company_id
from core.database import db

router = APIRouter(prefix="/ia", tags=["Consejo Estratégico IA"])


@router.post("/consejo-estrategico")
async def consejo_estrategico(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    body = await request.json()
    pregunta = body.get("pregunta", "").strip()
    if not pregunta:
        return {"error": "La pregunta no puede estar vacía"}

    company_id = await get_active_company_id(request, current_user)

    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    company_name = company.get("name", "la empresa") if company else "la empresa"

    prompt = f"""Eres el coordinador de un consejo de cinco asesores estratégicos analizando decisiones para {company_name}.

Analiza esta pregunta/decisión desde cinco perspectivas distintas e independientes:

PREGUNTA: {pregunta}

1. 🔴 EL CONTRARIAN — Busca activamente lo que puede fallar. Asume que hay un error fatal y trata de encontrarlo. No busca equilibrio, busca el punto de quiebre.

2. 🔵 EL PENSADOR DE PRIMEROS PRINCIPIOS — Ignora la pregunta superficial y pregunta qué es lo que realmente se está intentando resolver. Desmonta todos los supuestos. Regresa a la causa raíz.

3. 🟢 EL EXPANSIONISTA — Busca el upside que todos los demás están ignorando. ¿Qué oportunidad se está subestimando? ¿Qué pasa si esto funciona mejor de lo esperado?

4. 🟡 EL OUTSIDER — No tiene contexto previo. Responde únicamente a lo que tiene delante. Detecta lo que es obvio para un extraño pero invisible para quien está demasiado dentro.

5. 🟠 EL EJECUTOR — Solo le importa una cosa: ¿Se puede hacer, y cuál es el camino más rápido? Ignora la teoría. ¿Qué hago el lunes por la mañana?

INSTRUCCIONES:
- Cada asesor responde de forma independiente y defiende su ángulo con fuerza. Mínimo 3 párrafos cada uno.
- Después, cada asesor revisa las respuestas de los otros e identifica: cuál es la más sólida, cuál tiene el mayor punto ciego, y qué no ha visto nadie.
- Al final, el PRESIDENTE DEL CONSEJO sintetiza: dónde coinciden, dónde chocan, qué se detectó en la revisión, y UNA recomendación concreta con un único primer paso.

Responde en español. Sé directo, sin suavizar. Cada perspectiva debe defender su ángulo con convicción."""

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=6000,
            messages=[{"role": "user", "content": prompt}],
        )
        respuesta = message.content[0].text

        await db.consejo_estrategico_historial.insert_one({
            "company_id": company_id,
            "pregunta": pregunta,
            "respuesta": respuesta,
            "created_at": datetime.now(timezone.utc),
        })

        return {"success": True, "respuesta": respuesta}

    except Exception as e:
        print(f"[CONSEJO] ERROR: {e}", flush=True)
        return {"success": False, "error": str(e)}


@router.get("/consejo-estrategico/historial")
async def consejo_historial(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    historial = await db.consejo_estrategico_historial.find(
        {"company_id": company_id},
        {"_id": 0},
    ).sort("created_at", -1).limit(10).to_list(10)
    return {"historial": historial}
