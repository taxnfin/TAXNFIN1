"""
Importador de estado de cuenta AMEX (CSV)
Formato esperado:
  Fecha,Fecha de Compra,Descripción,Importe
  28 Jun 2026,29 Jun 2026,WALMART VENTA EN LINEA,59181.00
  19 Mar 2026,20 Mar 2026,GRACIAS POR SU PAGO EN LINEA,-40609.15

Los negativos son pagos/créditos (abonos a la tarjeta).
Los positivos son cargos (gastos con la tarjeta).
"""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from typing import Dict, List
from datetime import datetime, timezone
import uuid
import csv
import io
import logging

from core.database import db
from core.auth import get_current_user, get_active_company_id
from services.audit import audit_log

router = APIRouter(prefix="/amex", tags=["AMEX Import"])
logger = logging.getLogger(__name__)

# Categorías automáticas basadas en palabras clave en la descripción
AMEX_AUTO_CATEGORIES = {
    # Telefonía
    "telcel": "Telefonía e internet",
    "telmex": "Telefonía e internet",
    "at&t": "Telefonía e internet",
    # Software y suscripciones
    "amazon": "Software y suscripciones",
    "microsoft": "Software y suscripciones",
    "adobe": "Software y suscripciones",
    "claude.ai": "Software y suscripciones",
    "lucid": "Software y suscripciones",
    "hotmart": "Software y suscripciones",
    # Combustible
    "gas": "Combustible",
    "petrum": "Combustible",
    "oxxo gas": "Combustible",
    "orsan": "Combustible",
    # Restaurantes y representación
    "restaurant": "Gastos de representación",
    "rest ": "Gastos de representación",
    "cafe": "Gastos de representación",
    "coffee": "Gastos de representación",
    "starbucks": "Gastos de representación",
    "costco": "Gastos de representación",
    # Transporte
    "uber": "Viáticos y gastos de viaje",
    "viva": "Viáticos y gastos de viaje",
    "autobus": "Viáticos y gastos de viaje",
    "aerobus": "Viáticos y gastos de viaje",
    "autopista": "Viáticos y gastos de viaje",
    "ipark": "Viáticos y gastos de viaje",
    # Comisiones financieras
    "flex pricing": "Comisiones bancarias",
    "pena por pago": "Comisiones bancarias",
    "iva aplicable": "Comisiones bancarias",
    # Walmart/proveedores
    "walmart": "Proveedores de materia prima",
    "home depot": "Mantenimiento y reparaciones",
    "autozone": "Mantenimiento y reparaciones",
    # Pagos a la tarjeta (no son gastos, son liquidaciones)
    "gracias por su pago": "Traspaso entre cuentas",
    "ecommerce": "Traspaso entre cuentas",
}


def _auto_categorize(descripcion: str) -> str:
    """Asigna categoría automáticamente basada en la descripción."""
    desc_lower = descripcion.lower()
    for keyword, categoria in AMEX_AUTO_CATEGORIES.items():
        if keyword in desc_lower:
            return categoria
    return ""  # Sin categoría → aparecerá en "Sin clasificar"


def _parse_amex_date(fecha_str: str) -> str:
    """Parsea fecha de AMEX: '28 Jun 2026' → '2026-06-28'"""
    meses = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12"
    }
    try:
        partes = fecha_str.strip().split()
        if len(partes) == 3:
            dia = partes[0].zfill(2)
            mes = meses.get(partes[1].lower()[:3], "01")
            anio = partes[2]
            return f"{anio}-{mes}-{dia}"
    except Exception:
        pass
    return ""


@router.post("/import-csv")
async def import_amex_csv(
    request: Request,
    file: UploadFile = File(...),
    cuenta_nombre: str = "AMEX",
    current_user: Dict = Depends(get_current_user),
):
    """
    Importa un CSV de actividad AMEX.
    Formato: Fecha,Fecha de Compra,Descripción,Importe
    """
    company_id = await get_active_company_id(request, current_user)

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos CSV")

    content = await file.read()
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    insertados = 0
    omitidos = 0
    errores = []
    movimientos = []

    for i, row in enumerate(reader, 1):
        try:
            fecha_raw = row.get("Fecha", "").strip()
            desc = row.get("Descripción", row.get("Descripcion", "")).strip()
            importe_raw = row.get("Importe", "0").strip().replace(",", "")

            if not fecha_raw or not desc:
                continue

            fecha = _parse_amex_date(fecha_raw)
            if not fecha:
                errores.append(f"Fila {i}: fecha inválida '{fecha_raw}'")
                continue

            importe = float(importe_raw)
            es_cargo = importe > 0     # cargo = gasto con tarjeta
            es_abono = importe < 0     # abono = pago/crédito

            categoria = _auto_categorize(desc)
            tipo = "retiro" if es_cargo else "deposito"
            monto = abs(importe)

            # Clave de deduplicación para evitar importar dos veces
            dedup_key = f"amex|{fecha}|{round(monto, 2)}|{desc[:30]}"

            movimientos.append({
                "dedup_key": dedup_key,
                "fecha": fecha,
                "descripcion": desc,
                "monto": monto,
                "tipo": tipo,
                "es_cargo": es_cargo,
                "es_abono": es_abono,
                "categoria": categoria,
            })
        except Exception as e:
            errores.append(f"Fila {i}: {str(e)}")

    # Verificar duplicados existentes
    existing_keys = set()
    existing_docs = await db.bank_transactions.find(
        {"company_id": company_id, "source": "amex"},
        {"_id": 0, "dedup_key": 1}
    ).to_list(10000)
    for d in existing_docs:
        if d.get("dedup_key"):
            existing_keys.add(d["dedup_key"])

    # Insertar movimientos nuevos
    for mov in movimientos:
        if mov["dedup_key"] in existing_keys:
            omitidos += 1
            continue

        doc = {
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "source": "amex",
            "es_real": True,
            "cuenta_bancaria": cuenta_nombre,
            "cuenta_banco": cuenta_nombre,
            "dedup_key": mov["dedup_key"],
            "fecha": mov["fecha"],
            "fecha_movimiento": mov["fecha"],
            "descripcion": mov["descripcion"],
            "contacto": "",
            "monto": mov["monto"],
            "tipo": mov["tipo"],
            "tipo_movimiento": "debito" if mov["es_cargo"] else "credito",
            "moneda": "MXN",
            "moneda_original": "MXN",
            "category_name": mov["categoria"],
            "conciliado": False,
            "alegra_id": "",
            "alegra_payment_id": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.bank_transactions.insert_one(doc)
        insertados += 1

    await audit_log(company_id, "AMEXImport", file.filename, "IMPORT", current_user["id"],
                    {"insertados": insertados, "omitidos": omitidos})

    return {
        "status": "ok",
        "insertados": insertados,
        "omitidos_duplicados": omitidos,
        "errores": errores[:10],
        "total_procesados": len(movimientos),
    }


@router.get("/transactions")
async def list_amex_transactions(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Lista todos los movimientos AMEX importados."""
    company_id = await get_active_company_id(request, current_user)
    docs = await db.bank_transactions.find(
        {"company_id": company_id, "source": "amex"},
        {"_id": 0}
    ).sort("fecha", -1).to_list(2000)
    return docs
