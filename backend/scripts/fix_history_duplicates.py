"""
Diagnóstico y limpieza de bank_account_history - elimina duplicados por fecha.
Uso: python backend/scripts/fix_history_duplicates.py <TOKEN_JWT>
"""
import asyncio
import httpx
import sys

BASE_URL = "https://taxnfin1-production.up.railway.app"

async def main(token: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        # Obtener company_id
        r = await client.get(f"{BASE_URL}/api/auth/me", headers=headers)
        me = r.json()
        company_id = me.get('company_ids', [''])[0]
        h = {**headers, "X-Company-ID": company_id}

        # Ver historial de cada cuenta
        for acct_id, nombre in [
            ("908fd8ae-657f-4b24-8138-46a606be60c2", "BAJIO MXN"),
            ("9090c0a2-ce48-4fe1-894b-405af275cb50", "BAJIO USD"),
        ]:
            r2 = await client.get(f"{BASE_URL}/api/bank-accounts/{acct_id}/history", headers=h)
            if r2.status_code == 200:
                hist = r2.json().get('history', [])
                print(f"\n{nombre} ({len(hist)} entradas):")
                for entry in hist:
                    print(f"  {entry.get('fecha')}  ${entry.get('saldo'):>12,.2f}  id:{entry.get('id','')[:8]}")
            else:
                print(f"\n{nombre}: ERROR {r2.status_code}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python backend/scripts/fix_history_duplicates.py <TOKEN>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
