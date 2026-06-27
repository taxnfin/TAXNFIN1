import asyncio, httpx, json
from datetime import date, timedelta

BASE = 'https://taxnfin1-production.up.railway.app'
TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiNmYzZjkwOTYtMWI1Ny00NjE4LTgwYjYtZDk4NmUyODIzOWQ4IiwiY29tcGFueV9pZCI6Ijg5Y2RhNjFlLWM5YzMtNDQ3MC05OTJiLTQ4ZDMwMTVlNWNiZCIsInJvbGUiOiJjZm8iLCJleHAiOjE3ODMxOTM1NDJ9.wl5guU2auP6qZ36vgY4vV1Y0v2__1xPHUvdNunGXIEs'
CID = '89cda61e-c9c3-4470-992b-48d3015e5cbd'

async def main():
    h = {'Authorization': f'Bearer {TOKEN}', 'X-Company-ID': CID}

    # Exactamente lo que manda Dashboard.js en modo 13S:
    # dateFrom = hoy, luego resta 56 dias para fechaInicioReq
    today = date.today()
    date_to = (today + timedelta(days=91)).isoformat()
    fecha_inicio_req = (today - timedelta(days=56)).isoformat()

    print(f"today={today}  fecha_inicio_req={fecha_inicio_req}  date_to={date_to}")

    url = f'{BASE}/api/reports/dashboard-from-payments?moneda_vista=MXN&fecha_inicio={fecha_inicio_req}&fecha_fin={date_to}'
    print(f"\nURL: {url}\n")

    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.get(url, headers=h)
        if r.status_code != 200:
            print(f"ERROR {r.status_code}: {r.text[:500]}")
            return
        d = r.json()

        print(f"=== SALDO BASE ===")
        print(f"  saldo_bancos        = {d.get('saldo_bancos', 'N/A'):,.2f}")
        print(f"  saldo_actual        = {d.get('saldo_actual', 'N/A'):,.2f}")
        print(f"  fecha_saldo_bancos  = {d.get('fecha_saldo_bancos', 'N/A')}")

        print(f"\n=== CASH POOL ===")
        for moneda, info in d.get('cash_pool', {}).items():
            print(f"  {moneda}: total={info['total']:,.2f}  cuentas={info['cuentas']}")

        print(f"\n=== BANK ACCOUNTS DETAIL ===")
        for acc in d.get('bank_accounts', []):
            print(f"  {acc['nombre']} ({acc['moneda']}): saldo_inicial={acc['saldo_inicial']:,.2f}  saldo_final={acc['saldo_final']:,.2f}")

        print(f"\n=== SEMANAS S1-S5 (saldo_inicial) ===")
        weeks = d.get('weeks', [])
        for w in weeks[:5]:
            print(f"  {w.get('week_label','?')} {w.get('fecha_inicio','')}: saldo_inicial={w.get('saldo_inicial',0):,.2f}  saldo_final={w.get('saldo_final',0):,.2f}")

        # Tambien llama al summary con la misma fecha que usa el frontend
        summary_url = f'{BASE}/api/bank-accounts/summary?fecha={today.isoformat()}'
        r2 = await c.get(summary_url, headers=h)
        d2 = r2.json()
        print(f"\n=== SUMMARY fecha={today} ===")
        print(f"  total_mxn = {d2.get('total_mxn', 0):,.2f}")
        for banco, info in d2.get('por_banco', {}).items():
            for ct in info.get('cuentas', []):
                print(f"  {ct['nombre']} {ct['moneda']}: saldo={ct['saldo']:,.2f}  fecha_hist={ct.get('fecha_saldo','')}")

asyncio.run(main())
