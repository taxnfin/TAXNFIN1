import asyncio, httpx, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = 'https://taxnfin1-production.up.railway.app'
TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNmYzZjkwOTYtMWI1Ny00NjE4LTgwYjYtZDk4NmUyODIzOWQ4IiwiY29tcGFueV9pZCI6Ijg5Y2RhNjFlLWM5YzMtNDQ3MC05OTJiLTQ4ZDMwMTVlNWNiZCIsInJvbGUiOiJjZm8iLCJleHAiOjE3ODMxOTM1NDJ9.wl5guU2auP6qZ36vgY4vV1Y0v2__1xPHUvdNunGXIEs'
CID = '89cda61e-c9c3-4470-992b-48d3015e5cbd'

async def main():
    h = {'Authorization': f'Bearer {TOKEN}', 'X-Company-ID': CID}
    async with httpx.AsyncClient(timeout=30) as c:

        # Ver las primeras semanas raw de cashflow_weeks en DB
        r = await c.get(f'{BASE}/api/cashflow/weeks-raw', headers=h)
        if r.status_code == 200:
            semanas = r.json()
            print("=== cashflow_weeks RAW (primeras 3) ===")
            for s in semanas[:3]:
                print(f"  S{s.get('numero_semana')} fi={s.get('fecha_inicio','')[:10]} ff={s.get('fecha_fin','')[:10]} saldo_inicial={s.get('saldo_inicial',0):,.2f}")
        else:
            print(f"weeks-raw no existe ({r.status_code}), probando /cashflow/projections...")

        # Ver el endpoint que usa CashflowProjections.js
        r2 = await c.get(f'{BASE}/api/cashflow/projections', headers=h)
        if r2.status_code == 200:
            data = r2.json()
            semanas2 = data.get('weeks', data) if isinstance(data, dict) else data
            print("\n=== /cashflow/projections - primeras 3 semanas ===")
            for s in semanas2[:3]:
                print(f"  S{s.get('numero_semana',s.get('label','?'))} fi={str(s.get('fecha_inicio',''))[:10]} saldo_inicial={s.get('saldo_inicial',0):,.2f}")
        else:
            print(f"\n/cashflow/projections: {r2.status_code}")

        # Ver qué endpoint usa realmente el frontend
        # Buscar en cashflow route
        r3 = await c.get(f'{BASE}/api/cashflow/semanas', headers=h)
        print(f"\n/cashflow/semanas: {r3.status_code}")
        if r3.status_code == 200:
            data3 = r3.json()
            semanas3 = data3.get('weeks', data3) if isinstance(data3, dict) else data3
            for s in semanas3[:3]:
                print(f"  S{s.get('numero_semana',s.get('label','?'))} fi={str(s.get('fecha_inicio',''))[:10]} saldo_inicial={s.get('saldo_inicial',0):,.2f}")

asyncio.run(main())
