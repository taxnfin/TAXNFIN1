"""
Endpoint admin: limpia bank_transactions duplicados de Alegra.
Un duplicado = dos docs con el mismo alegra_id o alegra_payment_id.
Conserva el de mayor score (conciliado + categoria_especifica).
"""
from fastapi import APIRouter, Depends, Request
from core.database import db
from core.auth import get_current_user, get_active_company_id
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/dedup", tags=["Admin"])

GENERIC_CATS = {'cobro_alegra', 'banco_alegra', 'pago_alegra', ''}

@router.post("/bank-transactions")
async def dedup_bank_transactions(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Encuentra y elimina bank_transactions duplicados por alegra_id/alegra_payment_id.
    Conserva el registro con mayor score (conciliado=True + categoría específica).
    """
    company_id = await get_active_company_id(request, current_user)

    # Traer todos los docs de la empresa
    docs = await db.bank_transactions.find(
        {'company_id': company_id, 'source': 'alegra'},
        {'_id': 1, 'id': 1, 'alegra_id': 1, 'alegra_payment_id': 1,
         'monto': 1, 'fecha': 1, 'fecha_movimiento': 1,
         'category_name': 1, 'conciliado': 1, 'tipo': 1}
    ).to_list(10000)

    # Agrupar por clave canónica
    groups: dict = {}
    for d in docs:
        alegra_id = (
            str(d.get('alegra_id') or '').strip() or
            str(d.get('alegra_payment_id') or '').strip()
        )
        fecha = str(d.get('fecha') or d.get('fecha_movimiento') or '')[:10]
        monto = round(float(d.get('monto', 0) or 0), 2)

        clave = f"alegra|{alegra_id}" if alegra_id else f"{fecha}|{monto}"
        if clave not in groups:
            groups[clave] = []
        groups[clave].append(d)

    # Identificar duplicados
    ids_to_delete = []
    for clave, group in groups.items():
        if len(group) < 2:
            continue
        # Puntuar cada doc
        def score(d):
            cat = (d.get('category_name') or '').lower().strip()
            return (2 if d.get('conciliado') else 0) + (1 if cat not in GENERIC_CATS else 0)
        group_sorted = sorted(group, key=score, reverse=True)
        # El primero (mejor score) se conserva, el resto se elimina
        for loser in group_sorted[1:]:
            ids_to_delete.append(loser['_id'])

    deleted = 0
    if ids_to_delete:
        result = await db.bank_transactions.delete_many({'_id': {'$in': ids_to_delete}})
        deleted = result.deleted_count
        logger.info(f"[dedup] company={company_id} eliminados={deleted} de {len(ids_to_delete)} duplicados")

    return {
        'status': 'ok',
        'grupos_analizados': len(groups),
        'grupos_con_duplicados': sum(1 for g in groups.values() if len(g) > 1),
        'docs_eliminados': deleted,
    }
