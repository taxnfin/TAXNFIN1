"""
Contalink Integration — Router + Client
Combina el ContalinkClient existente con los endpoints FastAPI
"""
import httpx
import logging
import os
import uuid as uuid_lib
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

CONTALINK_BASE_URL = os.environ.get(
    'CONTALINK_BASE_URL',
    'https://794lol2h95.execute-api.us-east-1.amazonaws.com/prod'
)


# ══════════════════════════════════════════════════════════════════════════════
# CLIENT (tu código original — sin cambios)
# ══════════════════════════════════════════════════════════════════════════════
class ContalinkClient:
    """Client for CONTALink API"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = CONTALINK_BASE_URL
        self.headers = {
            'Authorization': api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    async def test_connection(self) -> Dict:
        """Test if the API key is valid by fetching trial balance for current month"""
        try:
            today = datetime.now()
            start = f"{today.year}-{today.month:02d}-01"
            end = f"{today.year}-{today.month:02d}-28"
            async with httpx.AsyncClient(timeout=15) as client:
                res = await client.get(
                    f"{self.base_url}/accounting/trial-balance/",
                    headers=self.headers,
                    params={'start_date': start, 'end_date': end, 'period': 'O'}
                )
                if res.status_code == 200:
                    data = res.json()
                    return {'status': 'connected', 'message': data.get('message', 'OK')}
                return {'status': 'error', 'message': f'HTTP {res.status_code}: {res.text[:200]}'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    async def get_trial_balance(self, start_date: str, end_date: str, include_period_13: bool = False) -> Dict:
        """Get trial balance (balanza de comprobación)"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                res = await client.get(
                    f"{self.base_url}/accounting/trial-balance/",
                    headers=self.headers,
                    params={
                        'start_date': start_date,
                        'end_date': end_date,
                        'period': 'I' if include_period_13 else 'O'
                    }
                )
                if res.status_code == 200:
                    return res.json()
                return {'status': 0, 'message': f'Error HTTP {res.status_code}'}
        except Exception as e:
            logger.error(f"ContalinkClient.get_trial_balance error: {e}")
            return {'status': 0, 'message': str(e)}

    async def get_invoices(self, rfc: str, transaction_type: str, document_type: str,
                           start_date: str, end_date: str, page: int = 0) -> Dict:
        """Get fiscal documents list"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                res = await client.get(
                    f"{self.base_url}/invoices/list/",
                    headers=self.headers,
                    params={
                        'transaction_type': transaction_type,
                        'document_type': document_type,
                        'rfc': rfc,
                        'start_date': start_date,
                        'end_date': end_date,
                        'page': page
                    }
                )
                logger.info(f"Contalink invoices HTTP {res.status_code} - raw: {res.text[:800]}")
                if res.status_code == 200:
                    try:
                        data = res.json()
                        logger.info(f"Contalink invoices parsed OK - type: {type(data).__name__}, sample: {str(data)[:300]}")
                        return data
                    except Exception as parse_err:
                        logger.error(f"Contalink invoices JSON parse error: {parse_err} - raw: {res.text[:300]}")
                        return {'status': 0, 'message': f'JSON parse error: {parse_err}'}
                return {'status': 0, 'message': f'Error HTTP {res.status_code}: {res.text[:200]}'}
        except Exception as e:
            logger.error(f"ContalinkClient.get_invoices error: {e}")
            return {'status': 0, 'message': str(e)}

    async def get_account_balance(self, account_number: str, date: str) -> Dict:
        """Get balance of a specific account"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                res = await client.get(
                    f"{self.base_url}/accounting/get-account-balance/{account_number}/",
                    headers=self.headers,
                    params={'date': date, 'period': 'O'}
                )
                if res.status_code == 200:
                    return res.json()
                return {'status': 0, 'message': f'Error HTTP {res.status_code}'}
        except Exception as e:
            return {'status': 0, 'message': str(e)}

    async def create_conciliation(self, invoice_uuid: str, amount: float,
                                  bank_account: str, payment_date: str,
                                  payment_form: str = '03') -> Dict:
        """Create a conciliation for an invoice"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                res = await client.post(
                    f"{self.base_url}/conciliation/create/",
                    headers=self.headers,
                    json={
                        'invoice_id': invoice_uuid,
                        'amount': amount,
                        'bank_account': bank_account,
                        'payment_date': payment_date,
                        'payment_form': payment_form
                    }
                )
                if res.status_code == 200:
                    return res.json()
                return {'status': 0, 'message': f'Error HTTP {res.status_code}'}
        except Exception as e:
            return {'status': 0, 'message': str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTER — FastAPI endpoints
# ══════════════════════════════════════════════════════════════════════════════
from core.database import db
from core.auth import get_current_user, get_active_company_id
from services.audit import audit_log

router = APIRouter(prefix="/contalink", tags=["Contalink Integration"])


class ContalinkCredentials(BaseModel):
    api_key: str
    rfc: str


class BankTransactionCreate(BaseModel):
    date: str
    amount: float
    description: str
    transaction_type: str  # "income" | "expense"
    bank_account_id: Optional[str] = None


async def get_contalink_credentials(company_id: str) -> dict:
    """Get stored Contalink credentials for a company"""
    integration = await db.integrations.find_one(
        {"company_id": company_id, "type": "contalink", "active": True},
        {"_id": 0}
    )
    if not integration:
        raise HTTPException(
            status_code=400,
            detail="Contalink no está configurado. Ve a Integraciones y guarda tu API Key."
        )
    return integration


# ── Connection ─────────────────────────────────────────────────────────────────
@router.post("/test-connection")
async def test_contalink_connection(
    credentials: ContalinkCredentials,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Test Contalink API connection"""
    client = ContalinkClient(credentials.api_key)
    result = await client.test_connection()
    return {
        "success": result["status"] == "connected",
        "message": result["message"],
        "rfc": credentials.rfc
    }


@router.post("/save-credentials")
async def save_contalink_credentials(
    credentials: ContalinkCredentials,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Save Contalink credentials for a company"""
    company_id = await get_active_company_id(request, current_user)

    # Test connection first
    client = ContalinkClient(credentials.api_key)
    result = await client.test_connection()
    logger.info(f"Contalink test_connection result: {result}")
    if result["status"] != "connected":
        raise HTTPException(status_code=400, detail=f"Credenciales inválidas: {result['message']}")

    logger.info(f"Saving contalink credentials for company_id: {company_id}, rfc: {credentials.rfc}")
    await db.integrations.update_one(
        {"company_id": company_id, "type": "contalink"},
        {"$set": {
            "company_id": company_id,
            "type": "contalink",
            "api_key": credentials.api_key,
            "rfc": credentials.rfc,
            "active": True,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    await audit_log(company_id, "Integration", "contalink", "SAVE_CREDENTIALS", current_user["id"])
    return {"success": True, "message": "Credenciales guardadas correctamente"}


@router.get("/status")
async def get_contalink_status(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Get Contalink integration status"""
    company_id = await get_active_company_id(request, current_user)
    integration = await db.integrations.find_one(
        {"company_id": company_id, "type": "contalink"},
        {"_id": 0, "api_key": 0}
    )
    logger.info(f"Contalink status check for company_id: {company_id}, integration found: {integration is not None}")
    if not integration:
        return {"connected": False, "message": "No configurado"}

    last_sync = await db.contalink_sync_log.find_one(
        {"company_id": company_id},
        {"_id": 0},
        sort=[("synced_at", -1)]
    )
    return {
        "connected": integration.get("active", False),
        "rfc": integration.get("rfc"),
        "last_sync": last_sync.get("synced_at") if last_sync else None,
        "last_sync_type": last_sync.get("type") if last_sync else None,
    }


# ── Invoices Sync ──────────────────────────────────────────────────────────────
@router.post("/sync/invoices")
async def sync_contalink_invoices(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    transaction_type: str = Query("received", description="received | issued"),
    document_type: str = Query("I", description="I=Ingreso, E=Egreso, N=Nómina, P=Pago"),
    days_back: int = Query(90),
):
    """Sync invoices/CFDIs from Contalink into TaxnFin"""
    company_id = await get_active_company_id(request, current_user)
    creds = await get_contalink_credentials(company_id)
    client = ContalinkClient(creds["api_key"])

    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

    # Contalink API uses E=emitidas, R=recibidas
    tx_type_map = {"issued": "E", "received": "R", "E": "E", "R": "R"}
    contalink_tx_type = tx_type_map.get(transaction_type, "E")
    # Contalink API document_type values (exact case required)
    doc_type_map = {"I": "Ingreso", "E": "Egreso", "N": "Nomina", "P": "Pago",
                    "ingreso": "Ingreso", "egreso": "Egreso", "nomina": "Nomina", "pago": "Pago",
                    "Ingreso": "Ingreso", "Egreso": "Egreso", "Nomina": "Nomina", "Pago": "Pago"}
    contalink_doc_type = doc_type_map.get(document_type, "Ingreso")
    logger.info(f"Sync invoices: transaction_type={transaction_type} -> contalink={contalink_tx_type}, document_type={document_type} -> {contalink_doc_type}, days_back={days_back}")

    synced = created = updated = errors = 0
    page = 0

    while True:
        result = await client.get_invoices(
            rfc=creds["rfc"],
            transaction_type=contalink_tx_type,
            document_type=contalink_doc_type,
            start_date=start_date,
            end_date=end_date,
            page=page
        )

        if result.get("status") == 0:
            logger.error(f"Contalink invoices error: {result.get('message')}")
            break

        # Contalink response: {"list": {"total": N, "invoices": [...]}}
        if isinstance(result, list):
            invoices = result
        elif "list" in result:
            invoices = result["list"].get("invoices", [])
        else:
            invoices = result.get("data", result.get("invoices", result.get("documents", [])))
        
        logger.info(f"Page {page}: {len(invoices)} invoices found")
        if not invoices:
            break

        for inv in invoices:
            try:
                synced += 1
                uuid_val = (inv.get("uuid") or inv.get("UUID") or
                            inv.get("folio_fiscal") or inv.get("folio_uuid", "")).strip()
                if not uuid_val:
                    continue

                # transaction_type R=recibidas=egreso, E=emitidas=ingreso
                if contalink_tx_type == "R":
                    tipo_cfdi = "egreso"
                else:
                    tipo_cfdi_map = {"I": "ingreso", "Ingreso": "ingreso", "E": "egreso", "Egreso": "egreso", "N": "nomina", "Nomina": "nomina", "P": "pago", "Pago": "pago"}
                    tipo_cfdi = tipo_cfdi_map.get(document_type, "ingreso")

                # Normalize fecha fields - Contalink uses fecha_expedicion
                fecha_raw = (inv.get("fecha_expedicion") or inv.get("fecha") or 
                             inv.get("fecha_emision") or "")
                fecha_timbrado_raw = (inv.get("fecha_timbrado") or fecha_raw or "")
                
                # Normalize estatus - Contalink uses Vigente/Cancelado (capitalized)
                estatus_raw = (inv.get("estatus") or inv.get("status") or "vigente").lower()
                if estatus_raw not in ["vigente", "cancelado"]:
                    estatus_raw = "vigente"

                # impuestos - calculate if not present
                total_val = float(inv.get("total") or 0)
                subtotal_val = float(inv.get("subtotal") or 0)
                impuestos_val = float(inv.get("impuestos") or (total_val - subtotal_val))

                doc = {
                    "company_id": company_id,
                    "uuid": uuid_val,
                    "tipo_cfdi": tipo_cfdi,
                    "emisor_rfc": inv.get("rfc_emisor") or inv.get("emisor_rfc", ""),
                    "emisor_nombre": inv.get("nombre_emisor") or inv.get("emisor_nombre", ""),
                    "receptor_rfc": inv.get("rfc_receptor") or inv.get("receptor_rfc") or creds["rfc"],
                    "receptor_nombre": inv.get("nombre_receptor") or inv.get("receptor_nombre", ""),
                    "fecha_emision": fecha_raw or datetime.now(timezone.utc).isoformat(),
                    "fecha_timbrado": fecha_timbrado_raw or datetime.now(timezone.utc).isoformat(),
                    "total": total_val,
                    "subtotal": subtotal_val,
                    "impuestos": impuestos_val,
                    "moneda": inv.get("moneda", "MXN"),
                    "tipo_cambio": float(inv.get("tipo_cambio") or 1),
                    "estatus": estatus_raw,
                    "estado_cancelacion": "cancelado" if estatus_raw == "cancelado" else "vigente",
                    "metodo_pago": inv.get("metodo_pago", "PUE"),
                    "forma_pago": inv.get("forma_pago", "03"),
                    "fuente": "contalink",
                    "contalink_id": str(inv.get("id") or ""),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }

                existing = await db.cfdis.find_one(
                    {"company_id": company_id, "uuid": uuid_val},
                    {"_id": 0, "id": 1}
                )
                if existing:
                    await db.cfdis.update_one(
                        {"company_id": company_id, "uuid": uuid_val},
                        {"$set": doc}
                    )
                    updated += 1
                else:
                    doc["id"] = str(uuid_lib.uuid4())
                    doc["created_at"] = datetime.now(timezone.utc).isoformat()
                    await db.cfdis.insert_one(doc)
                    created += 1

            except Exception as e:
                logger.error(f"Error procesando factura: {e}")
                errors += 1

        if len(invoices) < 50:
            break
        page += 1

    await db.contalink_sync_log.insert_one({
        "company_id": company_id,
        "type": f"invoices_{transaction_type}_{document_type}",
        "synced": synced, "created": created, "updated": updated, "errors": errors,
        "synced_at": datetime.now(timezone.utc).isoformat()
    })
    await audit_log(company_id, "Integration", "contalink", "SYNC_INVOICES", current_user["id"])

    return {
        "success": True,
        "message": f"Sincronización completada: {created} nuevas, {updated} actualizadas, {errors} errores",
        "synced": synced, "created": created, "updated": updated, "errors": errors
    }


@router.post("/sync/all")
async def sync_all_contalink(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    days_back: int = Query(90),
):
    """Sync all: issued + received invoices"""
    results = {}
    for tx_type, doc_type in [("E", "Ingreso"), ("R", "Ingreso"), ("R", "Egreso")]:  # E=emitidas, R=recibidas
        try:
            results[f"{tx_type}_{doc_type}"] = await sync_contalink_invoices(
                request, current_user,
                transaction_type=tx_type, document_type=doc_type, days_back=days_back
            )
        except Exception as e:
            results[f"{tx_type}_{doc_type}"] = {"error": str(e)}

    total_created = sum(r.get("created", 0) for r in results.values() if isinstance(r, dict))
    total_updated = sum(r.get("updated", 0) for r in results.values() if isinstance(r, dict))
    total_errors  = sum(r.get("errors", 0) for r in results.values() if isinstance(r, dict))

    return {
        "success": True,
        "message": f"Sincronización completa: {total_created} nuevas, {total_updated} actualizadas",
        "total_created": total_created, "total_updated": total_updated, "total_errors": total_errors,
        "details": results
    }


# ── Trial Balance ──────────────────────────────────────────────────────────────
@router.get("/trial-balance")
async def get_trial_balance(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    start_date: str = Query(...),
    end_date: str = Query(...),
    include_period_13: bool = Query(False),
):
    """Get trial balance from Contalink"""
    company_id = await get_active_company_id(request, current_user)
    creds = await get_contalink_credentials(company_id)
    client = ContalinkClient(creds["api_key"])

    result = await client.get_trial_balance(start_date, end_date, include_period_13)

    await db.contalink_trial_balance.update_one(
        {"company_id": company_id, "start_date": start_date, "end_date": end_date},
        {"$set": {
            "company_id": company_id, "start_date": start_date, "end_date": end_date,
            "data": result, "fetched_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    return {"success": True, "data": result, "start_date": start_date, "end_date": end_date}


# ── Account Balance ────────────────────────────────────────────────────────────
@router.get("/account-balance/{account_number}")
async def get_account_balance(
    account_number: str,
    date: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Get balance for a specific account"""
    company_id = await get_active_company_id(request, current_user)
    creds = await get_contalink_credentials(company_id)
    client = ContalinkClient(creds["api_key"])

    result = await client.get_account_balance(account_number, date)
    return {"success": True, "account": account_number, "date": date, "data": result}


# ── Conciliation ───────────────────────────────────────────────────────────────
@router.post("/conciliation")
async def create_conciliation(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Create a CFDI conciliation in Contalink"""
    company_id = await get_active_company_id(request, current_user)
    creds = await get_contalink_credentials(company_id)
    client = ContalinkClient(creds["api_key"])

    body = await request.json()
    result = await client.create_conciliation(
        invoice_uuid=body.get("invoice_uuid", ""),
        amount=float(body.get("amount", 0)),
        bank_account=body.get("bank_account", ""),
        payment_date=body.get("payment_date", ""),
        payment_form=body.get("payment_form", "03")
    )
    await audit_log(company_id, "Integration", "contalink", "CREATE_CONCILIATION", current_user["id"])
    return {"success": True, "data": result}


# ── Delete Credentials ────────────────────────────────────────────────────────
@router.delete("/credentials")
async def delete_contalink_credentials(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Remove Contalink credentials (disconnect)"""
    company_id = await get_active_company_id(request, current_user)
    await db.integrations.update_one(
        {"company_id": company_id, "type": "contalink"},
        {"$set": {"active": False, "api_key": "", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    await audit_log(company_id, "Integration", "contalink", "DISCONNECT", current_user["id"])
    return {"success": True, "message": "Contalink desconectado"}


# ── Invoice Status ─────────────────────────────────────────────────────────────
@router.get("/invoice-status/{cfdi_uuid}")
async def check_invoice_status(
    cfdi_uuid: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Check CFDI status in Contalink"""
    company_id = await get_active_company_id(request, current_user)
    creds = await get_contalink_credentials(company_id)

    async with httpx.AsyncClient(timeout=15) as http_client:
        res = await http_client.get(
            f"{CONTALINK_BASE_URL}/invoices/check-status/{cfdi_uuid}/",
            headers={"Authorization": creds["api_key"], "Content-Type": "application/json"}
        )
        result = res.json() if res.status_code == 200 else {"status": 0, "message": res.text}

    return {"success": True, "uuid": cfdi_uuid, "data": result}
