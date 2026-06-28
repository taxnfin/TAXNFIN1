import asyncio, httpx, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = 'https://taxnfin1-production.up.railway.app'
TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNmYzZjkwOTYtMWI1Ny00NjE4LTgwYjYtZDk4NmUyODIzOWQ4IiwiY29tcGFueV9pZCI6Ijg5Y2RhNjFlLWM5YzMtNDQ3MC05OTJiLTQ4ZDMwMTVlNWNiZCIsInJvbGUiOiJjZm8iLCJleHAiOjE3ODMxOTM1NDJ9.wl5guU2auP6qZ36vgY4vV1Y0v2__1xPHUvdNunGXIEs'
CID = '89cda61e-c9c3-4470-992b-48d3015e5cbd'

async def main():
    h = {'Authorization': f'Bearer {TOKEN}', 'X-Company-ID': CID}
    async with httpx.AsyncClient(timeout=60) as c:
        # 1. Ver cuantas semanas devuelve dashboard-from-payments
        r = await c.get(f'{BASE}/api/reports/dashboard-from-payments?moneda_vista=MXN', headers=h)
        d = r.json()
        weeks = d.get('weeks', [])
        print(f"Total semanas: {len(weeks)}")
        print(f"burn_rate: {d.get('burn_rate',0):,.2f}")
        print(f"runway_weeks: {d.get('runway_weeks')}")
        print(f"saldo_proyectado: {d.get('saldo_proyectado',0):,.2f}")
        print()
        print(f"{'Sem':<5} {'fecha_ini':<12} {'is_past':<8} {'is_current':<11} {'SI':>12} {'Ing':>12} {'Egr':>12} {'SF':>12}")
        for w in weeks:
            print(f"{w.get('week_label','?'):<5} {w.get('fecha_inicio','')[:10]:<12} {str(w.get('is_past','')):<8} {str(w.get('is_current','')):<11} {w.get('saldo_inicial',0):>12,.0f} {w.get('ingresos',0):>12,.0f} {w.get('egresos',0):>12,.0f} {w.get('saldo_final',0):>12,.0f}")

asyncio.run(main())
