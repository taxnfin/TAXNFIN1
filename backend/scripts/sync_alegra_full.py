"""
Script de sync completo de Alegra para una empresa.
Llama directamente la API de Alegra sin pasar por FastAPI.

Uso:
    cd backend
    python scripts/sync_alegra_full.py
"""
import asyncio
import sys
import os
import base64
import uuid
import httpx
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

COMPANY_ID = "89cda61e"
DATE_FROM  = "2026-01-01"
DATE_TO    = "2026-06-17"
ALEGRA_BASE_URL = "https://api.alegra.com/api/v1"


def _headers(email: str, token: str) -> dict:
    cred = base64.b64encode(f"{email}:{token}".encode()).decode()
    return {"Authorization": f"Basic {cred}", "Content-Type": "application/json"}


async def alegra_get(endpoint: str, email: str, token: str, params: dict = None):
    async with httpx.AsyncClient(timeout=60.0) as client:
        for attempt in range(3):
            try:
                r = await client.get(
                    f"{ALEGRA_BASE_URL}/{endpoint}",
                    headers=_headers(email, token),
                    params=params or {}
                )
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
    return None


async def main():
    from core.config import settings
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.DB_NAME]

    company = await db.companies.find_one({'id': COMPANY_ID}, {'_id': 0})
    if not company:
        print(f"ERROR: No se encontró empresa id={COMPANY_ID}")
        client.close()
        return

    email = company.get('alegra_email')
    token = company.get('alegra_token')
    if not email or not token:
        print("ERROR: Faltan credenciales Alegra (alegra_email / alegra_token)")
        client.close()
        return

    print(f"Empresa: {company.get('nombre', COMPANY_ID)}")
    print(f"Alegra email: {email}")
    print(f"Rango: {DATE_FROM} → {DATE_TO}")
    print("=" * 60)

    # ── 1. Sync invoices ──────────────────────────────────────────
    print("\n[1/3] Facturas de clientes (invoices / CxC)...")
    r1 = await _sync_invoices(db, email, token, COMPANY_ID, DATE_FROM, DATE_TO)
    print(f"  {r1}")

    # ── 2. Sync bills ─────────────────────────────────────────────
    print("\n[2/3] Facturas de proveedor (bills / CxP)...")
    r2 = await _sync_bills(db, email, token, COMPANY_ID, DATE_FROM, DATE_TO)
    print(f"  {r2}")

    # ── 3. Sync payments ──────────────────────────────────────────
    print("\n[3/3] Pagos (payments)...")
    r3 = await _sync_payments(db, email, token, COMPANY_ID, DATE_FROM, DATE_TO)
    print(f"  {r3}")

    client.close()
    print("\n✓ Sync completo.")


async def _paginate(endpoint, email, token, date_from, date_to, extra_params=None):
    """Fetches all pages from an Alegra list endpoint."""
    results = []
    start = 0
    MAX_PAGES = 50
    for _ in range(MAX_PAGES):
        params = {'start': start, 'limit': 30, **(extra_params or {})}
        if date_from:
            params['date[from]'] = date_from
        if date_to:
            params['date[to]'] = date_to
        batch = await alegra_get(endpoint, email, token, params)
        await asyncio.sleep(0.3)
        if not batch or not isinstance(batch, list):
            break
        filtered = [x for x in batch
                    if date_from <= (x.get('date') or '')[:10] <= date_to]
        results.extend(filtered)
        if len(batch) < 30:
            break
        start += 30
    return results


async def _sync_invoices(db, email, token, company_id, date_from, date_to):
    items = await _paginate('invoices', email, token, date_from, date_to,
                            {'order_field': 'date', 'order_direction': 'ASC'})
    created = updated = skipped = errors = 0
    for inv in items:
        try:
            alegra_id = str(inv.get('id'))
            status = (inv.get('status') or '').lower()
            if status in ('void', 'draft'):
                skipped += 1
                continue
            total = float(inv.get('total', 0) or 0)
            balance_raw = inv.get('balance')
            balance = float(balance_raw) if isinstance(balance_raw, (int, float)) else 0.0
            client_obj = inv.get('client') or {}
            client_name = client_obj.get('name', '') if isinstance(client_obj, dict) else ''
            curr_obj = inv.get('currency') or {}
            moneda = curr_obj.get('code', 'MXN') if isinstance(curr_obj, dict) else 'MXN'

            doc = {
                'alegra_id': alegra_id,
                'source': 'alegra',
                'company_id': company_id,
                'tipo_cfdi': 'ingreso',
                'estatus': 'vigente' if status == 'open' else status,
                'estado_conciliacion': 'conciliado' if balance <= 0.01 else 'pendiente',
                'total': total,
                'balance': balance,
                'receptor_nombre': client_name,
                'fecha_emision': (inv.get('date') or '')[:10],
                'fecha_vencimiento': (inv.get('dueDate') or inv.get('date') or '')[:10],
                'folio_alegra': str(inv.get('number', '')),
                'moneda': moneda,
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }
            res = await db.cfdis.update_one(
                {'company_id': company_id, 'source': 'alegra', 'alegra_id': alegra_id},
                {'$set': doc,
                 '$setOnInsert': {'id': str(uuid.uuid4()),
                                  'created_at': datetime.now(timezone.utc).isoformat()}},
                upsert=True
            )
            if res.upserted_id:
                created += 1
            else:
                updated += 1
        except Exception as e:
            print(f"    Error invoice {inv.get('id')}: {e}")
            errors += 1
    return {'total': len(items), 'created': created, 'updated': updated,
            'skipped': skipped, 'errors': errors}


async def _sync_bills(db, email, token, company_id, date_from, date_to):
    items = await _paginate('bills', email, token, date_from, date_to,
                            {'order_field': 'date', 'order_direction': 'ASC'})
    created = updated = skipped = errors = 0
    for bill in items:
        try:
            alegra_id = str(bill.get('id'))
            status = (bill.get('status') or '').lower()
            if status in ('void', 'draft'):
                skipped += 1
                continue
            total = float(bill.get('total', 0) or 0)
            balance_raw = bill.get('balance')
            balance = float(balance_raw) if isinstance(balance_raw, (int, float)) else 0.0
            vendor_obj = bill.get('vendor') or {}
            vendor_name = vendor_obj.get('name', '') if isinstance(vendor_obj, dict) else ''
            curr_obj = bill.get('currency') or {}
            moneda = curr_obj.get('code', 'MXN') if isinstance(curr_obj, dict) else 'MXN'

            doc = {
                'alegra_id': alegra_id,
                'source': 'alegra',
                'company_id': company_id,
                'tipo_cfdi': 'egreso',
                'estatus': 'vigente' if status == 'open' else status,
                'estado_conciliacion': 'conciliado' if balance <= 0.01 else 'pendiente',
                'total': total,
                'balance': balance,
                'emisor_nombre': vendor_name,
                'fecha_emision': (bill.get('date') or '')[:10],
                'fecha_vencimiento': (bill.get('dueDate') or bill.get('date') or '')[:10],
                'folio_alegra': str(bill.get('number', '')),
                'moneda': moneda,
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }
            res = await db.cfdis.update_one(
                {'company_id': company_id, 'source': 'alegra', 'alegra_id': alegra_id},
                {'$set': doc,
                 '$setOnInsert': {'id': str(uuid.uuid4()),
                                  'created_at': datetime.now(timezone.utc).isoformat()}},
                upsert=True
            )
            if res.upserted_id:
                created += 1
            else:
                updated += 1
        except Exception as e:
            print(f"    Error bill {bill.get('id')}: {e}")
            errors += 1
    return {'total': len(items), 'created': created, 'updated': updated,
            'skipped': skipped, 'errors': errors}


async def _sync_payments(db, email, token, company_id, date_from, date_to):
    # Payments usa parámetros distintos (date-start / date-end)
    all_payments = []
    start = 0
    MAX_PAGES = 50
    for _ in range(MAX_PAGES):
        params = {
            'start': start, 'limit': 30, 'order': 'date',
            'fields': 'id,date,amount,type,status,bankAccount,client,observations,anotation,categories,invoices',
            'date-start': date_from, 'date-end': date_to,
        }
        batch = await alegra_get('payments', email, token, params)
        await asyncio.sleep(0.3)
        if not batch or not isinstance(batch, list):
            break
        filtered = [p for p in batch
                    if date_from <= (p.get('date') or '')[:10] <= date_to]
        all_payments.extend(filtered)
        if len(batch) < 30:
            break
        start += 30

    created = updated = skipped = linked = errors = 0
    for payment in all_payments:
        try:
            alegra_id = str(payment.get('id'))
            pago_type = (payment.get('type') or '').lower()
            if (payment.get('status') or '').lower() == 'void':
                skipped += 1
                continue

            tipo = 'cobro' if pago_type == 'in' else 'pago'
            amount = float(payment.get('amount', 0) or 0)
            fecha_mov = (payment.get('date') or datetime.now(timezone.utc).strftime('%Y-%m-%d'))[:10]
            client_obj = payment.get('client') or {}
            client_name = (client_obj.get('name') or '') if isinstance(client_obj, dict) else ''
            categories = payment.get('categories') or []
            cat_name = (categories[0].get('name', '') if categories and isinstance(categories[0], dict) else '')
            concepto = (client_name or cat_name or
                        payment.get('observations') or payment.get('anotation') or
                        f"Pago Alegra {alegra_id}")
            bank_obj = payment.get('bankAccount') or {}
            bank_name = (bank_obj.get('name') or '') if isinstance(bank_obj, dict) else ''

            # Vincular con facturas
            facturas_aplicadas = []
            for inv_ref in (payment.get('invoices') or []):
                if not isinstance(inv_ref, dict):
                    continue
                inv_alegra_id = str(inv_ref.get('id', ''))
                monto_aplicado = float(inv_ref.get('amount', 0) or 0)
                if not inv_alegra_id:
                    continue
                cfdi_doc = await db.cfdis.find_one(
                    {'company_id': company_id, 'source': 'alegra', 'alegra_id': inv_alegra_id},
                    {'_id': 0, 'id': 1, 'folio_alegra': 1, 'total': 1,
                     'monto_cobrado': 1, 'monto_pagado': 1, 'tipo_cfdi': 1}
                )
                if not cfdi_doc:
                    continue
                facturas_aplicadas.append({
                    'cfdi_id': cfdi_doc['id'],
                    'alegra_id': inv_alegra_id,
                    'monto_aplicado': monto_aplicado,
                    'folio': cfdi_doc.get('folio_alegra', ''),
                })
                cfdi_total = float(cfdi_doc.get('total', 0) or 0)
                cfdi_tipo = str(cfdi_doc.get('tipo_cfdi', '') or '').lower()
                campo = 'monto_cobrado' if cfdi_tipo in ('ingreso', 'i', 'income') else 'monto_pagado'
                previo = float(cfdi_doc.get(campo, 0) or 0)
                nuevo = previo + monto_aplicado
                estado = ('conciliado' if cfdi_total > 0 and nuevo >= cfdi_total - 0.01
                          else 'parcial' if nuevo > 0 else 'pendiente')
                await db.cfdis.update_one(
                    {'company_id': company_id, 'id': cfdi_doc['id']},
                    {'$set': {campo: nuevo, 'estado_conciliacion': estado}}
                )
                linked += 1

            payment_doc = {
                'alegra_id': alegra_id,
                'alegra_type': 'payment',
                'company_id': company_id,
                'tipo': tipo,
                'concepto': concepto,
                'monto': abs(amount),
                'moneda': 'MXN',
                'metodo_pago': 'transferencia',
                'fecha_vencimiento': fecha_mov,
                'fecha_pago': fecha_mov,
                'estatus': 'completado',
                'referencia': str(alegra_id),
                'beneficiario': client_name,
                'es_real': True,
                'source': 'alegra',
                'alegra_bank_account': bank_name,
                'facturas_aplicadas': facturas_aplicadas,
                'estado_conciliacion': 'conciliado' if facturas_aplicadas else 'sin_factura',
                'updated_at': datetime.now(timezone.utc).isoformat(),
            }
            res = await db.payments.update_one(
                {'company_id': company_id, 'alegra_id': alegra_id, 'alegra_type': 'payment'},
                {'$set': payment_doc,
                 '$setOnInsert': {'id': str(uuid.uuid4()),
                                  'created_at': datetime.now(timezone.utc).isoformat()}},
                upsert=True
            )
            if res.upserted_id:
                created += 1
            else:
                updated += 1
        except Exception as e:
            print(f"    Error payment {payment.get('id')}: {e}")
            errors += 1

    return {'total': len(all_payments), 'created': created, 'updated': updated,
            'skipped': skipped, 'linked_invoices': linked, 'errors': errors}


if __name__ == '__main__':
    asyncio.run(main())
