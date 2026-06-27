import asyncio, httpx, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = 'https://taxnfin1-production.up.railway.app'
TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNmYzZjkwOTYtMWI1Ny00NjE4LTgwYjYtZDk4NmUyODIzOWQ4IiwiY29tcGFueV9pZCI6Ijg5Y2RhNjFlLWM5YzMtNDQ3MC05OTJiLTQ4ZDMwMTVlNWNiZCIsInJvbGUiOiJjZm8iLCJleHAiOjE3ODMxOTM1NDJ9.wl5guU2auP6qZ36vgY4vV1Y0v2__1xPHUvdNunGXIEs'
CID = '89cda61e-c9c3-4470-992b-48d3015e5cbd'

async def main():
    h = {'Authorization': f'Bearer {TOKEN}', 'X-Company-ID': CID}
    async with httpx.AsyncClient(timeout=60) as c:

        # Ver detalle de ingresos y egresos de S1 (05-11 enero)
        r = await c.get(f'{BASE}/api/cashflow/weeks', headers=h)
        semanas = r.json()

        print("=== DETALLE INGRESOS/EGRESOS POR SEMANA (S1-S4) ===")
        for s in semanas[:4]:
            num = s.get('numero_semana','?')
            fi = s.get('fecha_inicio','')[:10]
            ff = s.get('fecha_fin','')[:10]
            print(f"\n--- S{num} {fi} → {ff} ---")
            print(f"  SI={s.get('saldo_inicial',0):,.2f}  Ing={s.get('total_ingresos',0):,.2f}  Egr={s.get('total_egresos',0):,.2f}  anclado={s.get('saldo_anclado',False)}")

            print("  TOP INGRESOS:")
            for item in (s.get('top_ingresos') or s.get('ingresos_detalle',[]))[:5]:
                cat = item.get('categoria','')
                concepto = item.get('concepto','')[:40]
                print(f"    +{item.get('monto',0):>12,.2f}  cat={cat}  {concepto}")

            print("  TOP EGRESOS:")
            for item in (s.get('top_egresos') or s.get('egresos_detalle',[]))[:5]:
                cat = item.get('categoria','')
                concepto = item.get('concepto','')[:40]
                print(f"    -{item.get('monto',0):>12,.2f}  cat={cat}  {concepto}")

asyncio.run(main())
