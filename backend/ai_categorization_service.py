"""
AI Categorization Service for TaxnFin Cashflow
Uses OpenAI GPT-5.2 via Emergent LLM Key to automatically categorize CFDIs
"""
import os
import json
import logging
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

async def categorize_cfdi_with_ai(
    cfdi_data: Dict[str, Any],
    available_categories: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Use AI to suggest a category for a CFDI based on its data.
    
    Args:
        cfdi_data: Dictionary containing CFDI information (emisor, receptor, monto, etc.)
        available_categories: List of available categories with their subcategories
    
    Returns:
        Dictionary with suggested category_id, subcategory_id, confidence, and reasoning
    """
    if not EMERGENT_LLM_KEY:
        return {
            "success": False,
            "error": "EMERGENT_LLM_KEY not configured",
            "category_id": None,
            "subcategory_id": None,
            "confidence": 0,
            "reasoning": "API key not configured"
        }
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        # Format categories for the prompt
        categories_text = ""
        for cat in available_categories:
            subcats = cat.get('subcategorias', [])
            subcat_names = [s['nombre'] for s in subcats] if subcats else ['Sin subcategorías']
            categories_text += f"\n- ID: {cat['id']} | Nombre: {cat['nombre']} | Tipo: {cat['tipo']} | Subcategorías: {', '.join(subcat_names)}"
        
        # Build the prompt
        system_message = """Eres un asistente experto en contabilidad y finanzas mexicanas. Tu tarea es analizar CFDIs (Comprobantes Fiscales Digitales por Internet) y sugerir la categoría más apropiada para clasificarlos.

Debes responder ÚNICAMENTE con un objeto JSON válido con la siguiente estructura:
{
    "category_id": "el ID de la categoría sugerida",
    "subcategory_id": "el ID de la subcategoría si aplica, o null",
    "confidence": número entre 0 y 100 indicando tu nivel de confianza,
    "reasoning": "explicación breve de por qué sugieres esta categoría"
}

Reglas importantes:
1. Si el CFDI es de tipo "ingreso" (la empresa emitió la factura), solo sugiere categorías de tipo "ingreso"
2. Si el CFDI es de tipo "egreso" (la empresa recibió la factura), solo sugiere categorías de tipo "egreso"
3. Analiza el RFC del emisor, el concepto y el monto para determinar la categoría
4. Si no hay una categoría apropiada, sugiere category_id: null con una explicación"""

        cfdi_info = f"""Analiza el siguiente CFDI y sugiere la categoría apropiada:

**Datos del CFDI:**
- UUID: {cfdi_data.get('uuid', 'N/A')}
- Tipo: {cfdi_data.get('tipo_cfdi', 'N/A')}
- Emisor RFC: {cfdi_data.get('emisor_rfc', 'N/A')}
- Emisor Nombre: {cfdi_data.get('emisor_nombre', 'N/A')}
- Receptor RFC: {cfdi_data.get('receptor_rfc', 'N/A')}
- Receptor Nombre: {cfdi_data.get('receptor_nombre', 'N/A')}
- Monto Total: ${cfdi_data.get('total', 0):,.2f} {cfdi_data.get('moneda', 'MXN')}
- Fecha Emisión: {cfdi_data.get('fecha_emision', 'N/A')}

**Categorías Disponibles:**
{categories_text}

Responde SOLO con el JSON, sin texto adicional."""

        # Initialize chat with GPT-5.2
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"cfdi-categorization-{cfdi_data.get('uuid', 'unknown')}",
            system_message=system_message
        ).with_model("openai", "gpt-5.2")
        
        user_message = UserMessage(text=cfdi_info)
        
        response = await chat.send_message(user_message)
        
        # Parse the JSON response
        try:
            # Clean the response (remove markdown code blocks if present)
            clean_response = response.strip()
            if clean_response.startswith('```'):
                clean_response = clean_response.split('\n', 1)[1]
            if clean_response.endswith('```'):
                clean_response = clean_response.rsplit('```', 1)[0]
            clean_response = clean_response.strip()
            
            result = json.loads(clean_response)
            
            return {
                "success": True,
                "category_id": result.get('category_id'),
                "subcategory_id": result.get('subcategory_id'),
                "confidence": result.get('confidence', 0),
                "reasoning": result.get('reasoning', ''),
                "raw_response": response
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {response}")
            return {
                "success": False,
                "error": f"Invalid JSON response: {str(e)}",
                "category_id": None,
                "subcategory_id": None,
                "confidence": 0,
                "reasoning": response,
                "raw_response": response
            }
            
    except Exception as e:
        logger.error(f"AI categorization error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "category_id": None,
            "subcategory_id": None,
            "confidence": 0,
            "reasoning": f"Error: {str(e)}"
        }


async def batch_categorize_cfdis(
    cfdis: List[Dict[str, Any]],
    available_categories: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Categorize multiple CFDIs in batch.
    
    Returns a list of results, one for each CFDI.
    """
    results = []
    for cfdi in cfdis:
        result = await categorize_cfdi_with_ai(cfdi, available_categories)
        result['cfdi_id'] = cfdi.get('id')
        result['cfdi_uuid'] = cfdi.get('uuid')
        results.append(result)
    return results
