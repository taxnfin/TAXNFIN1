"""
Script para registrar saldos históricos verificados de BanBajío en TaxnFin.
Datos extraídos de estados de cuenta PDFs oficiales (Mar/Abr/May 2026).

Uso: python backend/scripts/actualizar_saldos_banbajio.py <TOKEN_JWT>

El TOKEN se obtiene de: F12 → Console → localStorage.getItem('token')
"""
import asyncio
import httpx
import sys

BASE_URL = "https://taxnfin1-production.up.railway.app"
COMPANY_ID_ORTECH = "89cda61e-af34-4b3c-8d2e-1234567890ab"  # ajustar si cambia

BAJIO_MXN_ID = "908fd8ae-657f-4b24-8138-46a606be60c2"
BAJIO_USD_ID  = "9090c0a2-ce48-4fe1-894b-405af275cb50"

# Saldos verificados de estados de cuenta (fuente: PDF BanBajío)
HISTORICO = [
    # (account_id, saldo, fecha, descripcion)
    (BAJIO_MXN_ID, 96512.44,  "2026-01-31", "Edo Cta MXN Enero 2026"),
    (BAJIO_USD_ID, 15853.83,  "2026-01-31", "Edo Cta USD Enero 2026"),
    (BAJIO_MXN_ID, 132865.17, "2026-02-28", "Edo Cta MXN Febrero 2026"),
    (BAJIO_USD_ID, 30887.28,  "2026-02-28", "Edo Cta USD Febrero 2026"),
    (BAJIO_MXN_ID, 115276.08, "2026-03-31", "Edo Cta MXN Marzo 2026"),
    (BAJIO_USD_ID, 15981.97,  "2026-03-31", "Edo Cta USD Marzo 2026"),
    (BAJIO_MXN_ID, 89779.93,  "2026-04-30", "Edo Cta MXN Abril 2026"),
    (BAJIO_USD_ID, 5517.90,   "2026-04-30", "Edo Cta USD Abril 2026"),
    (BAJIO_MXN_ID, 65149.37,  "2026-05-31", "Edo Cta MXN Mayo 2026"),
    (BAJIO_USD_ID, 10207.71,  "2026-05-31", "Edo Cta USD Mayo 2026"),
]


async def main(token: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Company-ID": COMPANY_ID_ORTECH,
        "Content-Type": "application/json",
    }

    print(f"\n🏦 Registrando saldos históricos BanBajío → TaxnFin")
    print(f"   {BASE_URL}\n")

    async with httpx.AsyncClient(timeout=30) as client:
        for acct_id, saldo, fecha, desc in HISTORICO:
            url = f"{BASE_URL}/bank-accounts/{acct_id}/history"
            payload = {
                "saldo": saldo,
                "fecha": fecha,
                "fuente": "estado_cuenta_pdf",
                "notas": f"Cargado de PDF oficial BanBajío - {desc}",
            }
            r = await client.post(url, json=payload, headers=headers)
            icon = "✅" if r.status_code == 200 else "❌"
            print(f"  {icon} {desc}: ${saldo:>12,.2f}  [{r.status_code}]")
            if r.status_code != 200:
                print(f"     {r.text[:300]}")

    print("\n✅ Listo. El motor de cashflow ahora tiene anclas para:")
    print("   Enero, Febrero, Marzo, Abril y Mayo 2026.")
    print("   El saldo de fin de cada mes cuadrará con el estado de cuenta.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python backend/scripts/actualizar_saldos_banbajio.py <TOKEN_JWT>")
        print("\nObtén el token:")
        print("  cashflow.taxnfin.com → F12 → Console → localStorage.getItem('token')")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
