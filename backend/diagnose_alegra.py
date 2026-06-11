"""
Diagnóstico de API Alegra — ejecutar con:
  MONGO_URL="mongodb+srv://..." DB_NAME="taxnfin_cashflow" python diagnose_alegra.py
O pasando credenciales directas:
  ALEGRA_EMAIL="tu@email.com" ALEGRA_TOKEN="token" python diagnose_alegra.py
"""
import asyncio, base64, json, os, sys
from datetime import datetime

try:
    import httpx
except ImportError:
    print("Instalando httpx..."); os.system("pip install httpx -q")
    import httpx

COMPANY_ID = "381aada7-9180-41fe-b1f8-9b15b4630414"
BASE_URL   = "https://api.alegra.com/api/v1"

async def get_credentials():
    email = os.environ.get("ALEGRA_EMAIL", "")
    token = os.environ.get("ALEGRA_TOKEN", "")
    if email and token:
        print(f"[Creds] Usando variables de entorno: {email}")
        return email, token

    mongo_url = os.environ.get("MONGO_URL", "")
    db_name   = os.environ.get("DB_NAME", "taxnfin_cashflow")
    if not mongo_url:
        print("ERROR: define MONGO_URL o ALEGRA_EMAIL+ALEGRA_TOKEN")
        sys.exit(1)

    try:
        import motor.motor_asyncio
        client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
        db = client[db_name]
        company = await db.companies.find_one(
            {"id": COMPANY_ID}, {"_id": 0, "nombre": 1, "alegra_email": 1, "alegra_token": 1}
        )
        client.close()
        if not company:
            print(f"ERROR: empresa {COMPANY_ID} no encontrada en MongoDB")
            sys.exit(1)
        print(f"[Empresa] {company.get('nombre')} — email: {company.get('alegra_email')}")
        return company["alegra_email"], company["alegra_token"]
    except Exception as e:
        print(f"ERROR MongoDB: {e}")
        sys.exit(1)


async def alegra_get(client, endpoint, email, token, params=None):
    creds   = base64.b64encode(f"{email}:{token}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Accept": "application/json"}
    url     = f"{BASE_URL}/{endpoint}"
    try:
        r = await client.get(url, headers=headers, params=params or {}, timeout=20)
        return r.status_code, r.json() if r.status_code < 400 else r.text
    except Exception as e:
        return 0, str(e)


async def main():
    email, token = await get_credentials()
    print(f"\n{'='*60}")
    print(f"Diagnóstico Alegra — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    async with httpx.AsyncClient() as client:
        # 1. Bank accounts
        print("── 1. GET /bank-accounts ──")
        status, data = await alegra_get(client, "bank-accounts", email, token)
        print(f"   HTTP {status}")
        if status == 200 and isinstance(data, list):
            print(f"   Cuentas bancarias: {len(data)}")
            for acc in data:
                print(f"   - ID={acc.get('id')} | Nombre={acc.get('name')} | Saldo={acc.get('balance')}")
            bank_account_ids = [acc.get("id") for acc in data]
        else:
            print(f"   Respuesta: {str(data)[:300]}")
            bank_account_ids = []

        # 2. Movements per account
        print(f"\n── 2. GET /bank-accounts/{{id}}/bank-movements ──")
        for acc_id in bank_account_ids:
            status, data = await alegra_get(
                client, f"bank-accounts/{acc_id}/bank-movements",
                email, token, {"start": 0, "limit": 5}
            )
            print(f"   Cuenta {acc_id} → HTTP {status}")
            if status == 200 and isinstance(data, list):
                print(f"   Movimientos (primeros 5 de ?): {len(data)}")
                for mov in data[:3]:
                    print(f"     · id={mov.get('id')} | date={mov.get('date')} | amount={mov.get('amount')} | desc={str(mov.get('description',''))[:40]}")
            else:
                print(f"   Respuesta: {str(data)[:300]}")

            # Count total
            status2, data2 = await alegra_get(
                client, f"bank-accounts/{acc_id}/bank-movements",
                email, token, {"start": 0, "limit": 200}
            )
            if status2 == 200 and isinstance(data2, list):
                print(f"   Total movimientos (limit=200): {len(data2)}")
                if data2:
                    fechas = [m.get('date','') for m in data2 if m.get('date')]
                    if fechas:
                        print(f"   Rango fechas: {min(fechas)} → {max(fechas)}")

        # 3. Payments endpoint
        print(f"\n── 3. GET /payments ──")
        status, data = await alegra_get(client, "payments", email, token, {"start": 0, "limit": 5})
        print(f"   HTTP {status}")
        if status == 200:
            if isinstance(data, list):
                print(f"   Pagos (primeros 5): {len(data)}")
                for p in data[:3]:
                    print(f"     · id={p.get('id')} | date={p.get('date')} | amount={p.get('amount')} | type={p.get('type')}")
            else:
                print(f"   Respuesta: {str(data)[:300]}")
        else:
            print(f"   Error: {str(data)[:300]}")

        # 4. Invoices (CxC) sample
        print(f"\n── 4. GET /invoices (muestra, status=all) ──")
        status, data = await alegra_get(client, "invoices", email, token, {"start": 0, "limit": 5})
        print(f"   HTTP {status}")
        if status == 200 and isinstance(data, list):
            print(f"   Facturas de venta (primeras 5): {len(data)}")
            for inv in data[:3]:
                total   = inv.get('total', 0)
                balance = inv.get('balance', 0)
                print(f"     · id={inv.get('id')} | date={inv.get('date')} | total={total} | balance={balance} | status={inv.get('status')}")
        else:
            print(f"   Respuesta: {str(data)[:300]}")

        # 5. Bills (CxP) sample
        print(f"\n── 5. GET /bills (muestra) ──")
        status, data = await alegra_get(client, "bills", email, token, {"start": 0, "limit": 5})
        print(f"   HTTP {status}")
        if status == 200 and isinstance(data, list):
            print(f"   Facturas de compra (primeras 5): {len(data)}")
            for b in data[:3]:
                print(f"     · id={b.get('id')} | date={b.get('date')} | total={b.get('total')} | status={b.get('status')}")
        else:
            print(f"   Respuesta: {str(data)[:300]}")

    print(f"\n{'='*60}")
    print("Diagnóstico completo.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
