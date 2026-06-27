import asyncio, httpx, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = 'https://taxnfin1-production.up.railway.app'
TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNmYzZjkwOTYtMWI1Ny00NjE4LTgwYjYtZDk4NmUyODIzOWQ4IiwiY29tcGFueV9pZCI6Ijg5Y2RhNjFlLWM5YzMtNDQ3MC05OTJiLTQ4ZDMwMTVlNWNiZCIsInJvbGUiOiJjZm8iLCJleHAiOjE3ODMxOTM1NDJ9.wl5guU2auP6qZ36vgY4vV1Y0v2__1xPHUvdNunGXIEs'
CID = '89cda61e-c9c3-4470-992b-48d3015e5cbd'

async def main():
    h = {'Authorization': f'Bearer {TOKEN}', 'X-Company-ID': CID}
    async with httpx.AsyncClient(timeout=60) as c:

        # 1. Anclas en MongoDB - lo que realmente tiene bank_account_history
        print("=== ANCLAS EN bank_account_history ===")
        r = await c.get(f'{BASE}/api/bank-accounts', headers=h)
        cuentas = r.json()
        for acc in cuentas:
            rh = await c.get(f'{BASE}/api/bank-accounts/{acc["id"]}/history', headers=h)
            hist = rh.json().get('history', [])
            print(f"\n{acc['nombre']} ({acc['moneda']}):")
            for h2 in hist:
                print(f"  {h2['fecha']}  saldo={h2['saldo']:>12,.2f}")

        # 2. Summary por fecha - lo que devuelve el endpoint para cada mes
        print("\n=== SUMMARY POR MES (saldo bancario consolidado MXN) ===")
        fechas = ['2025-12-31','2026-01-01','2026-01-31','2026-02-28','2026-03-31','2026-04-30','2026-05-31']
        for f in fechas:
            r2 = await c.get(f'{BASE}/api/bank-accounts/summary?fecha={f}', headers=h)
            d = r2.json()
            total = d.get('total_mxn', 0)
            por_banco = d.get('por_banco', {})
            detalles = []
            for banco, info in por_banco.items():
                for ct in info.get('cuentas', []):
                    if ct['saldo'] != 0:
                        detalles.append(f"{ct['nombre']}={ct['saldo']:,.2f}{ct['moneda']}@{ct.get('tipo_cambio_usado',1):.4f}")
            print(f"  {f}  total_mxn={total:>12,.2f}  [{', '.join(detalles)}]")

        # 3. CashFlow semanas S1-S8 - saldo_inicial y ancla
        print("\n=== CASHFLOW SEMANAS S1-S8 ===")
        r3 = await c.get(f'{BASE}/api/cashflow/weeks', headers=h)
        if r3.status_code == 200:
            semanas = r3.json()
            for s in semanas[:8]:
                num = s.get('numero_semana', s.get('label','?'))
                fi = s.get('fecha_inicio','')[:10]
                ff = s.get('fecha_fin','')[:10]
                si = s.get('saldo_inicial', 0)
                sf = s.get('saldo_final', s.get('saldo_inicial',0) + s.get('flujo_neto',0))
                anclado = s.get('saldo_anclado', False)
                ing = s.get('total_ingresos', 0)
                egr = s.get('total_egresos', 0)
                print(f"  S{num} {fi}→{ff}  SI={si:>12,.2f}  Ing={ing:>10,.2f}  Egr={egr:>10,.2f}  SF={sf:>12,.2f}  anclado={anclado}")
        else:
            print(f"  ERROR {r3.status_code}: {r3.text[:200]}")

asyncio.run(main())
