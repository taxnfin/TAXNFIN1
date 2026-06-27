import asyncio, httpx, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = 'https://taxnfin1-production.up.railway.app'
TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNmYzZjkwOTYtMWI1Ny00NjE4LTgwYjYtZDk4NmUyODIzOWQ4IiwiY29tcGFueV9pZCI6Ijg5Y2RhNjFlLWM5YzMtNDQ3MC05OTJiLTQ4ZDMwMTVlNWNiZCIsInJvbGUiOiJjZm8iLCJleHAiOjE3ODMxOTM1NDJ9.wl5guU2auP6qZ36vgY4vV1Y0v2__1xPHUvdNunGXIEs'
CID = '89cda61e-c9c3-4470-992b-48d3015e5cbd'

TRASPASO_KW = ['operacion cambios', 'operacion cambio', 'cambio de divisa',
               'traspaso', 'retiro por operacion', 'deposito por operacion']

async def main():
    h = {'Authorization': f'Bearer {TOKEN}', 'X-Company-ID': CID}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f'{BASE}/api/bank-transactions?limit=500', headers=h)
        txns = r.json() if isinstance(r.json(), list) else r.json().get('transactions', r.json().get('items', []))
        print(f"Total: {len(txns)}")

        from collections import Counter
        tipos = Counter()
        cats = Counter()
        traspasos, reales = 0, 0
        monto_traspasos, monto_reales = 0.0, 0.0

        for t in txns:
            tipo = t.get('tipo','')
            tipos[tipo] += 1
            cat = t.get('category_name', t.get('categoria','sin_cat')) or 'sin_cat'
            # quitar emojis para evitar encoding error
            cat_safe = cat.encode('ascii','replace').decode()
            cats[cat_safe] += 1
            desc = (t.get('descripcion','') or t.get('concepto','') or t.get('contacto','')).lower()
            monto = float(t.get('monto', 0) or 0)
            if any(k in desc for k in TRASPASO_KW):
                traspasos += 1
                monto_traspasos += monto
            else:
                reales += 1
                monto_reales += monto

        print(f"Tipos: {dict(tipos)}")
        print(f"Top cats: {cats.most_common(10)}")
        print(f"Traspasos por keyword: {traspasos}  monto=${monto_traspasos:,.2f}")
        print(f"Reales:                {reales}  monto=${monto_reales:,.2f}")

        # 5 ejemplos traspasos
        print("\n--- 5 ejemplos traspasos ---")
        n = 0
        for t in txns:
            desc = (t.get('descripcion','') or t.get('concepto','') or t.get('contacto','')).lower()
            if any(k in desc for k in TRASPASO_KW):
                desc_raw = t.get('descripcion','') or t.get('concepto','') or t.get('contacto','')
                print(f"  tipo={t.get('tipo')} monto={t.get('monto')} cat={str(t.get('category_name','')).encode('ascii','replace').decode()} desc={desc_raw[:60]}")
                n += 1
                if n >= 5: break

        # 5 ejemplos reales (egresos grandes)
        print("\n--- 5 egresos mayores (no traspaso) ---")
        egresos = [(float(t.get('monto',0) or 0), t) for t in txns
                   if t.get('tipo') in ('egreso','retiro')
                   and not any(k in (t.get('descripcion','') or t.get('concepto','') or t.get('contacto','')).lower() for k in TRASPASO_KW)]
        for monto, t in sorted(egresos, reverse=True)[:5]:
            desc_raw = t.get('descripcion','') or t.get('concepto','') or t.get('contacto','') or ''
            print(f"  monto=${monto:,.2f} cat={str(t.get('category_name','')).encode('ascii','replace').decode()} desc={desc_raw[:60]}")

asyncio.run(main())
