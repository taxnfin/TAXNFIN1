"""
Diagnóstico: muestra campos de categoría de pagos reales en MongoDB.
Uso: python diagnose_payments.py
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import pymongo

load_dotenv(Path(__file__).parent / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME   = os.environ.get("DB_NAME", "taxnfin_cashflow")

client = pymongo.MongoClient(MONGO_URL)
db = client[DB_NAME]

# 1. Buscar empresa PRUEBA-CONTALINK (o la primera disponible)
company = db.companies.find_one(
    {"$or": [
        {"nombre": {"$regex": "contalink", "$options": "i"}},
        {"nombre": {"$regex": "prueba", "$options": "i"}},
    ]},
    {"_id": 0, "id": 1, "nombre": 1}
)
if not company:
    company = db.companies.find_one({}, {"_id": 0, "id": 1, "nombre": 1})

if not company:
    print("No se encontraron empresas.")
    client.close()
    exit()

company_id = company["id"]
print(f"\n=== EMPRESA ===")
print(f"  nombre:     {company['nombre']}")
print(f"  company_id: {company_id}")

# 2. Conteos
total      = db.payments.count_documents({"company_id": company_id})
con_cat_id = db.payments.count_documents({
    "company_id": company_id,
    "category_id": {"$exists": True, "$nin": [None, ""]}
})
con_cat_nm = db.payments.count_documents({
    "company_id": company_id,
    "category_name": {"$exists": True, "$nin": [None, ""]}
})
sin_cat = db.payments.count_documents({
    "company_id": company_id,
    "$or": [{"category_id": None}, {"category_id": {"$exists": False}}, {"category_id": ""}]
})

print(f"\n=== CONTEOS ===")
print(f"  Total pagos:              {total}")
print(f"  Con category_id válido:   {con_cat_id}")
print(f"  Con category_name válido: {con_cat_nm}")
print(f"  Sin categoría (filtro):   {sin_cat}")

# 3. Muestra 3 pagos
print(f"\n=== MUESTRA DE 3 PAGOS ===")
pagos = list(db.payments.find(
    {"company_id": company_id},
    {"_id": 0, "id": 1, "tipo": 1, "concepto": 1, "monto": 1,
     "category_id": 1, "category_name": 1, "source": 1, "cfdi_id": 1}
).limit(3))

for i, p in enumerate(pagos, 1):
    print(f"\n  Pago {i}:")
    print(f"    concepto:      {str(p.get('concepto',''))[:60]}")
    print(f"    source:        {p.get('source','(sin source)')}")
    print(f"    cfdi_id:       {p.get('cfdi_id','(ausente)')}")
    print(f"    category_id:   {repr(p.get('category_id', '(campo ausente)'))}")
    print(f"    category_name: {repr(p.get('category_name', '(campo ausente)'))}")

# 4. Pago sin categoría — todos sus campos
sin_cat_pago = db.payments.find_one(
    {"company_id": company_id,
     "$or": [{"category_id": None}, {"category_id": {"$exists": False}}, {"category_id": ""}]},
    {"_id": 0}
)
if sin_cat_pago:
    print(f"\n=== PAGO SIN CATEGORÍA (todos los campos) ===")
    for k, v in sin_cat_pago.items():
        print(f"    {k}: {str(v)[:80]}")
else:
    print(f"\n=== Todos los pagos tienen category_id ===")

# 5. Pago CON categoría — para ver el formato esperado
con_cat_pago = db.payments.find_one(
    {"company_id": company_id,
     "category_id": {"$exists": True, "$nin": [None, ""]}},
    {"_id": 0, "concepto": 1, "category_id": 1, "category_name": 1, "categorized_by": 1}
)
if con_cat_pago:
    print(f"\n=== PAGO CON CATEGORÍA (referencia) ===")
    for k, v in con_cat_pago.items():
        print(f"    {k}: {repr(v)}")
else:
    print(f"\n=== No hay pagos con category_id válido ===")

client.close()
