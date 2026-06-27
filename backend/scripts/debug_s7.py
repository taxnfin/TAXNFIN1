import asyncio, httpx, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = 'https://taxnfin1-production.up.railway.app'
TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNmYzZjkwOTYtMWI1Ny00NjE4LTgwYjYtZDk4NmUyODIzOWQ4IiwiY29tcGFueV9pZCI6Ijg5Y2RhNjFlLWM5YzMtNDQ3MC05OTJiLTQ4ZDMwMTVlNWNiZCIsInJvbGUiOiJjZm8iLCJleHAiOjE3ODMxOTM1NDJ9.wl5guU2auP6qZ36vgY4vV1Y0v2__1xPHUvdNunGXIEs'
CID = '89cda61e-c9c3-4470-992b-48d3015e5cbd'

async def main():
    h = {'Authorization': f'Bearer {TOKEN}', 'X-Company-ID': CID}
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.get(f'{BASE}/api/cashflow/weeks', headers=h)
        semanas = r.json()

        # S6-S9 detalle completo
        print("=== S6-S9 DETALLE ===")
        for s in semanas[5:9]:
            num = s.get('numero_semana','?')
            fi  = s.get('fecha_inicio','')[:10]
            ff  = s.get('fecha_fin','')[:10]
            si  = s.get('saldo_inicial', 0)
            ing = s.get('total_ingresos', 0)
            egr = s.get('total_egresos', 0)
            anc = s.get('saldo_anclado', False)
            print(f"\nS{num} {fi}→{ff}  SI={si:,.2f}  Ing={ing:,.2f}  Egr={egr:,.2f}  anclado={anc}")
            print("  TOP INGRESOS:")
            for item in (s.get('top_ingresos') or [])[:5]:
                cat = item.get('categoria','')
                print(f"    +{item.get('monto',0):>12,.2f}  [{cat}]  {item.get('concepto','')[:50]}")
            print("  TOP EGRESOS:")
            for item in (s.get('top_egresos') or [])[:5]:
                cat = item.get('categoria','')
                print(f"    -{item.get('monto',0):>12,.2f}  [{cat}]  {item.get('concepto','')[:50]}")

asyncio.run(main())
