"""Módulo de Financiamientos — Simulador de Crédito con impacto en Cash Flow"""
from fastapi import APIRouter, Depends, Request
from typing import Dict
from core.database import db
from core.auth import get_current_user, get_active_company_id
from services.cashflow_calculator import calcular_semanas_cashflow

router = APIRouter()


@router.post("/financiamiento/simular")
async def simular_credito(
    request: Request,
    data: dict,
    current_user: Dict = Depends(get_current_user)
):
    """
    Simula un crédito y muestra su impacto semana a semana en el Cash Flow.
    Funciona con cualquier ERP (Contalink, Alegra, SAT, etc.)
    """
    company_id = await get_active_company_id(request, current_user)

    monto = float(data.get('monto', 0))
    tasa_anual = float(data.get('tasa_anual', 12)) / 100
    plazo_meses = int(data.get('plazo_meses', 12))

    if monto <= 0 or plazo_meses <= 0:
        return {'status': 'error', 'message': 'Monto y plazo requeridos'}

    # ── Cuota mensual (amortización francesa) ──
    tasa_mensual = tasa_anual / 12
    if tasa_mensual > 0:
        cuota_mensual = monto * (tasa_mensual * (1 + tasa_mensual)**plazo_meses) / ((1 + tasa_mensual)**plazo_meses - 1)
    else:
        cuota_mensual = monto / plazo_meses

    cuota_semanal = cuota_mensual / 4.33
    total_pagar = cuota_mensual * plazo_meses
    total_intereses = total_pagar - monto

    # ── Tabla de amortización mensual ──
    tabla_amortizacion = []
    saldo = monto
    for mes in range(1, plazo_meses + 1):
        interes = saldo * tasa_mensual
        capital = cuota_mensual - interes
        saldo -= capital
        tabla_amortizacion.append({
            'mes': mes,
            'cuota': round(cuota_mensual, 2),
            'capital': round(capital, 2),
            'interes': round(interes, 2),
            'saldo': round(max(0, saldo), 2),
        })

    # ── Impacto en Cash Flow semanal ──
    semanas = await calcular_semanas_cashflow(company_id, 26, db)

    semanas_con_impacto = []
    for week in semanas:
        semanas_con_impacto.append({
            **week,
            'cuota_credito': round(cuota_semanal, 2),
            'flujo_neto_sin_credito': week['flujo_neto'],
            'flujo_neto_con_credito': round(week['flujo_neto'] - cuota_semanal, 2),
            'saldo_con_credito': round(week.get('saldo_inicial', 0) + week['flujo_neto'] - cuota_semanal, 2),
            'alerta': (week['flujo_neto'] - cuota_semanal) < 0,
        })

    # ── Score de viabilidad ──
    semanas_con_datos = [s for s in semanas_con_impacto if s['flujo_neto_sin_credito'] != 0]
    flujo_promedio = (
        sum(s['flujo_neto_sin_credito'] for s in semanas_con_datos) / len(semanas_con_datos)
        if semanas_con_datos else 0
    )
    semanas_criticas = sum(1 for s in semanas_con_impacto if s['alerta'])

    if flujo_promedio <= 0:
        viabilidad, viabilidad_msg, score = 'no_viable', 'Tu flujo actual no soporta pagos adicionales', 0
    elif cuota_semanal > flujo_promedio * 0.5:
        viabilidad = 'riesgo_alto'
        viabilidad_msg = 'La cuota representa más del 50% de tu flujo promedio'
        score = 40
    elif cuota_semanal > flujo_promedio * 0.3:
        viabilidad = 'riesgo_medio'
        viabilidad_msg = 'La cuota es manejable pero ajustada'
        score = 70
    else:
        viabilidad = 'viable'
        viabilidad_msg = 'Tu flujo soporta cómodamente este crédito'
        score = 95

    # ── Análisis IA ──
    try:
        import anthropic
        import os
        client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))
        pct_flujo = f"{cuota_semanal/flujo_promedio*100:.0f}%" if flujo_promedio > 0 else "N/A"
        prompt = (
            f"Eres un CFO experto en empresas mexicanas. Analiza esta solicitud de crédito:\n\n"
            f"Monto solicitado: ${monto:,.0f} MXN\n"
            f"Tasa anual: {tasa_anual*100:.1f}%\n"
            f"Plazo: {plazo_meses} meses\n"
            f"Cuota mensual: ${cuota_mensual:,.0f} MXN\n"
            f"Total a pagar: ${total_pagar:,.0f} MXN (intereses: ${total_intereses:,.0f})\n"
            f"Flujo neto promedio semanal: ${flujo_promedio:,.0f} MXN\n"
            f"Semanas con flujo negativo si toma el crédito: {semanas_criticas} de 26\n"
            f"Viabilidad calculada: {viabilidad}\n\n"
            f"Da un análisis ejecutivo en español de máximo 100 palabras con: "
            f"1) Si conviene tomar este crédito, 2) El mayor riesgo, 3) Una recomendación concreta."
        )
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        analisis_ia = msg.content[0].text
    except Exception:
        pct = f"{cuota_semanal/flujo_promedio*100:.0f}%" if flujo_promedio > 0 else "N/A"
        analisis_ia = (
            f"Crédito {'viable' if score >= 70 else 'de alto riesgo'}. "
            f"Cuota mensual de ${cuota_mensual:,.0f} representa el {pct} de tu flujo promedio semanal."
        )

    return {
        'status': 'success',
        'simulacion': {
            'monto': monto,
            'tasa_anual_pct': tasa_anual * 100,
            'plazo_meses': plazo_meses,
            'cuota_mensual': round(cuota_mensual, 2),
            'cuota_semanal': round(cuota_semanal, 2),
            'total_pagar': round(total_pagar, 2),
            'total_intereses': round(total_intereses, 2),
            'costo_financiero_pct': round(total_intereses / monto * 100, 1),
        },
        'viabilidad': {
            'status': viabilidad,
            'mensaje': viabilidad_msg,
            'score': score,
            'semanas_criticas': semanas_criticas,
            'flujo_promedio_semanal': round(flujo_promedio, 2),
            'cobertura_cuota_pct': round(flujo_promedio / cuota_semanal * 100, 1) if cuota_semanal > 0 else 0,
        },
        'tabla_amortizacion': tabla_amortizacion,
        'impacto_cashflow': semanas_con_impacto[:16],
        'analisis_ia': analisis_ia,
    }


@router.get("/financiamiento/capacidad-pago")
async def get_capacidad_pago(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Calcula cuánto crédito puede pagar la empresa basado en su Cash Flow real."""
    company_id = await get_active_company_id(request, current_user)
    semanas = await calcular_semanas_cashflow(company_id, 13, db)

    semanas_con_datos = [s for s in semanas if s.get('flujo_neto', 0) != 0]
    if not semanas_con_datos:
        return {'status': 'insufficient_data', 'message': 'No hay suficientes datos de flujo'}

    flujo_promedio_semanal = sum(s['flujo_neto'] for s in semanas_con_datos) / len(semanas_con_datos)
    flujo_minimo_semanal = min(s['flujo_neto'] for s in semanas_con_datos)
    flujo_mensual = flujo_promedio_semanal * 4.33

    capacidad_conservadora = max(0, flujo_minimo_semanal * 4.33 * 0.30)
    capacidad_moderada = max(0, flujo_mensual * 0.30)
    capacidad_agresiva = max(0, flujo_mensual * 0.50)

    def monto_maximo(cuota_max, tasa_anual=0.18, plazo=24):
        tasa_m = tasa_anual / 12
        if tasa_m == 0:
            return cuota_max * plazo
        return cuota_max * ((1 + tasa_m)**plazo - 1) / (tasa_m * (1 + tasa_m)**plazo)

    return {
        'status': 'success',
        'flujo_promedio_mensual': round(flujo_mensual, 2),
        'flujo_minimo_mensual': round(flujo_minimo_semanal * 4.33, 2),
        'capacidad_pago': {
            'conservadora': {
                'cuota_max': round(capacidad_conservadora, 2),
                'credito_max_24m': round(monto_maximo(capacidad_conservadora), 2),
                'descripcion': 'Basado en tu peor semana — riesgo mínimo',
            },
            'moderada': {
                'cuota_max': round(capacidad_moderada, 2),
                'credito_max_24m': round(monto_maximo(capacidad_moderada), 2),
                'descripcion': 'Basado en tu promedio — recomendado',
            },
            'agresiva': {
                'cuota_max': round(capacidad_agresiva, 2),
                'credito_max_24m': round(monto_maximo(capacidad_agresiva), 2),
                'descripcion': 'Basado en 50% de tu promedio — mayor riesgo',
            },
        },
        'semanas_analizadas': len(semanas_con_datos),
        'fuente': 'Cash Flow real (CFDIs + proyecciones)',
    }
