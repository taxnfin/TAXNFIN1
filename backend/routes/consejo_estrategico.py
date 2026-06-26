"""
TaxnFin — Consejo Estratégico IA
Analiza decisiones empresariales desde 5 perspectivas independientes usando Claude.
"""
import os
import anthropic
from datetime import datetime, timezone, date, timedelta
from fastapi import APIRouter, Depends, Request
from typing import Dict
from core.auth import get_current_user, get_active_company_id
from core.database import db

router = APIRouter(prefix="/ia", tags=["Consejo Estratégico IA"])


async def _get_contexto_financiero(company_id: str) -> str:
    """Construye un resumen financiero real de la empresa para el prompt."""
    try:
        hoy = date.today()
        inicio_mes = hoy.replace(day=1).isoformat()
        hace_30 = (hoy - timedelta(days=30)).isoformat()

        # ── CxC ──────────────────────────────────────────────────────────────
        cxc_docs = await db.cfdis.find({
            'company_id': company_id,
            'tipo_cfdi': 'ingreso',
            'source': 'alegra',
            'estado_conciliacion': {'$in': ['pendiente', 'parcial']},
        }, {'_id': 0, 'total': 1, 'moneda': 1, 'tipo_cambio': 1,
            'saldo_pendiente': 1, 'monto_cobrado': 1,
            'fecha_vencimiento': 1, 'receptor_nombre': 1}).to_list(500)

        total_cxc = 0
        cxc_vencida = 0
        for inv in cxc_docs:
            tc = float(inv.get('tipo_cambio', 1) or 1)
            moneda = inv.get('moneda', 'MXN')
            total_orig = float(inv.get('total', 0) or 0)
            cobrado = float(inv.get('monto_cobrado', 0) or 0)
            saldo = float(inv.get('saldo_pendiente') or (total_orig - cobrado))
            saldo_mxn = round(saldo * tc, 2) if moneda != 'MXN' else saldo
            total_cxc += saldo_mxn
            fv = str(inv.get('fecha_vencimiento') or '')[:10]
            if fv and fv < hoy.isoformat():
                cxc_vencida += saldo_mxn

        # ── CxP ──────────────────────────────────────────────────────────────
        cxp_docs = await db.cfdis.find({
            'company_id': company_id,
            'tipo_cfdi': 'egreso',
            'source': 'alegra',
            'estado_conciliacion': {'$in': ['pendiente', 'parcial']},
        }, {'_id': 0, 'total': 1, 'moneda': 1, 'tipo_cambio': 1,
            'saldo_pendiente': 1, 'monto_pagado': 1,
            'fecha_vencimiento': 1, 'emisor_nombre': 1}).to_list(500)

        total_cxp = 0
        cxp_vencida = 0
        for bill in cxp_docs:
            tc = float(bill.get('tipo_cambio', 1) or 1)
            moneda = bill.get('moneda', 'MXN')
            total_orig = float(bill.get('total', 0) or 0)
            pagado = float(bill.get('monto_pagado', 0) or 0)
            saldo = round(total_orig - pagado, 2)
            saldo_mxn = round(saldo * tc, 2) if moneda != 'MXN' else saldo
            total_cxp += saldo_mxn
            fv = str(bill.get('fecha_vencimiento') or '')[:10]
            if fv and fv < hoy.isoformat():
                cxp_vencida += saldo_mxn

        # ── Saldo bancario ────────────────────────────────────────────────────
        cuentas = await db.bank_accounts.find(
            {'company_id': company_id, 'activa': {'$ne': False}},
            {'_id': 0, 'saldo_actual': 1, 'moneda': 1, 'nombre': 1}
        ).to_list(20)
        saldo_bancos = sum(
            float(c.get('saldo_actual', 0) or 0) *
            (float(c.get('tipo_cambio', 17.5) or 17.5) if c.get('moneda', 'MXN') != 'MXN' else 1)
            for c in cuentas
        )

        # ── Pagos del mes (ingresos y egresos reales) ─────────────────────────
        pagos = await db.payments.find({
            'company_id': company_id,
            'fecha_pago': {'$gte': inicio_mes},
        }, {'_id': 0, 'monto': 1, 'tipo': 1, 'moneda': 1, 'tipo_cambio': 1}).to_list(2000)

        ingresos_mes = sum(
            float(p.get('monto', 0) or 0) *
            (float(p.get('tipo_cambio', 17.5) or 17.5) if p.get('moneda', 'MXN') != 'MXN' else 1)
            for p in pagos if p.get('tipo') in ('cobro', 'ingreso')
        )
        egresos_mes = sum(
            float(p.get('monto', 0) or 0) *
            (float(p.get('tipo_cambio', 17.5) or 17.5) if p.get('moneda', 'MXN') != 'MXN' else 1)
            for p in pagos if p.get('tipo') in ('pago', 'egreso')
        )
        flujo_neto_mes = ingresos_mes - egresos_mes

        # ── Formateador ───────────────────────────────────────────────────────
        def fmt(n):
            return f"${n:,.0f} MXN"

        contexto = f"""
CONTEXTO FINANCIERO REAL DE LA EMPRESA (al {hoy.strftime('%d/%m/%Y')}):

💰 SALDO EN BANCOS:          {fmt(saldo_bancos)}

📈 CUENTAS POR COBRAR (CxC):
   • Total pendiente:         {fmt(total_cxc)}  ({len(cxc_docs)} facturas)
   • De las cuales vencidas:  {fmt(cxc_vencida)}

📉 CUENTAS POR PAGAR (CxP):
   • Total pendiente:         {fmt(total_cxp)}  ({len(cxp_docs)} facturas)
   • De las cuales vencidas:  {fmt(cxp_vencida)}

📊 FLUJO DEL MES EN CURSO ({hoy.strftime('%B %Y')}):
   • Ingresos cobrados:       {fmt(ingresos_mes)}
   • Egresos pagados:         {fmt(egresos_mes)}
   • Flujo neto:              {fmt(flujo_neto_mes)} {'✅' if flujo_neto_mes >= 0 else '🔴 NEGATIVO'}

🔑 INDICADORES CLAVE:
   • Capital de trabajo neto: {fmt(total_cxc - total_cxp)}
   • Días para cubrir CxP con bancos: {'∞' if egresos_mes <= 0 else f'{saldo_bancos / (egresos_mes / 30):.0f} días'}
"""
        return contexto.strip()

    except Exception as e:
        print(f"[CONSEJO] Error obteniendo contexto: {e}", flush=True)
        return "No se pudo obtener contexto financiero actualizado."


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

    # Obtener contexto financiero real
    contexto_financiero = await _get_contexto_financiero(company_id)

    prompt = f"""Eres el coordinador de un consejo de cinco asesores estratégicos analizando decisiones para {company_name}.

{contexto_financiero}

Tienes acceso a los datos financieros reales de la empresa mostrados arriba. Úsalos para hacer tu análisis específico y concreto — no genérico. Cuando algún asesor mencione flujo, liquidez, deuda o capital de trabajo, debe referirse a los números reales de la empresa.

Analiza esta pregunta/decisión desde cinco perspectivas distintas e independientes:

PREGUNTA: {pregunta}

1. 🔴 EL CONTRARIAN — Busca activamente lo que puede fallar. Asume que hay un error fatal y trata de encontrarlo. No busca equilibrio, busca el punto de quiebre. Usa los datos financieros para identificar vulnerabilidades concretas.

2. 🔵 EL PENSADOR DE PRIMEROS PRINCIPIOS — Ignora la pregunta superficial y pregunta qué es lo que realmente se está intentando resolver. Desmonta todos los supuestos. Regresa a la causa raíz. Cuestiona si los números de la empresa realmente sustentan la decisión.

3. 🟢 EL EXPANSIONISTA — Busca el upside que todos los demás están ignorando. ¿Qué oportunidad se está subestimando? ¿Qué pasa si esto funciona mejor de lo esperado? ¿Cómo puede la posición financiera actual ser un trampolín?

4. 🟡 EL OUTSIDER — No tiene contexto previo. Responde únicamente a lo que tiene delante. Detecta lo que es obvio para un extraño pero invisible para quien está demasiado dentro. Mira los números con ojos frescos.

5. 🟠 EL EJECUTOR — Solo le importa una cosa: ¿Se puede hacer con la liquidez disponible, y cuál es el camino más rápido? Ignora la teoría. ¿Qué hago el lunes por la mañana con este saldo en bancos y esta cartera?

INSTRUCCIONES:
- Cada asesor responde de forma independiente y defiende su ángulo con fuerza. Mínimo 3 párrafos cada uno.
- Cada asesor debe usar al menos un dato financiero real de la empresa en su análisis.
- Después, cada asesor revisa las respuestas de los otros e identifica: cuál es la más sólida, cuál tiene el mayor punto ciego, y qué no ha visto nadie.
- Al final, el PRESIDENTE DEL CONSEJO sintetiza: dónde coinciden, dónde chocan, qué se detectó en la revisión, y UNA recomendación concreta con un único primer paso que sea accionable esta semana.

Responde en español. Sé directo, sin suavizar. Cada perspectiva debe defender su ángulo con convicción y basarse en los datos reales."""

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
            "contexto_financiero": contexto_financiero,
            "created_at": datetime.now(timezone.utc),
        })

        return {"success": True, "respuesta": respuesta, "contexto": contexto_financiero}

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


@router.delete("/consejo-estrategico/historial")
async def borrar_historial(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    company_id = await get_active_company_id(request, current_user)
    result = await db.consejo_estrategico_historial.delete_many({"company_id": company_id})
    return {"deleted": result.deleted_count}
