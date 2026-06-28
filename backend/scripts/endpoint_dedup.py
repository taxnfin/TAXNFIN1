"""
Endpoint temporal de limpieza de duplicados en bank_transactions.
Solo accesible por admin. Agregar a bank_accounts.py o cashflow.py temporalmente.
"""

@router.post("/bank-transactions/deduplicate")
async def deduplicate_bank_transactions(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    dry_run: bool = Query(True, description="Si True, solo reporta — no elimina"),
):
    """
    Elimina duplicados en bank_transactions detectados por (fecha, monto, tipo, contacto).
    Conserva el registro con category_name más específico.
    Solo accesible por admin.
    """
    if current_user.get('role') not in ['admin', 'cfo']:
        raise HTTPException(status_code=403, detail="Solo admin/cfo")

    company_id = await get_active_company_id(request, current_user)
    GENERIC_CATS = {'cobro_alegra', 'banco_alegra', 'pago_alegra', '', None}

    # Leer todas las transacciones de la empresa
    txns = await db.bank_transactions.find(
        {'company_id': company_id},
        {'_id': 0, 'id': 1, 'fecha': 1, 'monto': 1, 'tipo': 1,
         'contacto': 1, 'category_name': 1}
    ).to_list(50000)

    from collections import defaultdict
    groups = defaultdict(list)
    for t in txns:
        fecha = str(t.get('fecha', ''))[:10]
        monto = round(float(t.get('monto', 0) or 0), 2)
        tipo  = t.get('tipo', '') or ''
        contacto = t.get('contacto', '') or ''
        key = (fecha, monto, tipo, contacto)
        groups[key].append(t)

    ids_to_delete = []
    report = []

    for key, group in groups.items():
        if len(group) <= 1:
            continue

        def score(t):
            cat = (t.get('category_name') or '').lower().strip()
            return 0 if cat in GENERIC_CATS else 1

        sorted_group = sorted(group, key=score, reverse=True)
        keep = sorted_group[0]
        to_delete = [t['id'] for t in sorted_group[1:] if t['id'] != keep['id']]
        ids_to_delete.extend(to_delete)

        report.append({
            'key': f"{key[0]} ${key[1]:,.2f} {key[2]} {key[3][:30]}",
            'conserva': keep['id'],
            'elimina': to_delete,
        })

    if not dry_run and ids_to_delete:
        result = await db.bank_transactions.delete_many(
            {'company_id': company_id, 'id': {'$in': ids_to_delete}}
        )
        deleted = result.deleted_count
    else:
        deleted = 0

    return {
        'dry_run': dry_run,
        'grupos_duplicados': len(report),
        'ids_a_eliminar': len(ids_to_delete),
        'eliminados': deleted,
        'sample': report[:10],
    }
