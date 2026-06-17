"""
Diagnóstico y limpieza de cashflow_weeks para company_id="89cda61e" (Ortech/Alegra).

Uso:
    # Con URL de Atlas (recomendado):
    $env:MONGO_URL = "mongodb+srv://user:pass@cluster.mongodb.net/"
    $env:DB_NAME   = "taxnfin_cashflow"
    python scripts/fix_cashflow_weeks.py

    # O con argumento directo:
    python scripts/fix_cashflow_weeks.py "mongodb+srv://..." "taxnfin_cashflow"
"""
import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

COMPANY_ID = "89cda61e"


async def main(mongo_url: str, db_name: str):
    from motor.motor_asyncio import AsyncIOMotorClient

    print(f"\nConectando a: {mongo_url[:40]}...")
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=8000)
    db = client[db_name]

    try:
        await client.admin.command('ping')
        print(f"[OK] Conectado a MongoDB -- base de datos: {db_name}\n")
    except Exception as e:
        print(f"[ERROR] Error de conexion: {e}")
        client.close()
        return

    sep = "=" * 70

    # ─────────────────────────────────────────────────────────────────────
    # 1. DIAGNÓSTICO — cashflow_weeks
    # ─────────────────────────────────────────────────────────────────────
    print(sep)
    print("1. DIAGNÓSTICO — db.cashflow_weeks")
    print(sep)

    weeks = await db.cashflow_weeks.find(
        {'company_id': COMPANY_ID}, {'_id': 0}
    ).sort('numero_semana', 1).to_list(200)

    print(f"Total semanas encontradas: {len(weeks)}\n")
    print(f"{'Sem':>4}  {'Label':<6}  {'Inicio':>12}  {'Fin':>12}  "
          f"{'Saldo Ini':>14}  {'Ingresos':>14}  {'Egresos':>14}  {'CFDIs':>6}")
    print("-" * 95)

    for w in weeks:
        num   = w.get('numero_semana', '?')
        label = w.get('label') or f"S{num}"
        fi    = str(w.get('fecha_inicio', ''))[:10]
        ff    = str(w.get('fecha_fin', ''))[:10]
        saldo = float(w.get('saldo_inicial', 0) or 0)
        ing   = float(w.get('total_ingresos', 0) or 0)
        egr   = float(w.get('total_egresos', 0) or 0)

        # Contar CFDIs Alegra en ese rango de fechas
        cfdi_count = 0
        if fi and ff:
            cfdi_count = await db.cfdis.count_documents({
                'company_id': COMPANY_ID,
                'source': 'alegra',
                'fecha_emision': {'$gte': fi, '$lte': ff},
            })

        print(f"{str(num):>4}  {label:<6}  {fi:>12}  {ff:>12}  "
              f"{saldo:>14,.2f}  {ing:>14,.2f}  {egr:>14,.2f}  {cfdi_count:>6}")

    # ─────────────────────────────────────────────────────────────────────
    # 2. LIMPIEZA — poner total_ingresos / total_egresos / flujo_neto = 0
    # ─────────────────────────────────────────────────────────────────────
    print(f"\n{sep}")
    print("2. LIMPIEZA — Zeroing total_ingresos / total_egresos / flujo_neto")
    print(sep)

    res = await db.cashflow_weeks.update_many(
        {'company_id': COMPANY_ID},
        {'$set': {
            'total_ingresos': 0,
            'total_egresos': 0,
            'flujo_neto': 0,
        }}
    )
    print(f"  Semanas actualizadas: {res.modified_count} / {res.matched_count} matched")
    print("  [OK] total_ingresos, total_egresos, flujo_neto -> 0 en todas las semanas")
    print("  (saldo_inicial no fue tocado)")

    # ─────────────────────────────────────────────────────────────────────
    # 3. DIAGNÓSTICO — CFDIs Alegra por tipo y mes
    # ─────────────────────────────────────────────────────────────────────
    print(f"\n{sep}")
    print("3. DIAGNÓSTICO — db.cfdis (source='alegra')")
    print(sep)

    pipeline_cfdis = [
        {'$match': {'company_id': COMPANY_ID, 'source': 'alegra'}},
        {'$addFields': {
            'mes': {'$substr': ['$fecha_emision', 0, 7]}
        }},
        {'$group': {
            '_id': {'tipo': '$tipo_cfdi', 'mes': '$mes'},
            'count': {'$sum': 1},
            'total': {'$sum': '$total'},
        }},
        {'$sort': {'_id.mes': 1, '_id.tipo': 1}},
    ]
    cfdis_agg = await db.cfdis.aggregate(pipeline_cfdis).to_list(500)

    total_docs = await db.cfdis.count_documents({'company_id': COMPANY_ID, 'source': 'alegra'})
    print(f"Total documentos Alegra en db.cfdis: {total_docs}\n")

    if cfdis_agg:
        print(f"  {'Tipo':<12}  {'Mes':<8}  {'Count':>6}  {'Total MXN':>14}")
        print("  " + "-" * 44)
        prev_mes = None
        for row in cfdis_agg:
            tipo = row['_id'].get('tipo', 'N/A') or 'N/A'
            mes  = row['_id'].get('mes', 'N/A') or 'N/A'
            if mes != prev_mes and prev_mes is not None:
                print()
            prev_mes = mes
            print(f"  {tipo:<12}  {mes:<8}  {row['count']:>6}  {row['total']:>14,.2f}")
    else:
        print("  (sin documentos)")

    # Diagnóstico extra: estados de conciliacion
    pipeline_estado = [
        {'$match': {'company_id': COMPANY_ID, 'source': 'alegra'}},
        {'$group': {'_id': '$estado_conciliacion', 'count': {'$sum': 1}}},
        {'$sort': {'_id': 1}},
    ]
    estados = await db.cfdis.aggregate(pipeline_estado).to_list(20)
    print(f"\n  Estados de conciliación:")
    for e in estados:
        print(f"    {str(e['_id']):<20}  {e['count']:>5}")

    # ─────────────────────────────────────────────────────────────────────
    # 4. DIAGNÓSTICO — Payments Alegra por tipo y mes
    # ─────────────────────────────────────────────────────────────────────
    print(f"\n{sep}")
    print("4. DIAGNÓSTICO — db.payments (source='alegra')")
    print(sep)

    pipeline_pays = [
        {'$match': {'company_id': COMPANY_ID, 'source': 'alegra'}},
        {'$addFields': {
            'mes': {'$substr': [{'$ifNull': ['$fecha_pago', '$fecha_vencimiento']}, 0, 7]}
        }},
        {'$group': {
            '_id': {'tipo': '$tipo', 'mes': '$mes'},
            'count': {'$sum': 1},
            'total': {'$sum': '$monto'},
        }},
        {'$sort': {'_id.mes': 1, '_id.tipo': 1}},
    ]
    pays_agg = await db.payments.aggregate(pipeline_pays).to_list(500)

    total_pays = await db.payments.count_documents({'company_id': COMPANY_ID, 'source': 'alegra'})
    print(f"Total pagos Alegra en db.payments: {total_pays}\n")

    if pays_agg:
        print(f"  {'Tipo':<10}  {'Mes':<8}  {'Count':>6}  {'Monto MXN':>14}")
        print("  " + "-" * 42)
        prev_mes = None
        for row in pays_agg:
            tipo = row['_id'].get('tipo', 'N/A') or 'N/A'
            mes  = row['_id'].get('mes', 'N/A') or 'N/A'
            if mes != prev_mes and prev_mes is not None:
                print()
            prev_mes = mes
            print(f"  {tipo:<10}  {mes:<8}  {row['count']:>6}  {row['total']:>14,.2f}")
    else:
        print("  (sin pagos)")

    # Diagnóstico extra: pagos con/sin facturas vinculadas
    con_facturas = await db.payments.count_documents({
        'company_id': COMPANY_ID,
        'source': 'alegra',
        'facturas_aplicadas': {'$exists': True, '$not': {'$size': 0}},
    })
    sin_facturas = await db.payments.count_documents({
        'company_id': COMPANY_ID,
        'source': 'alegra',
        '$or': [
            {'facturas_aplicadas': {'$exists': False}},
            {'facturas_aplicadas': {'$size': 0}},
        ],
    })
    print(f"\n  Pagos con facturas vinculadas: {con_facturas}")
    print(f"  Pagos sin facturas vinculadas: {sin_facturas}")

    print(f"\n{sep}")
    print("[OK] Script completado.")
    print(sep)
    client.close()


if __name__ == '__main__':
    # Prioridad: argumento CLI > env var > .env del proyecto
    if len(sys.argv) >= 3:
        mongo_url = sys.argv[1]
        db_name   = sys.argv[2]
    else:
        # Cargar .env del backend
        try:
            from dotenv import load_dotenv
            from pathlib import Path
            env_path = Path(__file__).parent.parent / '.env'
            load_dotenv(env_path)
        except ImportError:
            pass
        mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        db_name   = os.environ.get('DB_NAME', 'taxnfin_cashflow')

    asyncio.run(main(mongo_url, db_name))
