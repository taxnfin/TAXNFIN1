import httpx
import os
import base64

BELVO_BASE_URL = os.getenv("BELVO_BASE_URL", "https://sandbox.belvo.com")
BELVO_SECRET_ID = os.getenv("BELVO_SECRET_ID", "")
BELVO_SECRET_PASSWORD = os.getenv("BELVO_SECRET_PASSWORD", "")


class BelvoClient:
    def __init__(self):
        self.base_url = BELVO_BASE_URL
        credentials = f"{BELVO_SECRET_ID}:{BELVO_SECRET_PASSWORD}"
        encoded = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
        }

    async def create_link(self, rfc: str, ciec: str) -> dict:
        """Crear link SAT con CIEC — registra el contribuyente en Belvo."""
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{self.base_url}/api/links/",
                headers=self.headers,
                json={
                    "institution": "sat_mx_fiscal",
                    "username": rfc,
                    "password": ciec,
                    "fetch_resources": ["TAX_STATUS", "TAX_COMPLIANCE_STATUS"],
                },
            )
            print(f"[BELVO] create_link status: {r.status_code}", flush=True)
            print(f"[BELVO] create_link response: {r.text[:500]}", flush=True)
            r.raise_for_status()
            return r.json()

    async def get_tax_status(self, link_id: str) -> dict:
        """Constancia de Situación Fiscal."""
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(
                f"{self.base_url}/api/tax-status/?link={link_id}",
                headers=self.headers,
            )
            print(f"[BELVO] tax_status status: {r.status_code}", flush=True)
            print(f"[BELVO] tax_status response: {r.text[:500]}", flush=True)
            r.raise_for_status()
            return r.json()

    async def get_tax_compliance(self, link_id: str) -> dict:
        """Opinión de Cumplimiento 32-D."""
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(
                f"{self.base_url}/api/tax-compliance-status/?link={link_id}",
                headers=self.headers,
            )
            print(f"[BELVO] tax_compliance status: {r.status_code}", flush=True)
            print(f"[BELVO] tax_compliance response: {r.text[:500]}", flush=True)
            r.raise_for_status()
            return r.json()

    async def get_tax_status_pdf(self, link_id: str) -> bytes:
        """Descarga PDF de Constancia."""
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(
                f"{self.base_url}/api/tax-status/?link={link_id}",
                headers={**self.headers, "Accept": "application/pdf"},
            )
            r.raise_for_status()
            return r.content
