"""
Script para limpiar duplicados en db.bank_transactions para Ortech.
Mantiene el registro con categoria_name mas especifica (no cobro_alegra/banco_alegra).
"""
import asyncio, httpx, sys, json
sys.stdout.reconfigure(encoding='utf-8')

BASE  = 'https://taxnfin1-production.up.railway.app'
TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNmYzZjkwOTYtMWI1Ny00NjE4LTgwYjYtZDk4NmUyODIzOWQ4IiwiY29tcGFueV9pZCI6Ijg5Y2RhNjFlLWM5YzMtNDQ3MC05OTJiLTQ4ZDMwMTVlNWNiZCIsInJvbGUiOiJjZm8iLCJleHAiOjE3ODMxOTM1NDJ9.wl5guU2auP6qZ36vgY4vV1Y0v2__1xPHUvdNunGXIEs'
CID   = '89cda61e-c9c3-4470-992b-48d3015e5cbd'

# Categorias genericas que son duplicados de categorias especificas
GENERIC_CATS = {'cobro_alegra', 'banco_alegra', 'pago_alegra', ''}

async def main():
    h = {'Authorization': f'Bearer {TOKEN}', 'X-Company-ID': CID}
    async with httpx.AsyncClient(timeout=60) as c:

        # Obtener TODAS las bank_transactions via paginacion
        all_txns = []
        page = 0
        while True:
            r = await c.get(f'{BASE}/api/bank-transactions?limit=500&skip={page*500}', headers=h)
            data = r.json()
            batch = data if isinstance(data, list) else data.get('items', data.get('transactions', []))
            if not batch:
                break
            all_txns.extend(batch)
            if len(batch) < 500:
                break
            page += 1

        print(f"Total bank_transactions: {len(all_txns)}")

        # Agrupar por (fecha, monto, tipo, contacto) para encontrar duplicados
        from collections import defaultdict
        groups = defaultdict(list)
        for t in all_txns:
            fecha = str(t.get('fecha',''))[:10]
            monto = round(float(t.get('monto', 0) or 0), 2)
            tipo  = t.get('tipo', '')
            # Usar monto+tipo+contacto como clave (fecha puede variar por timezone)
            key = (fecha, monto, tipo, t.get('contacto','') or '')
            groups[key].append(t)

        # Identificar grupos con duplicados
        dup_groups = {k: v for k, v in groups.items() if len(v) > 1}
        print(f"Grupos con duplicados: {len(dup_groups)}")

        ids_a_eliminar = []
        for key, txns in dup_groups.items():
            # Ordenar: primero los que tienen categoria especifica (no generica)
            def score(t):
                cat = (t.get('category_name','') or '').lower()
                # Score alto = mas especifico = conservar
                if cat and cat not in GENERIC_CATS:
                    return 1
                return 0
            txns_sorted = sorted(txns, key=score, reverse=True)
            # Conservar el primero (mas especifico), eliminar el resto
            conservar = txns_sorted[0]
            eliminar  = txns_sorted[1:]
            for t in eliminar:
                ids_a_eliminar.append(t.get('id',''))
                cat_c = (conservar.get('category_name','') or '').encode('ascii','replace').decode()
                cat_e = (t.get('category_name','') or '').encode('ascii','replace').decode()
                contacto = (key[3] or '').encode('ascii','replace').decode()[:30]
                print(f"  DUP: {key[0]} ${key[1]:,.2f} {key[2]} [{contacto}]")
                print(f"       CONSERVA: [{cat_c}] id={conservar.get('id','')[:8]}")
                print(f"       ELIMINA:  [{cat_e}] id={t.get('id','')[:8]}")

        print(f"\nTotal a eliminar: {len(ids_a_eliminar)}")
        if not ids_a_eliminar:
            print("No hay duplicados — los datos estan limpios")
            return

        # Confirmar antes de eliminar
        print("\n¿Eliminar estos duplicados? Descomenta la linea de abajo y corre de nuevo.")
        # Descomentar para ejecutar:
        # r = await c.post(f'{BASE}/api/bank-transactions/bulk-delete',
        #                  json={'ids': ids_a_eliminar}, headers=h)
        # print(f"Resultado: {r.status_code} {r.text[:200]}")

asyncio.run(main())
