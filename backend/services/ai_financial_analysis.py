"""
AI Financial Analysis Service
Generates professional financial commentary and KPI explanations using GPT-5.2
OPTIMIZED V2: Single API call for faster response (~4-6s)
"""
import os
import json
import logging
from typing import Dict
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


async def generate_financial_analysis(
    metrics: Dict,
    income_statement: Dict,
    balance_sheet: Dict,
    company_name: str,
    period: str,
    language: str = 'es',
    trends_data: list = None
) -> Dict:
    """
    Generate AI-powered financial analysis for executive reports
    OPTIMIZED V2: Uses a single API call to generate all sections at once
    
    Args:
        metrics: Financial metrics dictionary with margins, returns, efficiency, liquidity, solvency
        income_statement: Income statement data
        balance_sheet: Balance sheet data
        company_name: Name of the company
        period: Period being analyzed (e.g., "Q1 2024", "2024-01")
        language: Language for the analysis ('es', 'en', 'pt')
        trends_data: Optional list of historical period data for trends analysis
    
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
        
        # Add trends data if available
        if trends_data and len(trends_data) > 1:
            financial_context += "\n\nTENDENCIAS HISTÓRICAS:\n"
            for td in trends_data[-6:]:  # Last 6 periods max
                td_is = td.get('income_statement', {})
                financial_context += f"- {td.get('periodo', 'N/A')}: Ingresos ${td_is.get('ingresos', 0):,.0f}, Utilidad Bruta ${td_is.get('utilidad_bruta', 0):,.0f}, Utilidad Neta ${td_is.get('utilidad_neta', 0):,.0f}\n"
        
        lang_instructions = {
            'es': 'Responde SOLO en español.',
            'en': 'Respond ONLY in English.',
            'pt': 'Responda APENAS em português.'
        }
        
        system_message = f"""Eres un analista financiero senior especializado en reportes ejecutivos para juntas directivas.
{lang_instructions.get(language, lang_instructions['es'])}

Tu tarea es generar análisis financiero profesional, conciso y accionable.
- Usa un tono ejecutivo y profesional
- Sé específico con los números
- Destaca fortalezas y áreas de mejora
- Cada sección debe ser de 2-4 oraciones máximo
- NO uses viñetas ni listas, escribe en párrafos cortos
- IMPORTANTE: Responde ÚNICAMENTE con el JSON solicitado, sin texto adicional"""

        # Build JSON structure based on available data
        json_structure = """{
  "executive_summary": "Resumen ejecutivo de 3-4 oraciones sobre el desempeño general, indicadores positivos y áreas de atención",
  "profitability_analysis": "Análisis de 2-3 oraciones sobre los márgenes (bruto, operativo, neto, EBITDA)",
  "returns_analysis": "Análisis de 2-3 oraciones sobre ROIC, ROE y ROA",
  "liquidity_analysis": "Análisis de 2-3 oraciones sobre liquidez (razón circulante, prueba ácida, capital de trabajo)",
  "solvency_analysis": "Análisis de 2-3 oraciones sobre solvencia (endeudamiento, cobertura de intereses)",
  "recommendations": "2-3 recomendaciones estratégicas en un párrafo\""""
        
        # Add trends_analysis if we have historical data
        if trends_data and len(trends_data) > 1:
            json_structure += """,
  "trends_analysis": "Análisis de 3-5 oraciones explicando las tendencias observadas en los períodos históricos, identificando causas de cambios significativos (especialmente utilidades negativas), patrones y riesgos potenciales\""""
        
        json_structure += "\n}"
        
        # Single comprehensive prompt
        prompt = f"""{financial_context}

Genera un análisis financiero completo. Responde ÚNICAMENTE con un objeto JSON válido con estas secciones:

{json_structure}

Responde SOLO con el JSON, sin markdown ni texto adicional."""

        logger.info(f"Starting single-call AI analysis for {company_name} - {period}")
        
        chat = LlmChat(
            api_key=api_key,
            session_id=f"financial-analysis-{period}",
            system_message=system_message
        ).with_model("openai", "gpt-5.2")
        
        message = UserMessage(text=prompt)
        response = await chat.send_message(message)
        
        # Parse JSON response
        try:
            # Clean response (remove potential markdown code blocks)
            cleaned_response = response.strip()
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response.split("```")[1]
                if cleaned_response.startswith("json"):
                    cleaned_response = cleaned_response[4:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            
            analysis_result = json.loads(cleaned_response.strip())
            
            # Ensure all keys exist
            required_keys = ['executive_summary', 'profitability_analysis', 'returns_analysis', 
                           'liquidity_analysis', 'solvency_analysis', 'recommendations']
            
            # Add trends_analysis if we had trends data
            if trends_data and len(trends_data) > 1:
                required_keys.append('trends_analysis')
            
            defaults = get_default_analysis(language)
            
            for key in required_keys:
                if key not in analysis_result or not analysis_result[key]:
                    analysis_result[key] = defaults.get(key, '')
            
            analysis_result["generated_by"] = "AI"
            analysis_result["model"] = "gpt-5.2"
            
            logger.info(f"Completed single-call AI analysis for {company_name} - {period}")
            
            return analysis_result
            
        except json.JSONDecodeError as je:
            logger.error(f"Failed to parse JSON response: {je}")
            logger.debug(f"Raw response: {response[:500]}")
            # Fallback: try to extract sections manually
            return _extract_from_text(response, language)
        
    except ImportError as e:
        logger.error(f"emergentintegrations not installed: {e}")
        return get_default_analysis(language)
    except Exception as e:
        logger.error(f"Error generating AI analysis: {e}")
        return get_default_analysis(language)


def _extract_from_text(text: str, language: str) -> Dict:
    """Fallback: extract analysis sections from non-JSON text"""
    defaults = get_default_analysis(language)
    
    # Simple extraction based on common patterns
    result = {
        "generated_by": "AI",
        "model": "gpt-5.2"
    }
    
    sections = ['executive_summary', 'profitability_analysis', 'returns_analysis',
                'liquidity_analysis', 'solvency_analysis', 'recommendations']
    
    # If text contains useful content, use it for executive summary
    if len(text) > 100:
        # Take first meaningful paragraph
        paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 50]
        if paragraphs:
            result['executive_summary'] = paragraphs[0][:500]
            for i, section in enumerate(sections[1:], 1):
                if i < len(paragraphs):
                    result[section] = paragraphs[i][:500]
                else:
                    result[section] = defaults[section]
        else:
            return defaults
    else:
        return defaults
    
    # Fill any missing sections
    for section in sections:
        if section not in result:
            result[section] = defaults[section]
    
    return result


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
