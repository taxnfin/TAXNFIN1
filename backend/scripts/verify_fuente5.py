"""
Diagnóstico: verifica que Fuente 5 (db.bank_transactions) tiene datos
para la empresa Ortech y muestra cómo quedarían distribuidos por semana.

Uso:
    cd backend
    python scripts/verify_fuente5.py
"""
import asyncio
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

COMPANY_ID_SHORT = "89cda61e"


async def main():
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        load_dotenv(Path(__file__).parent.parent / '.env')
    except ImportError:
        pass

    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name   = os.environ.get('DB_NAME', 'taxnfin_cashflow')

    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=8000)
    db = client[db_name]

    try:
        await client.admin.command('ping')
        print(f"[OK] Conectado a {db_name}\n")
    except Exception as e:
        print(f"[ERROR] {e}")
        client.close()
        return

    # 1. Resolver company_id completo
    company_full = await db.companies.find_one(
        {'id': {'$regex': f'^{COMPANY_ID_SHORT}'}}, {'_id': 0, 'id': 1, 'nombre': 1}
    )
    if not company_full:
        print(f"[ERROR] No se encontró empresa con id que empiece con '{COMPANY_ID_SHORT}'")
        client.close()
        return
    company_id = company_full['id']
    print(f"Empresa : {company_full.get('nombre', company_id)}")
    print(f"UUID    : {company_id}\n")

    sep = "=" * 70

    # 2. Contar docs Fuente 5 (query exacto de cashflow_calculator.py)
    print(sep)
    print("FUENTE 5 — db.bank_transactions (query exacto de cashflow_calculator)")
    print(sep)

    total = await db.bank_transactions.count_documents({
        'company_id': company_id,
        'source': 'alegra',
        'es_real': True,
    })
    print(f"Total docs encontrados: {total}")

    if total == 0:
        # Verificar si existen con el ID truncado
        total_trunc = await db.bank_transactions.count_documents({
            'company_id': COMPANY_ID_SHORT,
            'source': 'alegra',
        })
        print(f"Docs con company_id TRUNCADO ('{COMPANY_ID_SHORT}'): {total_trunc}")
        if total_trunc > 0:
            print("[PROBLEMA] Los docs aún tienen company_id truncado — el fix no se aplicó")
        client.close()
        return

    # 3. Distribución por tipo
    pipeline_tipo = [
        {'$match': {'company_id': company_id, 'source': 'alegra', 'es_real': True}},
        {'$group': {'_id': '$tipo', 'count': {'$sum': 1}, 'total_monto': {'$sum': '$monto'}}},
        {'$sort': {'_id': 1}},
    ]
    tipos = await db.bank_transactions.aggregate(pipeline_tipo).to_list(20)
    print(f"\n{'Tipo':<12}  {'Count':>6}  {'Monto Total':>16}")
    print("-" * 38)
    for t in tipos:
        print(f"{str(t['_id']):<12}  {t['count']:>6}  {t['total_monto']:>16,.2f}")

    # 4. Sample de docs para verificar campos
    print(f"\n{sep}")
    print("MUESTRA — primeros 3 docs (campos relevantes)")
    print(sep)
    sample = await db.bank_transactions.find(
        {'company_id': company_id, 'source': 'alegra', 'es_real': True},
        {'_id': 0, 'alegra_id': 1, 'fecha': 1, 'monto': 1, 'tipo': 1,
         'descripcion': 1, 'cuenta_bancaria': 1, 'conciliation_id': 1}
    ).limit(3).to_list(3)
    for doc in sample:
        print(doc)

    # 5. Distribución por semana (usando las cashflow_weeks de la empresa)
    print(f"\n{sep}")
    print("DISTRIBUCIÓN POR SEMANA (cashflow_weeks existentes)")
    print(sep)

    weeks = await db.cashflow_weeks.find(
        {'company_id': company_id}, {'_id': 0, 'numero_semana': 1, 'fecha_inicio': 1, 'fecha_fin': 1}
    ).sort('numero_semana', 1).to_list(60)

    # Leer todos los bank_transactions de Fuente 5
    import re
    def parse_date(val):
        if not val:
            return ''
        m = re.search(r'(\d{4}-\d{2}-\d{2})', str(val))
        return m.group(1) if m else ''

    bank_txns = await db.bank_transactions.find(
        {'company_id': company_id, 'source': 'alegra', 'es_real': True},
        {'_id': 0, 'tipo': 1, 'monto': 1, 'fecha': 1}
    ).to_list(10000)

    print(f"\n{'Sem':>4}  {'Inicio':>12}  {'Fin':>12}  {'Depositos':>12}  {'Retiros':>12}  {'Docs':>5}")
    print("-" * 65)
    total_dep = total_ret = 0
    for w in weeks:
        fi = parse_date(w.get('fecha_inicio'))
        ff = parse_date(w.get('fecha_fin'))
        if not fi or not ff:
            continue
        dep = sum(t['monto'] for t in bank_txns
                  if fi <= parse_date(t.get('fecha')) <= ff and t.get('tipo') == 'deposito')
        ret = sum(t['monto'] for t in bank_txns
                  if fi <= parse_date(t.get('fecha')) <= ff and t.get('tipo') == 'retiro')
        docs = sum(1 for t in bank_txns if fi <= parse_date(t.get('fecha')) <= ff)
        if dep > 0 or ret > 0:
            print(f"{w['numero_semana']:>4}  {fi:>12}  {ff:>12}  {dep:>12,.2f}  {ret:>12,.2f}  {docs:>5}")
            total_dep += dep
            total_ret += ret

    print("-" * 65)
    print(f"{'TOTAL':>4}  {'':>12}  {'':>12}  {total_dep:>12,.2f}  {total_ret:>12,.2f}")

    # 6. Verificar response_model issue
    print(f"\n{sep}")
    print("ADVERTENCIA — response_model en GET /cashflow/weeks")
    print(sep)
    print("CashFlowWeek en models/transaction.py tiene extra='ignore'")
    print("Los campos que calcula cashflow_calculator.py (total_ingresos,")
    print("ingresos_detalle, flujo_neto, etc.) NO están en ese modelo.")
    print("=> FastAPI los ELIMINA de la respuesta al cliente.")
    print("=> El endpoint /cashflow/weeks puede devolver zeros aunque Fuente 5 tenga datos.")
    print("\nSolución: cambiar response_model=None o usar response_model=List[dict] en cashflow.py")

    client.close()


if __name__ == '__main__':
    asyncio.run(main())
