"""
Parser y endpoint para subir pagos históricos de Contalink
(reporte INGRESOS Y EGRESOS POR FORMA DE PAGO)
backend/routes/contalink_payments_upload.py
"""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Query
from typing import Dict, List
from datetime import datetime, timezone
import logging
import io

from core.database import db
from core.auth import get_current_user, get_active_company_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contalink-payments", tags=["Contalink Payments Upload"])


def _parse_ingr_egre(content: bytes) -> List[dict]:
    """
    Parsea el reporte 'INGRESOS Y EGRESOS POR FORMA DE PAGO' de Contalink.
    Estructura:
      Fila 0: Título
      Fila 1: Organización | Filtro de fecha
      Fila 3: Headers (DOCUMENTO, FECHA, DEPOSITOS, RETIROS)
      Fila 4+: Filas vacías en col0 + 'ID xxxxx' en col1 = movimiento
    Devuelve lista de payments listos para insertar en MongoDB.
    """
    try:
        import xlrd
        wb = xlrd.open_workbook(file_contents=content)
        ws = wb.sheet_by_index(0)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el archivo XLS: {str(e)}")

    payments = []
    current_payment = None

    for r in range(4, ws.nrows):
        col0 = str(ws.cell_value(r, 0)).strip()
        col1 = str(ws.cell_value(r, 1)).strip()
        col2 = str(ws.cell_value(r, 2)).strip()
        col3 = ws.cell_value(r, 3)  # FECHA
        col4 = str(ws.cell_value(r, 4)).strip()  # REFERENCIA
        col5 = ws.cell_value(r, 5) or 0  # DEPOSITOS
        col6 = ws.cell_value(r, 6) or 0  # RETIROS

        # Fila de movimiento principal (ID xxxxx)
        if col0 == '' and col1.startswith('ID '):
            # Guardar el anterior si existe
            if current_payment:
                payments.append(current_payment)

            # Parsear fecha
            fecha_str = None
            try:
                if isinstance(col3, float) and col3 > 0:
                    import xlrd as _xlrd
                    dt = _xlrd.xldate_as_datetime(col3, wb.datemode)
                    fecha_str = dt.strftime('%Y-%m-%d')
                elif isinstance(col3, str) and col3:
                    fecha_str = col3[:10]
            except:
                fecha_str = None

            deposito = float(col5) if col5 else 0.0
            retiro   = float(col6) if col6 else 0.0

            current_payment = {
                'contalink_id':   col1,           # 'ID 448259118'
                'fecha':          fecha_str,
                'deposito':       round(deposito, 2),
                'retiro':         round(retiro, 2),
                'tipo':           'cobro' if deposito > 0 else 'pago',
                'monto':          round(deposito if deposito > 0 else retiro, 2),
                'referencia':     col4 or '',
                'cfdis_aplicados': [],
                'descripcion':    '',
            }

        # Fila de detalle APLICADO A
        elif col0 == 'APLICADO A:' and current_payment:
            tipo_doc = col1  # 'CFDI ingreso', 'ND', etc
            folio    = col2  # número de folio
            monto_ap = float(col5) if col5 else (float(col6) if col6 else 0.0)

            current_payment['cfdis_aplicados'].append({
                'tipo':  tipo_doc,
                'folio': folio,
                'monto': round(monto_ap, 2),
            })

            # Construir descripción
            if folio and folio not in ['ND', '']:
                current_payment['descripcion'] = f"{tipo_doc} {folio}"

    # Agregar el último
    if current_payment:
        payments.append(current_payment)

    # Filtrar filas sin fecha o monto
    payments = [p for p in payments if p['fecha'] and (p['deposito'] > 0 or p['retiro'] > 0)]
    return payments


@router.post("/upload-historico")
async def upload_pagos_historicos(
    request: Request,
    file: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user),
):
    """
    Sube el reporte INGR-EGRE-FORMA-PAGO de Contalink para importar
    pagos históricos a la colección payments de MongoDB.
    Evita duplicados por contalink_id.
    """
    company_id = await get_active_company_id(request, current_user)

    if not file.filename.endswith(('.xls', '.xlsx')):
        raise HTTPException(status_code=400, detail="El archivo debe ser .xls o .xlsx")

    content = await file.read()

    try:
        payments = _parse_ingr_egre(content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parseando INGR-EGRE: {e}")
        raise HTTPException(status_code=400, detail=f"Error leyendo el archivo: {str(e)}")

    if not payments:
        raise HTTPException(status_code=400, detail="No se encontraron movimientos en el archivo")

    now = datetime.now(timezone.utc).isoformat()
    insertados = 0
    duplicados = 0

    for p in payments:
        # Evitar duplicados por contalink_id + company_id
        existing = await db.payments.find_one({
            'company_id':   company_id,
            'contalink_id': p['contalink_id'],
        })
        if existing:
            duplicados += 1
            continue

        # Mapear al esquema de payments de TaxnFin
        doc = {
            'company_id':       company_id,
            'contalink_id':     p['contalink_id'],
            'fecha':            p['fecha'],
            'fecha_pago':       p['fecha'],
            'fecha_vencimiento':p['fecha'],
            'monto':            p['monto'],
            'deposito':         p['deposito'],
            'retiro':           p['retiro'],
            'tipo':             p['tipo'],
            'descripcion':      p['descripcion'] or f"Movimiento {p['contalink_id']}",
            'referencia':       p['referencia'],
            'cfdis_aplicados':  p['cfdis_aplicados'],
            'fuente':           'contalink_excel',
            'moneda':           'MXN',
            'estatus':          'completado',
            'status':           'completado',
            'es_real':          True,
            'source':           'contalink',
            'created_at':       now,
            'updated_at':       now,
        }

        # Mes/año para agrupación
        try:
            dt = datetime.strptime(p['fecha'], '%Y-%m-%d')
            doc['mes']  = dt.month
            doc['anio'] = dt.year
            doc['periodo'] = dt.strftime('%Y-%m')
        except:
            pass

        await db.payments.insert_one(doc)
        insertados += 1

    # Resumen por mes
    resumen = {}
    for p in payments:
        mes = p['fecha'][:7] if p['fecha'] else 'desconocido'
        if mes not in resumen:
            resumen[mes] = {'cobros': 0, 'pagos': 0, 'count': 0}
        resumen[mes]['cobros'] += p['deposito']
        resumen[mes]['pagos']  += p['retiro']
        resumen[mes]['count']  += 1

    logger.info(f"[upload-historico] company={company_id} insertados={insertados} duplicados={duplicados}")

    return {
        'success':    True,
        'insertados': insertados,
        'duplicados': duplicados,
        'total':      len(payments),
        'resumen':    resumen,
        'message':    f'{insertados} movimientos importados ({duplicados} duplicados omitidos)',
    }


@router.get("/resumen-historico")
async def get_resumen_historico(
    request: Request,
    current_user: Dict = Depends(get_current_user),
):
    """Resumen de pagos históricos importados por mes."""
    company_id = await get_active_company_id(request, current_user)

    pipeline = [
        {'$match': {'company_id': company_id, 'fuente': 'contalink_excel'}},
        {'$group': {
            '_id':    '$periodo',
            'cobros': {'$sum': '$deposito'},
            'pagos':  {'$sum': '$retiro'},
            'count':  {'$sum': 1},
        }},
        {'$sort': {'_id': 1}},
    ]
    results = await db.payments.aggregate(pipeline).to_list(24)
    return {'periodos': results}
