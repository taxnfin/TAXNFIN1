import asyncio, sys
sys.stdout.reconfigure(encoding='utf-8')
from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGO_URL = os.environ.get('MONGODB_URL', 'mongodb+srv://taxnfin:taxnfin2024@cluster0.mongodb.net/taxnfin?retryWrites=true&w=majority')

async def main():
    # Leer la URL de MongoDB desde el .env
    env_path = 'backend/.env'
    mongo_url = None
    try:
        for line in open(env_path):
            if line.startswith('MONGODB_URL') or line.startswith('MONGO_URL'):
                mongo_url = line.split('=', 1)[1].strip().strip('"')
                break
    except:
        pass

    if not mongo_url:
        # Buscar en Railway env
        for name in ['MONGODB_URL', 'MONGO_URL', 'DATABASE_URL']:
            val = os.environ.get(name)
            if val and 'mongodb' in val:
                mongo_url = val
                break

    if not mongo_url:
        print("No encontre MONGO_URL — busco en .env.production o config.py")
        import glob
        for f in glob.glob('backend/**/*.env', recursive=True) + glob.glob('backend/**/*.py', recursive=True):
            try:
                content = open(f).read()
                if 'mongodb' in content.lower() and 'cluster' in content.lower():
                    print(f"Posible URL en: {f}")
                    for line in content.split('\n'):
                        if 'mongodb' in line.lower():
                            print(f"  {line[:100]}")
            except:
                pass
        return

    print(f"Conectando a MongoDB...")
    client = AsyncIOMotorClient(mongo_url)
    db = client.get_default_database()
    CID = '89cda61e-c9c3-4470-992b-48d3015e5cbd'

    # Buscar duplicados en bank_transactions por fecha + monto + tipo + contacto
    print("\n=== DUPLICADOS EN bank_transactions (Ortech) ===")
    pipeline = [
        {'$match': {'company_id': CID, 'source': 'alegra'}},
        {'$group': {
            '_id': {'fecha': '$fecha', 'monto': '$monto', 'tipo': '$tipo', 'contacto': '$contacto'},
            'count': {'$sum': 1},
            'ids': {'$push': '$id'}
        }},
        {'$match': {'count': {'$gt': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 10}
    ]
    dups = await db.bank_transactions.aggregate(pipeline).to_list(10)
    print(f"Grupos duplicados: {len(dups)}")
    for d in dups[:5]:
        print(f"  count={d['count']} fecha={d['_id'].get('fecha','')} monto={d['_id'].get('monto',0):,.2f} tipo={d['_id'].get('tipo','')} contacto={d['_id'].get('contacto','')[:30]}")

    # Total bank_transactions Alegra
    total = await db.bank_transactions.count_documents({'company_id': CID, 'source': 'alegra'})
    print(f"\nTotal bank_transactions Alegra: {total}")

    # Verificar S6 (02-09 feb) — por que tiene $3.1M ingresos
    from datetime import datetime
    s6_start = '2026-02-09'
    s6_end   = '2026-02-16'
    txns_s6 = await db.bank_transactions.find(
        {'company_id': CID, 'source': 'alegra', 'tipo': 'deposito',
         'fecha': {'$gte': s6_start, '$lt': s6_end}},
        {'_id': 0, 'fecha': 1, 'monto': 1, 'contacto': 1, 'category_name': 1, 'id': 1}
    ).sort('monto', -1).to_list(20)
    print(f"\n=== DEPOSITOS S6 ({s6_start} → {s6_end}) — top 10 ===")
    for t in txns_s6[:10]:
        print(f"  {t.get('fecha','')} ${t.get('monto',0):>12,.2f} [{t.get('category_name','')}] {t.get('contacto','')[:40]} id={t.get('id','')[:8]}")

    client.close()

asyncio.run(main())
