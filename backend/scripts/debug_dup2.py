import asyncio, httpx, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE  = 'https://taxnfin1-production.up.railway.app'
TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNmYzZjkwOTYtMWI1Ny00NjE4LTgwYjYtZDk4NmUyODIzOWQ4IiwiY29tcGFueV9pZCI6Ijg5Y2RhNjFlLWM5YzMtNDQ3MC05OTJiLTQ4ZDMwMTVlNWNiZCIsInJvbGUiOiJjZm8iLCJleHAiOjE3ODMxOTM1NDJ9.wl5guU2auP6qZ36vgY4vV1Y0v2__1xPHUvdNunGXIEs'
CID   = '89cda61e-c9c3-4470-992b-48d3015e5cbd'

async def main():
    h = {'Authorization': f'Bearer {TOKEN}', 'X-Company-ID': CID}
    async with httpx.AsyncClient(timeout=30) as c:

        # Obtener bank_transactions de febrero para ver duplicados
        r = await c.get(f'{BASE}/api/bank-transactions?limit=500', headers=h)
        txns = r.json() if isinstance(r.json(), list) else r.json().get('items', [])

        # Filtrar febrero
        feb = [t for t in txns if str(t.get('fecha',''))[:7] == '2026-02']
        print(f"Total bank_transactions: {len(txns)}")
        print(f"De febrero 2026: {len(feb)}")

        # Top depositos febrero
        dep_feb = [t for t in feb if t.get('tipo') in ('deposito','ingreso')]
        dep_feb.sort(key=lambda x: x.get('monto',0), reverse=True)
        print(f"\n=== TOP 10 DEPOSITOS FEBRERO ===")
        for t in dep_feb[:10]:
            cat = (t.get('category_name','') or '').encode('ascii','replace').decode()
            desc = (t.get('contacto','') or t.get('descripcion','')).encode('ascii','replace').decode()
            print(f"  {t.get('fecha','')[:10]} ${t.get('monto',0):>12,.2f} [{cat}] {desc[:40]}")

        # Buscar duplicados exactos (mismo fecha+monto+contacto)
        from collections import Counter
        keys = [(t.get('fecha','')[:10], t.get('monto',0), t.get('contacto','')) for t in txns]
        dups = [(k,v) for k,v in Counter(keys).items() if v > 1]
        dups.sort(key=lambda x: x[1], reverse=True)
        print(f"\n=== DUPLICADOS EXACTOS (fecha+monto+contacto) ===")
        print(f"Grupos duplicados: {len(dups)}")
        for k, cnt in dups[:10]:
            print(f"  count={cnt} fecha={k[0]} monto=${k[1]:,.2f} contacto={str(k[2]).encode('ascii','replace').decode()[:30]}")

asyncio.run(main())
