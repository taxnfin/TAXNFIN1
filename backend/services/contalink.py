"""
TaxnFin — Contalink API Client
Documentación: https://apidocs.contalink.com

Endpoints implementados:
  - GET /invoices/list/          → Facturas (emitidas E / recibidas R)
  - GET /trial-balance/          → Balanza de comprobación
  - GET /accounts-receivable/    → CxC (cuentas por cobrar pendientes)
  - GET /accounts-payable/       → CxP (cuentas por pagar pendientes)
"""
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

CONTALINK_BASE_URL = "https://api.contalink.com/api/v1"


class ContalinkClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ══════════════════════════════════════════════════════════════════
    # BALANZA DE COMPROBACIÓN
    # ══════════════════════════════════════════════════════════════════

    async def get_trial_balance(self, start_date: str, end_date: str) -> dict:
        """
        GET /trial-balance/
        Params: start_date (YYYY-MM-DD), end_date (YYYY-MM-DD)
        """
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{CONTALINK_BASE_URL}/trial-balance/",
                headers=self.headers,
                params={"start_date": start_date, "end_date": end_date},
            )
            resp.raise_for_status()
            return resp.json()

    # ══════════════════════════════════════════════════════════════════
    # FACTURAS
    # ══════════════════════════════════════════════════════════════════

    async def get_invoices(
        self,
        transaction_type: str,   # "E" = emitidas (ingresos), "R" = recibidas (egresos)
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 200,
    ) -> dict:
        """
        GET /invoices/list/
        transaction_type: "E" (emitidas) | "R" (recibidas)
        """
        params = {
            "transaction_type": transaction_type,
            "page": page,
            "page_size": page_size,
        }
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{CONTALINK_BASE_URL}/invoices/list/",
                headers=self.headers,
                params=params,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_all_invoices(
        self,
        transaction_type: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list:
        """Pagina automáticamente y devuelve todas las facturas."""
        all_invoices = []
        page = 1
        while True:
            data = await self.get_invoices(
                transaction_type=transaction_type,
                start_date=start_date,
                end_date=end_date,
                page=page,
                page_size=200,
            )
            items = data.get("data", data) if isinstance(data, dict) else data
            if isinstance(items, dict):
                items = items.get("results", items.get("invoices", []))
            if not items:
                break
            all_invoices.extend(items)
            # Si la respuesta tiene paginación explícita
            total = data.get("count") or data.get("total") if isinstance(data, dict) else None
            if total and len(all_invoices) >= total:
                break
            if len(items) < 200:
                break
            page += 1
        return all_invoices

    # ══════════════════════════════════════════════════════════════════
    # CUENTAS POR COBRAR  (facturas emitidas con saldo pendiente)
    # ══════════════════════════════════════════════════════════════════

    async def get_cuentas_por_cobrar(
        self,
        cut_date: Optional[str] = None,   # YYYY-MM-DD; None = hoy
        start_date: Optional[str] = None, # Para filtrar por periodo de emisión
        end_date: Optional[str] = None,
    ) -> list:
        """
        Devuelve facturas emitidas (tipo E) con saldo pendiente > 0.
        Intenta primero /accounts-receivable/; si falla, calcula desde /invoices/list/.
        """
        # Intento 1: endpoint nativo de CxC (puede existir según versión de la API)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                params = {}
                if cut_date:
                    params["cut_date"] = cut_date
                resp = await client.get(
                    f"{CONTALINK_BASE_URL}/accounts-receivable/",
                    headers=self.headers,
                    params=params,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data", data)
                    if isinstance(items, list) and len(items) > 0:
                        return items
        except Exception:
            pass

        # Intento 2: calcular desde facturas emitidas
        invoices = await self.get_all_invoices(
            transaction_type="E",
            start_date=start_date,
            end_date=end_date,
        )

        cxc = []
        for inv in invoices:
            total   = float(inv.get("total", 0) or 0)
            cobrado = float(
                inv.get("amount_paid", 0)
                or inv.get("monto_cobrado", 0)
                or inv.get("paid_amount", 0)
                or 0
            )
            saldo = round(total - cobrado, 2)
            if saldo <= 0:
                continue  # Ya cobrada, skip

            cxc.append({
                "uuid":            inv.get("uuid") or inv.get("cfdi_uuid", ""),
                "folio":           inv.get("folio", ""),
                "fecha_emision":   inv.get("date") or inv.get("fecha_emision", ""),
                "fecha_vencimiento": inv.get("due_date") or inv.get("fecha_vencimiento", ""),
                "cliente_rfc":     inv.get("receiver_rfc") or inv.get("receptor_rfc", ""),
                "cliente_nombre":  inv.get("receiver_name") or inv.get("receptor_nombre", ""),
                "moneda":          inv.get("currency") or inv.get("moneda", "MXN"),
                "total":           total,
                "monto_cobrado":   cobrado,
                "saldo_pendiente": saldo,
                "estatus":         inv.get("status") or inv.get("estatus", ""),
                "dias_vencido":    _calcular_dias_vencido(
                    inv.get("due_date") or inv.get("fecha_vencimiento")
                ),
            })

        return cxc

    # ══════════════════════════════════════════════════════════════════
    # CUENTAS POR PAGAR  (facturas recibidas con saldo pendiente)
    # ══════════════════════════════════════════════════════════════════

    async def get_cuentas_por_pagar(
        self,
        cut_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list:
        """
        Devuelve facturas recibidas (tipo R) con saldo pendiente > 0.
        Intenta primero /accounts-payable/; si falla, calcula desde /invoices/list/.
        """
        # Intento 1: endpoint nativo
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                params = {}
                if cut_date:
                    params["cut_date"] = cut_date
                resp = await client.get(
                    f"{CONTALINK_BASE_URL}/accounts-payable/",
                    headers=self.headers,
                    params=params,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data", data)
                    if isinstance(items, list) and len(items) > 0:
                        return items
        except Exception:
            pass

        # Intento 2: calcular desde facturas recibidas
        invoices = await self.get_all_invoices(
            transaction_type="R",
            start_date=start_date,
            end_date=end_date,
        )

        cxp = []
        for inv in invoices:
            total  = float(inv.get("total", 0) or 0)
            pagado = float(
                inv.get("amount_paid", 0)
                or inv.get("monto_pagado", 0)
                or inv.get("paid_amount", 0)
                or 0
            )
            saldo = round(total - pagado, 2)
            if saldo <= 0:
                continue

            cxp.append({
                "uuid":            inv.get("uuid") or inv.get("cfdi_uuid", ""),
                "folio":           inv.get("folio", ""),
                "fecha_emision":   inv.get("date") or inv.get("fecha_emision", ""),
                "fecha_vencimiento": inv.get("due_date") or inv.get("fecha_vencimiento", ""),
                "proveedor_rfc":   inv.get("issuer_rfc") or inv.get("emisor_rfc", ""),
                "proveedor_nombre":inv.get("issuer_name") or inv.get("emisor_nombre", ""),
                "moneda":          inv.get("currency") or inv.get("moneda", "MXN"),
                "total":           total,
                "monto_pagado":    pagado,
                "saldo_pendiente": saldo,
                "estatus":         inv.get("status") or inv.get("estatus", ""),
                "dias_vencido":    _calcular_dias_vencido(
                    inv.get("due_date") or inv.get("fecha_vencimiento")
                ),
            })

        return cxp


# ══════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════

def _calcular_dias_vencido(fecha_vencimiento: Optional[str]) -> int:
    """Días vencido (positivo = ya venció, negativo = aún no vence)."""
    if not fecha_vencimiento:
        return 0
    from datetime import date
    try:
        venc = date.fromisoformat(str(fecha_vencimiento)[:10])
        return (date.today() - venc).days
    except Exception:
        return 0
