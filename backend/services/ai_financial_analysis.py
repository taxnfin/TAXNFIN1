"""
AI Financial Analysis Service
Generates professional financial commentary and KPI explanations.
NOTE: AI integration disabled — returns default analysis templates.
To enable AI, configure an LLM API key and implement the generate call.
"""
import logging
from typing import Dict

logger = logging.getLogger(__name__)


async def generate_financial_analysis(
    company_name: str,
    period: str,
    income_statement: Dict,
    balance_sheet: Dict,
    metrics: Dict,
    language: str = 'es',
    **kwargs
) -> Dict:
    """Generate financial analysis. Returns default analysis (AI disabled)."""
    logger.info(f"Financial analysis for {company_name} - {period} (AI disabled, returning defaults)")
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
            "income_flow_analysis": "El flujo del estado de resultados muestra cómo los ingresos se transforman en utilidad neta. Es importante analizar la proporción de costo de ventas y gastos operativos para identificar oportunidades de mejora en márgenes.",
            "recommendations": "Se recomienda realizar un análisis más detallado de las tendencias históricas y comparar con benchmarks de la industria para obtener conclusiones más específicas.",
            "trends_analysis": "Las tendencias históricas muestran la evolución del desempeño financiero. Se recomienda analizar los factores que explican las variaciones significativas entre períodos.",
            "generated_by": "Default",
            "model": "N/A"
        },
        'en': {
            "executive_summary": "The financial data for the period shows the company's operational performance. It is recommended to review key indicators to make informed decisions.",
            "profitability_analysis": "Profitability margins reflect operational efficiency. It is suggested to compare with previous periods and industry averages.",
            "returns_analysis": "Return indicators show the ability to generate value on invested capital. It is important to monitor their evolution.",
            "liquidity_analysis": "Liquidity indicators show the company's ability to meet its short-term obligations.",
            "solvency_analysis": "The capital structure and level of indebtedness determine the company's financial risk.",
            "income_flow_analysis": "The income statement flow shows how revenue is converted to net profit. It is important to analyze cost of sales and operating expenses proportions.",
            "recommendations": "It is recommended to perform a more detailed analysis of historical trends and compare with industry benchmarks.",
            "trends_analysis": "Historical trends show the evolution of financial performance. It is recommended to analyze factors that explain significant variations between periods.",
            "generated_by": "Default",
            "model": "N/A"
        },
        'pt': {
            "executive_summary": "Os dados financeiros do período mostram o desempenho operacional da empresa. Recomenda-se revisar os indicadores-chave para tomar decisões informadas.",
            "profitability_analysis": "As margens de rentabilidade refletem a eficiência operacional. Sugere-se comparar com períodos anteriores e com a média do setor.",
            "returns_analysis": "Os indicadores de retorno mostram a capacidade de gerar valor sobre o capital investido. É importante monitorar sua evolução.",
            "liquidity_analysis": "Os indicadores de liquidez mostram a capacidade da empresa de cumprir suas obrigações de curto prazo.",
            "solvency_analysis": "A estrutura de capital e o nível de endividamento determinam o risco financeiro da empresa.",
            "income_flow_analysis": "O fluxo da demonstração de resultados mostra como a receita é convertida em lucro líquido. É importante analisar as proporções de custo de vendas e despesas operacionais.",
            "recommendations": "Recomenda-se realizar uma análise mais detalhada das tendências históricas e comparar com benchmarks do setor.",
            "trends_analysis": "As tendências históricas mostram a evolução do desempenho financeiro. Recomenda-se analisar os fatores que explicam variações significativas entre períodos.",
            "generated_by": "Default",
            "model": "N/A"
        }
    }
    return defaults.get(language, defaults['es'])
