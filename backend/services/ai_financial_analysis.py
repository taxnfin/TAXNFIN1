"""AI Financial Analysis Service — Claude API integration via httpx."""
import json
import logging
import os
import re
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
MODEL = 'claude-sonnet-4-6'


def _fmt(n) -> str:
    if n is None:
        return '0'
    n = float(n)
    if abs(n) >= 1_000_000:
        return f'{n/1_000_000:.1f}M'
    if abs(n) >= 1_000:
        return f'{n/1_000:.0f}K'
    return f'{n:.0f}'


def _pct(n) -> str:
    if n is None:
        return '0%'
    return f'{float(n):.1f}%'


def _build_prompt(
    company_name: str,
    period: str,
    income_statement: Dict,
    balance_sheet: Dict,
    metrics: Dict,
    trends_data: Optional[List] = None,
    language: str = 'es',
) -> str:
    inc = income_statement or {}
    bal = balance_sheet or {}
    met = metrics or {}

    ventas = _fmt(inc.get('ventas_netas') or inc.get('ingresos_totales', 0))
    utilidad_bruta = _fmt(inc.get('utilidad_bruta', 0))
    utilidad_op = _fmt(inc.get('utilidad_operativa') or inc.get('utilidad_operacional', 0))
    utilidad_neta = _fmt(inc.get('utilidad_neta', 0))
    ebitda = _fmt(inc.get('ebitda', 0))

    activo_total = _fmt(bal.get('activo_total') or bal.get('total_activos', 0))
    activo_circ = _fmt(bal.get('activo_circulante') or bal.get('activos_corrientes', 0))
    pasivo_total = _fmt(bal.get('pasivo_total') or bal.get('total_pasivos', 0))
    capital = _fmt(bal.get('capital_contable') or bal.get('patrimonio', 0))

    margen_bruto = _pct(met.get('margen_bruto'))
    margen_op = _pct(met.get('margen_operativo') or met.get('margen_operacional'))
    margen_neto = _pct(met.get('margen_neto'))
    roe = _pct(met.get('roe') or met.get('retorno_capital'))
    roa = _pct(met.get('roa') or met.get('retorno_activos'))
    liquidez = _pct(met.get('razon_circulante') or met.get('liquidez_corriente'))
    endeudamiento = _pct(met.get('razon_endeudamiento') or met.get('nivel_endeudamiento'))

    trends_block = ''
    if trends_data:
        lines = []
        for t in trends_data[-4:]:
            p = t.get('periodo', '')
            s = t.get('income_statement', {})
            v = _fmt(s.get('ventas_netas') or s.get('ingresos_totales', 0))
            u = _fmt(s.get('utilidad_neta', 0))
            lines.append(f'  - {p}: Ventas {v}, Utilidad neta {u}')
        trends_block = 'TENDENCIA HISTÓRICA:\n' + '\n'.join(lines) + '\n\n'

    if language == 'es':
        return f"""Eres un CFO virtual experto en finanzas corporativas mexicanas. Analiza los siguientes estados financieros y devuelve EXCLUSIVAMENTE un objeto JSON válido (sin markdown, sin texto extra).

EMPRESA: {company_name}
PERÍODO: {period}

ESTADO DE RESULTADOS:
- Ventas netas: ${ventas}
- Utilidad bruta: ${utilidad_bruta} (margen: {margen_bruto})
- Utilidad operativa: ${utilidad_op} (margen: {margen_op})
- EBITDA: ${ebitda}
- Utilidad neta: ${utilidad_neta} (margen: {margen_neto})

BALANCE GENERAL:
- Activo total: ${activo_total}
- Activo circulante: ${activo_circ}
- Pasivo total: ${pasivo_total}
- Capital contable: ${capital}

INDICADORES CLAVE:
- ROE: {roe} | ROA: {roa}
- Liquidez corriente: {liquidez}
- Endeudamiento: {endeudamiento}

{trends_block}Responde SOLO con este JSON (sin bloques de código):
{{
  "executive_summary": "Resumen ejecutivo de 3-4 oraciones con los hallazgos más importantes del período.",
  "profitability_analysis": "Análisis de márgenes y rentabilidad, comparando ventas vs utilidades, identificando tendencias.",
  "returns_analysis": "Evaluación de ROE y ROA con interpretación del retorno sobre capital e inversión.",
  "liquidity_analysis": "Análisis de liquidez y capacidad de pago de obligaciones de corto plazo.",
  "solvency_analysis": "Evaluación de estructura de capital, nivel de deuda y riesgo financiero.",
  "income_flow_analysis": "Flujo del estado de resultados: cómo los ingresos se transforman en utilidad neta.",
  "recommendations": "3-5 recomendaciones concretas y accionables para mejorar el desempeño financiero.",
  "trends_analysis": "Análisis de tendencias históricas y proyección cualitativa del desempeño futuro.",
  "generated_by": "Claude",
  "model": "{MODEL}"
}}"""
    else:
        return f"""You are a virtual CFO expert in corporate finance. Analyze the following financial statements and return ONLY a valid JSON object (no markdown, no extra text).

COMPANY: {company_name}
PERIOD: {period}

INCOME STATEMENT:
- Net sales: ${ventas}
- Gross profit: ${utilidad_bruta} (margin: {margen_bruto})
- Operating income: ${utilidad_op} (margin: {margen_op})
- EBITDA: ${ebitda}
- Net income: ${utilidad_neta} (margin: {margen_neto})

BALANCE SHEET:
- Total assets: ${activo_total}
- Current assets: ${activo_circ}
- Total liabilities: ${pasivo_total}
- Equity: ${capital}

KEY RATIOS:
- ROE: {roe} | ROA: {roa}
- Current ratio: {liquidez}
- Debt ratio: {endeudamiento}

{trends_block}Respond ONLY with this JSON (no code blocks):
{{
  "executive_summary": "3-4 sentence executive summary with the most important findings.",
  "profitability_analysis": "Margin and profitability analysis comparing revenue vs profits.",
  "returns_analysis": "ROE and ROA evaluation with interpretation of return on capital.",
  "liquidity_analysis": "Liquidity analysis and short-term obligation coverage.",
  "solvency_analysis": "Capital structure, debt level and financial risk assessment.",
  "income_flow_analysis": "Income statement flow: how revenue converts to net income.",
  "recommendations": "3-5 concrete actionable recommendations to improve financial performance.",
  "trends_analysis": "Historical trend analysis and qualitative forward-looking assessment.",
  "generated_by": "Claude",
  "model": "{MODEL}"
}}"""


async def generate_financial_analysis(
    company_name: str,
    period: str,
    income_statement: Dict,
    balance_sheet: Dict,
    metrics: Dict,
    language: str = 'es',
    **kwargs
) -> Dict:
    """Generate financial analysis using Claude API. Falls back to defaults if unavailable."""
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY in ('test-key', 'your-anthropic-key', ''):
        logger.info(f"Claude API key not configured — returning defaults for {company_name} / {period}")
        return get_default_analysis(language)

    trends_data = kwargs.get('trends_data')
    prompt = _build_prompt(
        company_name=company_name,
        period=period,
        income_statement=income_statement,
        balance_sheet=balance_sheet,
        metrics=metrics,
        trends_data=trends_data,
        language=language,
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': ANTHROPIC_API_KEY,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json',
                },
                json={
                    'model': MODEL,
                    'max_tokens': 4000,
                    'messages': [{'role': 'user', 'content': prompt}],
                },
            )
            response.raise_for_status()
            result = response.json()
            text = result['content'][0]['text'].strip()

            # Limpiar markdown si viene con backticks
            text = text.strip()
            if '```' in text:
                md_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
                if md_match:
                    text = md_match.group(1).strip()
                else:
                    text = text.split('```')[1]
                    if text.startswith('json'):
                        text = text[4:]
                    text = text.strip()

            # Intentar parsear directo
            try:
                analysis = json.loads(text)
            except json.JSONDecodeError:
                # JSON truncado — extraer campos individualmente con regex
                analysis = {}
                fields = [
                    'executive_summary', 'profitability_analysis', 'returns_analysis',
                    'liquidity_analysis', 'solvency_analysis', 'income_flow_analysis',
                    'recommendations', 'trends_analysis'
                ]
                for field in fields:
                    pattern = rf'"{field}"\s*:\s*"((?:[^"\\]|\\.)*?)(?:"|$)'
                    field_match = re.search(pattern, text, re.DOTALL)
                    if field_match:
                        try:
                            analysis[field] = bytes(field_match.group(1), 'utf-8').decode('unicode_escape')
                        except Exception:
                            analysis[field] = field_match.group(1)

                if not analysis:
                    raise  # Re-raise si no se pudo extraer nada

            analysis['generated_by'] = 'Claude AI'
            analysis['model'] = MODEL
            logger.info(f"Claude analysis generated for {company_name} / {period}")
            return analysis

    except httpx.HTTPStatusError as e:
        import traceback
        logger.error(f"Claude API HTTP error {e.response.status_code}: {e.response.text[:500]}\n{traceback.format_exc()}")
    except json.JSONDecodeError as e:
        import traceback
        logger.error(f"Claude returned invalid JSON: {e}\n{traceback.format_exc()}")
    except Exception as e:
        import traceback
        logger.error(f"Claude API error: {type(e).__name__}: {e}\n{traceback.format_exc()}")

    return get_default_analysis(language)


def get_default_analysis(language: str = 'es') -> Dict:
    defaults = {
        'es': {
            "executive_summary": "Los datos financieros del período muestran el desempeño operativo de la empresa. Se recomienda revisar los indicadores clave para tomar decisiones informadas.",
            "profitability_analysis": "Los márgenes de rentabilidad reflejan la eficiencia operativa. Se sugiere comparar con períodos anteriores y con el promedio de la industria.",
            "returns_analysis": "Los indicadores de retorno muestran la capacidad de generar valor sobre el capital invertido. Es importante monitorear su evolución.",
            "liquidity_analysis": "Los indicadores de liquidez muestran la capacidad de la empresa para cumplir con sus obligaciones de corto plazo.",
            "solvency_analysis": "La estructura de capital y el nivel de endeudamiento determinan el riesgo financiero de la empresa.",
            "income_flow_analysis": "El flujo del estado de resultados muestra cómo los ingresos se transforman en utilidad neta.",
            "recommendations": "Se recomienda realizar un análisis más detallado de las tendencias históricas y comparar con benchmarks de la industria.",
            "trends_analysis": "Las tendencias históricas muestran la evolución del desempeño financiero.",
            "generated_by": "Default",
            "model": "N/A",
        },
        'en': {
            "executive_summary": "The financial data for the period shows the company's operational performance. It is recommended to review key indicators to make informed decisions.",
            "profitability_analysis": "Profitability margins reflect operational efficiency. It is suggested to compare with previous periods and industry averages.",
            "returns_analysis": "Return indicators show the ability to generate value on invested capital. It is important to monitor their evolution.",
            "liquidity_analysis": "Liquidity indicators show the company's ability to meet its short-term obligations.",
            "solvency_analysis": "The capital structure and level of indebtedness determine the company's financial risk.",
            "income_flow_analysis": "The income statement flow shows how revenue is converted to net income.",
            "recommendations": "It is recommended to perform a more detailed analysis of historical trends and compare with industry benchmarks.",
            "trends_analysis": "Historical trends show the evolution of financial performance.",
            "generated_by": "Default",
            "model": "N/A",
        },
        'pt': {
            "executive_summary": "Os dados financeiros do período mostram o desempenho operacional da empresa.",
            "profitability_analysis": "As margens de rentabilidade refletem a eficiência operacional.",
            "returns_analysis": "Os indicadores de retorno mostram a capacidade de gerar valor sobre o capital investido.",
            "liquidity_analysis": "Os indicadores de liquidez mostram a capacidade da empresa de cumprir suas obrigações de curto prazo.",
            "solvency_analysis": "A estrutura de capital e o nível de endividamento determinam o risco financeiro da empresa.",
            "income_flow_analysis": "O fluxo da demonstração de resultados mostra como a receita é convertida em lucro líquido.",
            "recommendations": "Recomenda-se realizar uma análise mais detalhada das tendências históricas.",
            "trends_analysis": "As tendências históricas mostram a evolução do desempenho financeiro.",
            "generated_by": "Default",
            "model": "N/A",
        },
    }
    return defaults.get(language, defaults['es'])
