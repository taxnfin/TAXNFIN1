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

        print("=== SEMANAS S1-S8: fechas exactas y anclas ===")
        print(f"{'S#':<4} {'fecha_inicio':<14} {'fecha_fin':<14} {'SI':>12} {'Ing':>12} {'Egr':>12} {'SF':>12} {'anclado'}")
        for s in semanas[:8]:
            num = s.get('numero_semana','?')
            fi  = s.get('fecha_inicio','')[:10]
            ff  = s.get('fecha_fin','')[:10]
            si  = s.get('saldo_inicial', 0)
            ing = s.get('total_ingresos', 0)
            egr = s.get('total_egresos', 0)
            sf  = si + ing - egr
            anc = s.get('saldo_anclado', False)
            print(f"S{num:<3} {fi:<14} {ff:<14} {si:>12,.2f} {ing:>12,.2f} {egr:>12,.2f} {sf:>12,.2f} {'✅' if anc else '  '}")

        print("\n=== ANCLAS DISPONIBLES ===")
        # Verificar qué anclas existen y en qué semana caen
        anclas = {
            '2025-12-31': 305849.85,
            '2026-01-01': 305849.85,
            '2026-01-31': 387509.49,
            '2026-02-28': 665865.34,
            '2026-03-31': 412879.54,
            '2026-04-30': 182554.04,
            '2026-05-31': 240721.98,
        }
        for fecha, mxn in anclas.items():
            # buscar en qué semana cae
            semana_que_la_contiene = None
            for s in semanas:
                fi = s.get('fecha_inicio','')[:10]
                ff = s.get('fecha_fin','')[:10]
                if fi <= fecha <= ff:
                    semana_que_la_contiene = f"S{s.get('numero_semana','?')} ({fi}→{ff})"
                    break
            print(f"  {fecha}  ${mxn:>12,.2f}  → {semana_que_la_contiene or 'SIN SEMANA (entre semanas o antes de S1)'}")

asyncio.run(main())
