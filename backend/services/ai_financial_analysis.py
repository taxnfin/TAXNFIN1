"""
AI Financial Analysis Service
Generates professional financial commentary and KPI explanations using GPT-5.2
"""
import os
import logging
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

async def generate_financial_analysis(
    metrics: Dict,
    income_statement: Dict,
    balance_sheet: Dict,
    company_name: str,
    period: str,
    language: str = 'es'
) -> Dict:
    """
    Generate AI-powered financial analysis for executive reports
    
    Args:
        metrics: Financial metrics dictionary with margins, returns, efficiency, liquidity, solvency
        income_statement: Income statement data
        balance_sheet: Balance sheet data
        company_name: Name of the company
        period: Period being analyzed (e.g., "Q1 2024", "2024-01")
        language: Language for the analysis ('es', 'en', 'pt')
    
    Returns:
        Dictionary with analysis sections
    """
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            logger.warning("EMERGENT_LLM_KEY not found, returning default analysis")
            return get_default_analysis(language)
        
        # Prepare financial data summary
        margins = metrics.get('margins', {})
        returns = metrics.get('returns', {})
        efficiency = metrics.get('efficiency', {})
        liquidity = metrics.get('liquidity', {})
        solvency = metrics.get('solvency', {})
        
        # Build context for the AI
        financial_context = f"""
DATOS FINANCIEROS DE {company_name} - PERÍODO: {period}

ESTADO DE RESULTADOS:
- Ingresos: ${income_statement.get('ingresos', 0):,.0f}
- Costo de Ventas: ${income_statement.get('costo_ventas', 0):,.0f}
- Utilidad Bruta: ${income_statement.get('utilidad_bruta', 0):,.0f}
- Utilidad Operativa: ${income_statement.get('utilidad_operativa', 0):,.0f}
- EBITDA: ${income_statement.get('ebitda', 0):,.0f}
- Utilidad Neta: ${income_statement.get('utilidad_neta', 0):,.0f}

BALANCE GENERAL:
- Activo Total: ${balance_sheet.get('activo_total', 0):,.0f}
- Activo Circulante: ${balance_sheet.get('activo_circulante', 0):,.0f}
- Efectivo: ${balance_sheet.get('efectivo', 0):,.0f}
- Pasivo Total: ${balance_sheet.get('pasivo_total', 0):,.0f}
- Capital Contable: ${balance_sheet.get('capital_contable', 0):,.0f}

MÁRGENES:
- Margen Bruto: {margins.get('gross_margin', {}).get('value', 0):.1f}%
- Margen EBITDA: {margins.get('ebitda_margin', {}).get('value', 0):.1f}%
- Margen Operativo: {margins.get('operating_margin', {}).get('value', 0):.1f}%
- Margen Neto: {margins.get('net_margin', {}).get('value', 0):.1f}%

RETORNOS:
- ROIC: {returns.get('roic', {}).get('value', 0):.1f}%
- ROE: {returns.get('roe', {}).get('value', 0):.1f}%
- ROA: {returns.get('roa', {}).get('value', 0):.1f}%

EFICIENCIA:
- Rotación de Activos: {efficiency.get('asset_turnover', {}).get('value', 0):.2f}x
- DSO (Días de Cobro): {efficiency.get('dso', {}).get('value', 0):.0f} días
- DPO (Días de Pago): {efficiency.get('dpo', {}).get('value', 0):.0f} días
- Ciclo de Conversión: {efficiency.get('cash_conversion_cycle', {}).get('value', 0):.0f} días

LIQUIDEZ:
- Razón Circulante: {liquidity.get('current_ratio', {}).get('value', 0):.2f}x
- Prueba Ácida: {liquidity.get('quick_ratio', {}).get('value', 0):.2f}x
- Capital de Trabajo: ${liquidity.get('working_capital', {}).get('value', 0):,.0f}

SOLVENCIA:
- Deuda/Capital: {solvency.get('debt_to_equity', {}).get('value', 0):.2f}x
- Deuda/Activos: {solvency.get('debt_to_assets', {}).get('value', 0):.1f}%
- Cobertura de Intereses: {solvency.get('interest_coverage', {}).get('value', 0):.1f}x
"""
        
        lang_instructions = {
            'es': 'Responde en español.',
            'en': 'Respond in English.',
            'pt': 'Responda em português.'
        }
        
        system_message = f"""Eres un analista financiero senior especializado en reportes ejecutivos para juntas directivas.
{lang_instructions.get(language, lang_instructions['es'])}

Tu tarea es generar análisis financiero profesional, conciso y accionable.
- Usa un tono ejecutivo y profesional
- Sé específico con los números
- Destaca fortalezas y áreas de mejora
- Incluye recomendaciones cuando sea apropiado
- Cada sección debe ser de 2-4 oraciones máximo
- NO uses viñetas ni listas, escribe en párrafos cortos"""

        chat = LlmChat(
            api_key=api_key,
            session_id=f"financial-analysis-{period}",
            system_message=system_message
        ).with_model("openai", "gpt-5.2")
        
        # Generate Executive Summary
        exec_prompt = f"""{financial_context}

Genera un RESUMEN EJECUTIVO de 3-4 oraciones que destaque:
1. El desempeño general del período
2. Los principales indicadores positivos
3. Las áreas que requieren atención

Solo escribe el texto del resumen, sin títulos ni encabezados."""

        exec_message = UserMessage(text=exec_prompt)
        executive_summary = await chat.send_message(exec_message)
        
        # Generate Profitability Analysis
        profit_prompt = f"""{financial_context}

Genera un ANÁLISIS DE RENTABILIDAD de 2-3 oraciones interpretando los márgenes (bruto, operativo, neto, EBITDA).
Menciona si están en rangos saludables y qué indican sobre la operación.

Solo escribe el texto del análisis, sin títulos."""

        profit_message = UserMessage(text=profit_prompt)
        profitability_analysis = await chat.send_message(profit_message)
        
        # Generate Returns Analysis
        returns_prompt = f"""{financial_context}

Genera un ANÁLISIS DE RETORNOS de 2-3 oraciones interpretando ROIC, ROE y ROA.
Explica qué tan eficiente es la empresa generando valor para los accionistas.

Solo escribe el texto del análisis, sin títulos."""

        returns_message = UserMessage(text=returns_prompt)
        returns_analysis = await chat.send_message(returns_message)
        
        # Generate Liquidity Analysis
        liquidity_prompt = f"""{financial_context}

Genera un ANÁLISIS DE LIQUIDEZ de 2-3 oraciones interpretando la razón circulante, prueba ácida y capital de trabajo.
Indica si la empresa puede cumplir sus obligaciones de corto plazo.

Solo escribe el texto del análisis, sin títulos."""

        liquidity_message = UserMessage(text=liquidity_prompt)
        liquidity_analysis = await chat.send_message(liquidity_message)
        
        # Generate Solvency Analysis
        solvency_prompt = f"""{financial_context}

Genera un ANÁLISIS DE SOLVENCIA de 2-3 oraciones interpretando el nivel de endeudamiento y cobertura de intereses.
Indica el riesgo financiero de la estructura de capital.

Solo escribe el texto del análisis, sin títulos."""

        solvency_message = UserMessage(text=solvency_prompt)
        solvency_analysis = await chat.send_message(solvency_message)
        
        # Generate Recommendations
        recommendations_prompt = f"""{financial_context}

Genera 2-3 RECOMENDACIONES ESTRATÉGICAS breves basadas en el análisis financiero.
Cada recomendación debe ser específica y accionable.

Solo escribe las recomendaciones en un párrafo, sin numeración ni viñetas."""

        recommendations_message = UserMessage(text=recommendations_prompt)
        recommendations = await chat.send_message(recommendations_message)
        
        return {
            "executive_summary": executive_summary,
            "profitability_analysis": profitability_analysis,
            "returns_analysis": returns_analysis,
            "liquidity_analysis": liquidity_analysis,
            "solvency_analysis": solvency_analysis,
            "recommendations": recommendations,
            "generated_by": "AI",
            "model": "gpt-5.2"
        }
        
    except ImportError as e:
        logger.error(f"emergentintegrations not installed: {e}")
        return get_default_analysis(language)
    except Exception as e:
        logger.error(f"Error generating AI analysis: {e}")
        return get_default_analysis(language)


def get_default_analysis(language: str = 'es') -> Dict:
    """Return default analysis when AI is not available"""
    
    defaults = {
        'es': {
            "executive_summary": "Los datos financieros del período muestran el desempeño operativo de la empresa. Se recomienda revisar los indicadores clave para tomar decisiones informadas.",
            "profitability_analysis": "Los márgenes de rentabilidad reflejan la eficiencia operativa. Se sugiere comparar con períodos anteriores y con el promedio de la industria.",
            "returns_analysis": "Los indicadores de retorno muestran la capacidad de generar valor sobre el capital invertido. Es importante monitorear su evolución.",
            "liquidity_analysis": "Los indicadores de liquidez muestran la capacidad de la empresa para cumplir con sus obligaciones de corto plazo.",
            "solvency_analysis": "La estructura de capital y el nivel de endeudamiento determinan el riesgo financiero de la empresa.",
            "recommendations": "Se recomienda realizar un análisis más detallado de las tendencias históricas y comparar con benchmarks de la industria para obtener conclusiones más específicas.",
            "generated_by": "Default",
            "model": "N/A"
        },
        'en': {
            "executive_summary": "The financial data for the period shows the company's operational performance. It is recommended to review key indicators to make informed decisions.",
            "profitability_analysis": "Profitability margins reflect operational efficiency. It is suggested to compare with previous periods and industry averages.",
            "returns_analysis": "Return indicators show the ability to generate value on invested capital. It is important to monitor their evolution.",
            "liquidity_analysis": "Liquidity indicators show the company's ability to meet its short-term obligations.",
            "solvency_analysis": "The capital structure and level of indebtedness determine the company's financial risk.",
            "recommendations": "It is recommended to perform a more detailed analysis of historical trends and compare with industry benchmarks for more specific conclusions.",
            "generated_by": "Default",
            "model": "N/A"
        },
        'pt': {
            "executive_summary": "Os dados financeiros do período mostram o desempenho operacional da empresa. Recomenda-se revisar os indicadores-chave para tomar decisões informadas.",
            "profitability_analysis": "As margens de rentabilidade refletem a eficiência operacional. Sugere-se comparar com períodos anteriores e com a média do setor.",
            "returns_analysis": "Os indicadores de retorno mostram a capacidade de gerar valor sobre o capital investido. É importante monitorar sua evolução.",
            "liquidity_analysis": "Os indicadores de liquidez mostram a capacidade da empresa de cumprir suas obrigações de curto prazo.",
            "solvency_analysis": "A estrutura de capital e o nível de endividamento determinam o risco financeiro da empresa.",
            "recommendations": "Recomenda-se realizar uma análise mais detalhada das tendências históricas e comparar com benchmarks do setor para obter conclusões mais específicas.",
            "generated_by": "Default",
            "model": "N/A"
        }
    }
    
    return defaults.get(language, defaults['es'])
