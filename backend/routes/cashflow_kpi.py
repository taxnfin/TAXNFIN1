"""
TaxnFin — KPI Insight endpoint
Llama a la API de Anthropic para interpretar un KPI de Cash Flow en contexto de negocio.
"""
import os
import httpx
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any
from core.auth import get_current_user

router = APIRouter(prefix="/cashflow-kpi", tags=["Cashflow KPI"])


class KpiInsightRequest(BaseModel):
    kpi_name: str
    formula: str
    description: str
    values: Dict[str, Any]


@router.post("/insight")
async def get_kpi_insight(
    payload: KpiInsightRequest,
    current_user: Dict = Depends(get_current_user),
):
    """
    Recibe datos de un KPI y devuelve un análisis en español generado por Claude.
    Interpreta el valor actual en el contexto financiero del negocio mexicano.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY no configurada")

    # Serializar valores para el prompt
    values_text = "\n".join(
        f"  • {k}: {v}" for k, v in payload.values.items() if v is not None
    )

    prompt = (
        f"Eres un CFO experto en empresas mexicanas analizando el flujo de caja.\n\n"
        f"KPI analizado: {payload.kpi_name}\n"
        f"Descripción: {payload.description}\n"
        f"Fórmula: {payload.formula}\n\n"
        f"Valores actuales:\n{values_text}\n\n"
        f"Proporciona un análisis ejecutivo en español (máximo 110 palabras) que incluya:\n"
        f"1. Si el valor es favorable, desfavorable o neutro para el negocio\n"
        f"2. Qué implica para la liquidez y operación\n"
        f"3. Una acción concreta y prioritaria que debería tomar el CFO\n\n"
        f"Responde directamente, en tono ejecutivo, sin encabezados ni listas."
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        resp.raise_for_status()
        insight = resp.json()["content"][0]["text"].strip()
        return {"insight": insight}

    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Error al llamar a Claude API: {str(e)}")
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=502, detail=f"Respuesta inesperada de Claude: {str(e)}")
