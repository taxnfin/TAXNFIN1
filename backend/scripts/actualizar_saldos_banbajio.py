"""
Script para registrar saldos historicos verificados de BanBajio en TaxnFin.
Datos extraidos de estados de cuenta PDFs oficiales (Ene-May 2026).

Uso: python backend/scripts/actualizar_saldos_banbajio.py <TOKEN_JWT>

El TOKEN se obtiene de:
  cashflow.taxnfin.com -> F12 -> Console -> localStorage.getItem('token')

Los IDs de cuentas bancarias se obtienen automaticamente via API si no los conoces.
"""
import asyncio
import httpx
import sys

BASE_URL = "https://taxnfin1-production.up.railway.app"

# Saldos verificados de estados de cuenta BanBajio (fuente: PDF oficial)
# Formato: (moneda, saldo, fecha_corte, descripcion)
HISTORICO = [
    ("MXN",  25180.98,  "2025-12-31", "Edo Cta MXN Diciembre 2025"),
    ("USD",  16286.71,  "2025-12-31", "Edo Cta USD Diciembre 2025"),
    ("MXN",  25180.98,  "2026-01-01", "Saldo inicio enero 2026 MXN"),
    ("USD",  16286.71,  "2026-01-01", "Saldo inicio enero 2026 USD"),
    ("MXN",  96512.44,  "2026-01-31", "Edo Cta MXN Enero 2026"),
    ("USD",  15853.83,  "2026-01-31", "Edo Cta USD Enero 2026"),
    ("MXN", 132865.17,  "2026-02-28", "Edo Cta MXN Febrero 2026"),
    ("USD",  30887.28,  "2026-02-28", "Edo Cta USD Febrero 2026"),
    ("MXN", 115276.08,  "2026-03-31", "Edo Cta MXN Marzo 2026"),
    ("USD",  15981.97,  "2026-03-31", "Edo Cta USD Marzo 2026"),
    ("MXN",  89779.93,  "2026-04-30", "Edo Cta MXN Abril 2026"),
    ("USD",   5517.90,  "2026-04-30", "Edo Cta USD Abril 2026"),
    ("MXN",  65149.37,  "2026-05-31", "Edo Cta MXN Mayo 2026"),
    ("USD",  10207.71,  "2026-05-31", "Edo Cta USD Mayo 2026"),
]


async def main(token: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    print(f"\nConectando a {BASE_URL}...")

    async with httpx.AsyncClient(timeout=30) as client:

        # ── 1. Obtener company_id activo del usuario ───────────────────
        r = await client.get(f"{BASE_URL}/api/auth/me", headers=headers)
        if r.status_code != 200:
            print(f"[ERROR] No pude autenticar: {r.status_code} {r.text[:200]}")
            return
        me = r.json()
        # Buscar empresa Ortech (Alegra / COT080703U40)
        company_ids = me.get('company_ids', [])
        print(f"  Usuario: {me.get('email')}")
        print(f"  Empresas: {len(company_ids)} disponibles\n")

        # ── 2. Obtener cuentas bancarias de cada empresa ───────────────
        # Iterar empresas hasta encontrar BanBajio MXN + USD
        cuentas_por_moneda = {}  # {"MXN": id, "USD": id}

        for cid in company_ids:
            h = {**headers, "X-Company-ID": cid}
            r2 = await client.get(f"{BASE_URL}/api/bank-accounts", headers=h)
            if r2.status_code != 200:
                continue
            cuentas = r2.json()
            # Filtrar BanBajio
            for c in cuentas:
                banco = (c.get('banco') or c.get('nombre') or '').lower()
                moneda = c.get('moneda', 'MXN')
                if 'bajio' in banco or 'banbajio' in banco or 'bajío' in banco:
                    cuentas_por_moneda[moneda] = {
                        'id': c['id'],
                        'company_id': cid,
                        'nombre': c.get('nombre') or c.get('banco', ''),
                    }

        if not cuentas_por_moneda:
            print("[ERROR] No encontre cuentas BanBajio. Verifica que el token tenga acceso a Ortech.")
            print("        O ejecuta primero: GET /api/bank-accounts y copia los IDs manualmente.")
            return

        print("Cuentas BanBajio encontradas:")
        for moneda, info in cuentas_por_moneda.items():
            print(f"  {moneda}: {info['nombre']} (id: {info['id'][:8]}...) empresa: {info['company_id'][:8]}...")

        # ── 3. Registrar historial de saldos ──────────────────────────
        print(f"\nRegistrando {len(HISTORICO)} saldos historicos...\n")

        for moneda, saldo, fecha, desc in HISTORICO:
            if moneda not in cuentas_por_moneda:
                print(f"  [SKIP] {desc}: no hay cuenta {moneda} de BanBajio")
                continue

            info = cuentas_por_moneda[moneda]
            acct_id = info['id']
            company_id = info['company_id']

            h = {**headers, "X-Company-ID": company_id}
            url = f"{BASE_URL}/api/bank-accounts/{acct_id}/history"
            payload = {
                "saldo": saldo,
                "fecha": fecha,
                "fuente": "estado_cuenta_pdf",
                "notas": f"PDF BanBajio oficial - {desc}",
            }
            r3 = await client.post(url, json=payload, headers=h)
            icon = "OK" if r3.status_code == 200 else "ERR"
            print(f"  [{icon}] {desc}: ${saldo:>12,.2f}  [{r3.status_code}]")
            if r3.status_code != 200:
                print(f"        {r3.text[:200]}")

    print("\nListo. El dashboard de Ortech ahora tendra anclas bancarias para:")
    print("  Enero, Febrero, Marzo, Abril y Mayo 2026.")
    print("  El saldo de fin de cada mes cuadrara con el estado de cuenta BanBajio.")
    print("\nRecarga el dashboard en cashflow.taxnfin.com para verificar.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python backend/scripts/actualizar_saldos_banbajio.py <TOKEN_JWT>")
        print("")
        print("Obtener el token:")
        print("  1. Abre cashflow.taxnfin.com y loguea como Kary (cfo de Ortech)")
        print("  2. F12 -> Console -> escribe: localStorage.getItem('token')")
        print("  3. Copia el valor y pegalo aqui")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
