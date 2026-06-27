import asyncio, httpx, json

BASE = 'https://taxnfin1-production.up.railway.app'
TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNmYzZjkwOTYtMWI1Ny00NjE4LTgwYjYtZDk4NmUyODIzOWQ4IiwiY29tcGFueV9pZCI6Ijg5Y2RhNjFlLWM5YzMtNDQ3MC05OTJiLTQ4ZDMwMTVlNWNiZCIsInJvbGUiOiJjZm8iLCJleHAiOjE3ODMxOTM1NDJ9.wl5guU2auP6qZ36vgY4vV1Y0v2__1xPHUvdNunGXIEs'
CID = '89cda61e-c9c3-4470-992b-48d3015e5cbd'

async def main():
    h = {'Authorization': f'Bearer {TOKEN}', 'X-Company-ID': CID}
    async with httpx.AsyncClient(timeout=30) as c:

        # 1. Todas las cuentas
        r = await c.get(f'{BASE}/api/bank-accounts', headers=h)
        cuentas = r.json()
        print('=== CUENTAS BANCARIAS ===')
        for a in cuentas:
            aid = a.get('id','')[:8]
            nombre = a.get('nombre','')
            banco = a.get('banco','')
            moneda = a.get('moneda','')
            saldo = a.get('saldo_inicial', 0)
            activo = a.get('activo', '?')
            fecha = a.get('fecha_saldo','')
            print(f'  {aid} | {nombre} | {banco} | {moneda} | saldo={saldo:,.2f} | activo={activo} | fecha={fecha}')

        # 2. Summary sin fecha
        r2 = await c.get(f'{BASE}/api/bank-accounts/summary', headers=h)
        d2 = r2.json()
        print(f'\n=== SUMMARY sin fecha ===')
        print(f'  total_mxn = {d2.get("total_mxn",0):,.2f}')
        print(f'  por_moneda = {json.dumps(d2.get("por_moneda",{}), indent=4)}')

        # 3. Summary enero
        r3 = await c.get(f'{BASE}/api/bank-accounts/summary?fecha=2026-01-31', headers=h)
        d3 = r3.json()
        print(f'\n=== SUMMARY fecha=2026-01-31 ===')
        print(f'  total_mxn = {d3.get("total_mxn",0):,.2f}')
        for banco, info in d3.get('por_banco',{}).items():
            print(f'  {banco}: {info["saldo_mxn"]:,.2f}')
            for ct in info.get('cuentas',[]):
                print(f'    {ct["nombre"]} {ct["moneda"]} saldo={ct["saldo"]:,.2f} tc={ct.get("tipo_cambio_usado",1):.4f} => {ct["saldo_mxn"]:,.2f} MXN | fecha_hist={ct.get("fecha_saldo","")}')

        # 4. Summary mayo
        r4 = await c.get(f'{BASE}/api/bank-accounts/summary?fecha=2026-05-31', headers=h)
        d4 = r4.json()
        print(f'\n=== SUMMARY fecha=2026-05-31 ===')
        print(f'  total_mxn = {d4.get("total_mxn",0):,.2f}')
        for banco, info in d4.get('por_banco',{}).items():
            print(f'  {banco}: {info["saldo_mxn"]:,.2f}')
            for ct in info.get('cuentas',[]):
                print(f'    {ct["nombre"]} {ct["moneda"]} saldo={ct["saldo"]:,.2f} tc={ct.get("tipo_cambio_usado",1):.4f} => {ct["saldo_mxn"]:,.2f} MXN | fecha_hist={ct.get("fecha_saldo","")}')

asyncio.run(main())
