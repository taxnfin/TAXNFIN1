from pymongo import MongoClient
from datetime import datetime, timezone
from pathlib import Path
import os, uuid, bcrypt

# Load .env when running locally
_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env)

MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGODB_URL")
if not MONGO_URL:
    raise SystemExit("ERROR: set MONGO_URL or MONGODB_URL env var")

DB_NAME = os.getenv("DB_NAME", "taxnfin_cashflow")
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

EMAIL = "hola@taxnfin.com"

existing = db.users.find_one({"email": EMAIL})
if existing:
    print(f"Usuario ya existe: {EMAIL}  (id={existing.get('id')})")
    raise SystemExit(0)

password = "TaxnFin2026!"
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
user_id = str(uuid.uuid4())

db.users.insert_one({
    "id":            user_id,
    "email":         EMAIL,
    "nombre":        "TaxnFin Admin",
    "password_hash": hashed,
    "role":          "admin",
    "company_id":    user_id,   # dummy — admin never accesses company data
    "company_ids":   [],
    "activo":        True,
    "created_at":    datetime.now(timezone.utc).isoformat(),
})
print(f"Admin creado: {EMAIL} / {password}  (id={user_id})")
print("IMPORTANTE: cambia la contraseña después del primer login.")
