"""
AI Categorization Service for TaxnFin Cashflow
NOTE: AI integration disabled — returns no-suggestion response.
To enable, configure an LLM API key and implement the categorization call.
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


async def categorize_cfdi_with_ai(
    cfdi_data: Dict[str, Any],
    available_categories: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Suggest a category for a CFDI. AI disabled — returns no suggestion.
    """
    return {
        "success": False,
        "error": "AI categorization disabled — no LLM API key configured",
        "category_id": None,
        "subcategory_id": None,
        "confidence": 0,
        "reasoning": "AI categorization is currently disabled"
    }


async def batch_categorize_cfdis(
    cfdis: List[Dict[str, Any]],
    available_categories: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Categorize multiple CFDIs in batch."""
    results = []
    for cfdi in cfdis:
        result = await categorize_cfdi_with_ai(cfdi, available_categories)
        result['cfdi_id'] = cfdi.get('id')
        result['cfdi_uuid'] = cfdi.get('uuid')
        results.append(result)
    return results
