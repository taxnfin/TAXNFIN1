import asyncio, httpx, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE  = 'https://taxnfin1-production.up.railway.app'
TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNmYzZjkwOTYtMWI1Ny00NjE4LTgwYjYtZDk4NmUyODIzOWQ4IiwiY29tcGFueV9pZCI6Ijg5Y2RhNjFlLWM5YzMtNDQ3MC05OTJiLTQ4ZDMwMTVlNWNiZCIsInJvbGUiOiJjZm8iLCJleHAiOjE3ODMxOTM1NDJ9.wl5guU2auP6qZ36vgY4vV1Y0v2__1xPHUvdNunGXIEs'
CID   = '89cda61e-c9c3-4470-992b-48d3015e5cbd'

async def main():
    h = {'Authorization': f'Bearer {TOKEN}', 'X-Company-ID': CID}
    async with httpx.AsyncClient(timeout=30) as c:

        # Llamar al cashflow/weeks directo para ver el detalle de S6 (Feb 09-16)
        r = await c.get(f'{BASE}/api/cashflow/weeks', headers=h)
        semanas = r.json()

        s6 = next((s for s in semanas if s.get('numero_semana') == 6), None)
        if not s6:
            # buscar por fecha
            s6 = next((s for s in semanas if '2026-02-09' in str(s.get('fecha_inicio',''))), None)

        if s6:
            print(f"S6: {s6.get('fecha_inicio','')[:10]} → {s6.get('fecha_fin','')[:10]}")
            print(f"  SI={s6.get('saldo_inicial',0):,.2f}  Ing={s6.get('total_ingresos',0):,.2f}  Egr={s6.get('total_egresos',0):,.2f}")
            print(f"\n  TOP INGRESOS:")
            for item in (s6.get('top_ingresos') or s6.get('ingresos_detalle',[]))[:10]:
                cat = str(item.get('categoria','')).encode('ascii','replace').decode()
                desc = str(item.get('concepto','') or item.get('nombre','')).encode('ascii','replace').decode()
                print(f"    +{item.get('monto',0):>12,.2f}  [{cat}]  {desc[:50]}")
            print(f"\n  TOP EGRESOS:")
            for item in (s6.get('top_egresos') or s6.get('egresos_detalle',[]))[:10]:
                cat = str(item.get('categoria','')).encode('ascii','replace').decode()
                desc = str(item.get('concepto','') or item.get('nombre','')).encode('ascii','replace').decode()
                print(f"    -{item.get('monto',0):>12,.2f}  [{cat}]  {desc[:50]}")
        else:
            print("S6 no encontrada")
            print(f"Semanas disponibles: {[s.get('numero_semana') for s in semanas[:15]]}")

asyncio.run(main())
