import httpx
import os

SYNTAGE_BASE_URL = os.getenv("SYNTAGE_API_URL", "https://api.sandbox.syntage.com")
SYNTAGE_API_KEY = os.getenv("SYNTAGE_API_KEY", "")


class SyntageClient:
    def __init__(self):
        self.base_url = SYNTAGE_BASE_URL
        self.headers = {
            "X-Api-Key": SYNTAGE_API_KEY,
            "Accept": "application/ld+json",
            "Content-Type": "application/json",
        }

    async def create_credential(self, rfc: str, ciec: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/credentials",
                headers=self.headers,
                json={"rfc": rfc, "password": ciec, "type": "ciec"},
            )
            r.raise_for_status()
            return r.json()

    async def get_entity_by_rfc(self, rfc: str) -> dict | None:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{self.base_url}/entities?taxpayerIdentifier[]={rfc}",
                headers=self.headers,
            )
            r.raise_for_status()
            members = r.json().get("hydra:member", [])
            return members[0] if members else None

    async def get_tax_status(self, entity_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{self.base_url}/entities/{entity_id}/tax-status",
                headers=self.headers,
            )
            r.raise_for_status()
            return r.json()

    async def get_tax_compliance(self, entity_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{self.base_url}/entities/{entity_id}/tax-compliance-checks",
                headers=self.headers,
            )
            r.raise_for_status()
            return r.json()

    async def get_tax_status_pdf(self, entity_id: str) -> bytes:
        headers_pdf = {**self.headers, "Accept": "application/pdf"}
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(
                f"{self.base_url}/entities/{entity_id}/tax-status",
                headers=headers_pdf,
            )
            r.raise_for_status()
            return r.content
