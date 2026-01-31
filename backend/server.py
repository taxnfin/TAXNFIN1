from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
from enum import Enum
import io
import openpyxl
from lxml import etree

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="TaxnFin Cashflow API", version="1.0.0")
api_router = APIRouter(prefix="/api")

# Import modular routers
from routes.auth import router as auth_router
from routes.companies import router as companies_router
from routes.categories import router as categories_router
from routes.vendors import router as vendors_router
from routes.customers import router as customers_router
from routes.bank_accounts import router as bank_accounts_router
from routes.payments import router as payments_router
from routes.reconciliations import router as reconciliations_router
from routes.cfdi import router as cfdi_router
from routes.fx_rates import router as fx_rates_router
from routes.bank_transactions import router as bank_transactions_router
from routes.sat import router as sat_router

# Include modular routers in api_router
api_router.include_router(auth_router)
api_router.include_router(companies_router)
api_router.include_router(categories_router)
api_router.include_router(vendors_router)
api_router.include_router(customers_router)
api_router.include_router(bank_accounts_router)
api_router.include_router(payments_router)
api_router.include_router(reconciliations_router)
api_router.include_router(cfdi_router)
api_router.include_router(fx_rates_router)
api_router.include_router(bank_transactions_router)
api_router.include_router(sat_router)

JWT_SECRET = os.environ.get('JWT_SECRET', 'taxnfin-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24 * 7

security = HTTPBearer()

class UserRole(str, Enum):
    ADMIN = "admin"
    CFO = "cfo"
    VIEWER = "viewer"

class TransactionType(str, Enum):
    INGRESO = "ingreso"
    EGRESO = "egreso"

class TransactionOrigin(str, Enum):
    BANCO = "banco"
    CSV = "csv"
    MANUAL = "manual"

class CFDIType(str, Enum):
    INGRESO = "ingreso"
    EGRESO = "egreso"
    PAGO = "pago"
    NOTA_CREDITO = "nota_credito"

class CFDIStatus(str, Enum):
    VIGENTE = "vigente"
    CANCELADO = "cancelado"

class BankTransactionType(str, Enum):
    CREDITO = "credito"
    DEBITO = "debito"

class ReconciliationMethod(str, Enum):
    AUTOMATICA = "automatica"
    MANUAL = "manual"

class ReconciliationStatus(str, Enum):
    PENDIENTE = "pendiente"
    CONCILIADO = "conciliado"
    NO_CONCILIABLE = "no_conciliable"

class CategoryType(str, Enum):
    INGRESO = "ingreso"
    EGRESO = "egreso"

# ===== CATEGORÍAS =====
class Category(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    nombre: str
    tipo: CategoryType  # ingreso o egreso
    color: str = "#6B7280"
    icono: str = "folder"
    activo: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CategoryCreate(BaseModel):
    nombre: str
    tipo: CategoryType
    color: str = "#6B7280"
    icono: str = "folder"

class SubCategory(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    category_id: str
    nombre: str
    activo: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SubCategoryCreate(BaseModel):
    category_id: str
    nombre: str

class Company(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    nombre: str
    rfc: str
    moneda_base: str = "MXN"
    pais: str = "México"
    activo: bool = True
    inicio_semana: int = 1  # 0=Domingo, 1=Lunes, 2=Martes, etc. Default: Lunes
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CompanyCreate(BaseModel):
    nombre: str
    rfc: str
    moneda_base: str = "MXN"
    pais: str = "México"
    inicio_semana: int = 1  # 0=Domingo, 1=Lunes, etc.

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    nombre: str
    role: UserRole = UserRole.VIEWER
    company_id: str
    activo: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nombre: str
    role: UserRole = UserRole.VIEWER
    company_id: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User

class BankAccount(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    nombre: str
    numero_cuenta: str
    banco: str
    moneda: str = "MXN"
    pais_banco: str = "México"
    saldo_inicial: float = 0.0
    fecha_saldo: Optional[datetime] = None  # Fecha del saldo inicial para tipo de cambio histórico
    activo: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BankAccountCreate(BaseModel):
    nombre: str
    numero_cuenta: str
    banco: str
    moneda: str = "MXN"
    pais_banco: str = "México"
    saldo_inicial: float = 0.0
    fecha_saldo: Optional[datetime] = None  # Fecha del saldo inicial para tipo de cambio histórico

class Vendor(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    nombre: str
    rfc: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    activo: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class VendorCreate(BaseModel):
    nombre: str
    rfc: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None

class Customer(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    nombre: str
    rfc: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    activo: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CustomerCreate(BaseModel):
    nombre: str
    rfc: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None

class CashFlowWeek(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    año: int
    numero_semana: int
    fecha_inicio: datetime
    fecha_fin: datetime
    saldo_inicial: float = 0.0
    total_ingresos_reales: float = 0.0
    total_egresos_reales: float = 0.0
    total_ingresos_proyectados: float = 0.0
    total_egresos_proyectados: float = 0.0
    saldo_final_real: float = 0.0
    saldo_final_proyectado: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Transaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    bank_account_id: str
    vendor_id: Optional[str] = None
    customer_id: Optional[str] = None
    category_id: Optional[str] = None
    subcategory_id: Optional[str] = None
    concepto: str
    monto: float
    moneda: str = "MXN"
    tipo_transaccion: TransactionType
    cashflow_week_id: str
    fecha_transaccion: datetime
    es_real: bool = False
    es_proyeccion: bool = True
    origen: TransactionOrigin = TransactionOrigin.MANUAL
    referencia: Optional[str] = None
    notas: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TransactionCreate(BaseModel):
    bank_account_id: str
    vendor_id: Optional[str] = None
    customer_id: Optional[str] = None
    category_id: Optional[str] = None
    subcategory_id: Optional[str] = None
    concepto: str
    monto: float
    moneda: str = "MXN"
    tipo_transaccion: TransactionType
    fecha_transaccion: datetime
    es_real: bool = False
    es_proyeccion: bool = True
    origen: TransactionOrigin = TransactionOrigin.MANUAL
    referencia: Optional[str] = None
    notas: Optional[str] = None

class FXRate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    moneda_base: str
    moneda_cotizada: str
    tipo_cambio: float
    fecha_vigencia: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class FXRateCreate(BaseModel):
    moneda_base: str
    moneda_cotizada: str
    tipo_cambio: float
    fecha_vigencia: datetime

class CFDI(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    uuid: str
    tipo_cfdi: CFDIType
    emisor_rfc: str
    emisor_nombre: Optional[str] = None
    receptor_rfc: str
    receptor_nombre: Optional[str] = None
    fecha_emision: datetime
    fecha_timbrado: datetime
    moneda: str = "MXN"
    subtotal: float
    descuento: float = 0.0
    impuestos: float
    total: float
    metodo_pago: Optional[str] = None  # PUE or PPD
    forma_pago: Optional[str] = None   # 01, 02, 03, etc.
    uso_cfdi: Optional[str] = None     # G01, G02, G03, etc.
    iva_trasladado: float = 0.0
    isr_retenido: float = 0.0
    iva_retenido: float = 0.0
    ieps: float = 0.0
    impuestos_locales: float = 0.0
    estatus: CFDIStatus = CFDIStatus.VIGENTE
    estado_cancelacion: Optional[str] = None  # vigente, cancelado
    xml_original: Optional[str] = None
    monto_cobrado: float = 0.0
    monto_pagado: float = 0.0
    category_id: Optional[str] = None
    subcategory_id: Optional[str] = None
    estado_conciliacion: str = "pendiente"
    customer_id: Optional[str] = None  # Para CFDIs de ingreso - asociar cliente
    vendor_id: Optional[str] = None    # Para CFDIs de egreso - asociar proveedor
    notas: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CFDICreate(BaseModel):
    uuid: str
    tipo_cfdi: CFDIType
    emisor_rfc: str
    emisor_nombre: Optional[str] = None
    receptor_rfc: str
    receptor_nombre: Optional[str] = None
    fecha_emision: datetime
    fecha_timbrado: datetime
    moneda: str = "MXN"
    subtotal: float
    impuestos: float
    total: float
    estatus: CFDIStatus = CFDIStatus.VIGENTE
    xml_original: Optional[str] = None

class BankTransaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    bank_account_id: str
    fecha_movimiento: datetime
    fecha_valor: datetime
    descripcion: str
    referencia: Optional[str] = None
    monto: float
    moneda: str = "MXN"
    tipo_movimiento: BankTransactionType
    saldo: float
    fuente: str = "manual"
    conciliado: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BankTransactionCreate(BaseModel):
    bank_account_id: str
    fecha_movimiento: datetime
    fecha_valor: datetime
    descripcion: str
    referencia: Optional[str] = None
    monto: float
    moneda: str = "MXN"
    tipo_movimiento: BankTransactionType
    saldo: float
    fuente: str = "manual"

class BankReconciliation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    bank_transaction_id: str
    transaction_id: Optional[str] = None
    cfdi_id: Optional[str] = None
    metodo_conciliacion: ReconciliationMethod
    tipo_conciliacion: str = "con_uuid"  # con_uuid, sin_uuid, no_relacionado
    porcentaje_match: float = 100.0
    fecha_conciliacion: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: str
    notas: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BankReconciliationCreate(BaseModel):
    bank_transaction_id: str
    transaction_id: Optional[str] = None
    cfdi_id: Optional[str] = None
    metodo_conciliacion: ReconciliationMethod
    tipo_conciliacion: str = "con_uuid"  # con_uuid, sin_uuid, no_relacionado
    porcentaje_match: float = 100.0
    notas: Optional[str] = None

class PaymentStatus(str, Enum):
    PENDIENTE = "pendiente"
    COMPLETADO = "completado"
    CANCELADO = "cancelado"
    VENCIDO = "vencido"

class PaymentMethod(str, Enum):
    TRANSFERENCIA = "transferencia"
    CHEQUE = "cheque"
    EFECTIVO = "efectivo"
    TARJETA = "tarjeta"
    DOMICILIACION = "domiciliacion"
    SPEI = "spei"

class Payment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    bank_account_id: Optional[str] = None
    cfdi_id: Optional[str] = None
    tipo: str  # "cobro" o "pago"
    concepto: str
    monto: float
    moneda: str = "MXN"
    tipo_cambio_historico: Optional[float] = None  # Exchange rate at time of payment
    metodo_pago: PaymentMethod
    fecha_vencimiento: datetime
    fecha_pago: Optional[datetime] = None
    estatus: PaymentStatus = PaymentStatus.PENDIENTE
    referencia: Optional[str] = None
    beneficiario: Optional[str] = None
    notas: Optional[str] = None
    domiciliacion_activa: bool = False
    es_real: bool = True  # True = movimiento real, False = proyección
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PaymentCreate(BaseModel):
    bank_account_id: Optional[str] = None
    cfdi_id: Optional[str] = None
    tipo: str
    concepto: str
    monto: float
    moneda: str = "MXN"
    tipo_cambio_historico: Optional[float] = None  # Exchange rate at time of payment
    metodo_pago: PaymentMethod
    fecha_vencimiento: datetime
    fecha_pago: Optional[datetime] = None
    estatus: PaymentStatus = PaymentStatus.PENDIENTE
    referencia: Optional[str] = None
    beneficiario: Optional[str] = None
    notas: Optional[str] = None
    domiciliacion_activa: bool = False
    es_real: bool = True  # True = movimiento real, False = proyección

# Concepto Manual de Proyección
class ManualProjectionConcept(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    nombre: str
    tipo: str  # "ingreso" o "egreso"
    monto: float
    moneda: str = "MXN"
    semana: Optional[int] = None  # Semana específica (1-13) o None si es para vista mensual
    mes: Optional[int] = None  # Mes (1-12) o None si es para vista semanal
    recurrente: bool = False  # Si aplica a todas las semanas/meses
    categoria: Optional[str] = None
    notas: Optional[str] = None
    activo: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ManualProjectionConceptCreate(BaseModel):
    nombre: str
    tipo: str  # "ingreso" o "egreso"
    monto: float
    moneda: str = "MXN"
    semana: Optional[int] = None
    mes: Optional[int] = None
    recurrente: bool = False
    categoria: Optional[str] = None
    notas: Optional[str] = None

class AuditLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    entidad: str
    entity_id: str
    accion: str
    user_id: str
    datos_anteriores: Optional[Dict[str, Any]] = None
    datos_nuevos: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ===== BELVO BANK CONNECTION MODELS =====
class BankConnectionStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    INVALID = "invalid"
    DISCONNECTED = "disconnected"

class BankConnection(BaseModel):
    """Represents a connection to a bank via Belvo"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    bank_account_id: str  # Reference to our bank_accounts table
    belvo_link_id: str  # Belvo's link ID
    institution_name: str  # Bank name (e.g., "BBVA Mexico")
    institution_id: str  # Belvo institution ID
    status: BankConnectionStatus = BankConnectionStatus.PENDING
    last_sync: Optional[datetime] = None
    sync_status: str = "never"  # never, syncing, success, error
    sync_error: Optional[str] = None
    credentials_encrypted: Optional[str] = None  # Encrypted bank credentials
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    activo: bool = True

class BankMovementRaw(BaseModel):
    """Raw bank movement from Belvo - before processing"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    bank_connection_id: str
    bank_account_id: str
    belvo_transaction_id: str  # Belvo's unique ID
    fecha_movimiento: datetime
    fecha_valor: Optional[datetime] = None
    descripcion: str
    referencia: Optional[str] = None
    monto: float
    tipo_movimiento: str  # credito or debito
    saldo: Optional[float] = None
    categoria_belvo: Optional[str] = None  # Belvo's category
    subcategoria_belvo: Optional[str] = None
    merchant_name: Optional[str] = None
    merchant_logo: Optional[str] = None
    moneda: str = "MXN"
    raw_data: Optional[Dict[str, Any]] = None  # Original Belvo response
    procesado: bool = False  # If already converted to bank_transaction
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_token(user_id: str, company_id: str, role: str) -> str:
    payload = {
        'user_id': user_id,
        'company_id': company_id,
        'role': role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({'id': payload['user_id']}, {'_id': 0, 'password_hash': 0})
        if not user or not user.get('activo'):
            raise HTTPException(status_code=401, detail="Usuario inválido")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")

from fastapi import Request

async def get_active_company_id(request: Request, current_user: Dict = Depends(get_current_user)) -> str:
    """Get the active company ID from header or fallback to user's company"""
    # Check for X-Company-ID header first
    company_id = request.headers.get('X-Company-ID')
    
    if company_id:
        # Verify user has access to this company (admin can access all, others only their own)
        if current_user['role'] == 'admin':
            # Verify company exists
            company = await db.companies.find_one({'id': company_id}, {'_id': 0})
            if company:
                return company_id
        elif company_id == current_user['company_id']:
            return company_id
    
    # Fallback to user's company
    return current_user['company_id']

async def audit_log(company_id: str, entidad: str, entity_id: str, accion: str, user_id: str, datos_anteriores: Optional[Dict] = None, datos_nuevos: Optional[Dict] = None):
    log = AuditLog(
        company_id=company_id,
        entidad=entidad,
        entity_id=entity_id,
        accion=accion,
        user_id=user_id,
        datos_anteriores=datos_anteriores,
        datos_nuevos=datos_nuevos
    )
    doc = log.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.audit_logs.insert_one(doc)

async def get_fx_rate_by_date(company_id: str, moneda: str, fecha: datetime = None) -> float:
    """Get the exchange rate for a specific currency and date.
    If no rate exists for that date, returns the closest previous rate.
    """
    if moneda == 'MXN':
        return 1.0
    
    # Default rates
    default_rates = {'USD': 17.50, 'EUR': 19.00, 'GBP': 23.00, 'CAD': 13.00, 'CHF': 22.00, 'CNY': 2.50, 'JPY': 0.12}
    
    if fecha is None:
        fecha = datetime.now(timezone.utc)
    
    # Get the rate for the specified date or closest previous date
    fecha_str = fecha.isoformat() if isinstance(fecha, datetime) else fecha
    
    rate_doc = await db.fx_rates.find_one(
        {
            'company_id': company_id,
            '$or': [
                {'moneda_origen': moneda},
                {'moneda_cotizada': moneda}
            ],
            'fecha_vigencia': {'$lte': fecha_str}
        },
        {'_id': 0},
        sort=[('fecha_vigencia', -1)]
    )
    
    if rate_doc:
        return rate_doc.get('tasa') or rate_doc.get('tipo_cambio') or default_rates.get(moneda, 1.0)
    
    # No historical rate found, try to get any rate for this currency
    any_rate = await db.fx_rates.find_one(
        {
            'company_id': company_id,
            '$or': [
                {'moneda_origen': moneda},
                {'moneda_cotizada': moneda}
            ]
        },
        {'_id': 0},
        sort=[('fecha_vigencia', -1)]
    )
    
    if any_rate:
        return any_rate.get('tasa') or any_rate.get('tipo_cambio') or default_rates.get(moneda, 1.0)
    
    return default_rates.get(moneda, 1.0)

async def initialize_cashflow_weeks(company_id: str):
    existing = await db.cashflow_weeks.find_one({'company_id': company_id})
    if existing:
        return
    
    today = datetime.now(timezone.utc)
    start_of_week = today - timedelta(days=today.weekday())
    
    for i in range(13):
        week_start = start_of_week + timedelta(weeks=i)
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        week = CashFlowWeek(
            company_id=company_id,
            año=week_start.year,
            numero_semana=week_start.isocalendar()[1],
            fecha_inicio=week_start,
            fecha_fin=week_end
        )
        doc = week.model_dump()
        for field in ['fecha_inicio', 'fecha_fin', 'created_at']:
            doc[field] = doc[field].isoformat()
        await db.cashflow_weeks.insert_one(doc)

def parse_cfdi_xml(xml_content: str) -> Dict[str, Any]:
    try:
        root = etree.fromstring(xml_content.encode('utf-8'))
        ns = {
            'cfdi': 'http://www.sat.gob.mx/cfd/4', 
            'cfdi3': 'http://www.sat.gob.mx/cfd/3',
            'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
            'nomina12': 'http://www.sat.gob.mx/nomina12'
        }
        
        # Detect CFDI version (3.3 or 4.0)
        cfdi_ns = 'cfdi' if root.tag.startswith('{http://www.sat.gob.mx/cfd/4}') else 'cfdi3'
        if cfdi_ns == 'cfdi3':
            ns['cfdi'] = 'http://www.sat.gob.mx/cfd/3'
        
        timbre = root.find('.//tfd:TimbreFiscalDigital', ns)
        uuid = timbre.get('UUID') if timbre is not None else None
        fecha_timbrado = timbre.get('FechaTimbrado') if timbre is not None else None
        
        emisor = root.find('cfdi:Emisor', ns)
        receptor = root.find('cfdi:Receptor', ns)
        
        # Map SAT codes to enum values
        tipo_comprobante_map = {
            'i': 'ingreso',
            'e': 'egreso', 
            'p': 'pago',
            'n': 'nomina',  # Nómina - Payroll
            't': 'ingreso'  # Traslado -> treat as ingreso
        }
        tipo_raw = root.get('TipoDeComprobante', 'I').lower()
        tipo_cfdi = tipo_comprobante_map.get(tipo_raw, 'ingreso')
        
        # If TipoDeComprobante is 'N' (Nómina), mark it specially
        es_nomina_por_tipo = tipo_raw == 'n'
        
        # Extract MetodoPago, FormaPago and other fields from XML
        metodo_pago = root.get('MetodoPago', '')  # PUE or PPD
        forma_pago = root.get('FormaPago', '')    # 01, 02, 03, etc.
        uso_cfdi = receptor.get('UsoCFDI', '') if receptor is not None else ''
        descuento = float(root.get('Descuento', 0) or 0)
        
        # Extract tax details from Impuestos node
        impuestos_node = root.find('cfdi:Impuestos', ns)
        total_impuestos_trasladados = float(impuestos_node.get('TotalImpuestosTrasladados', 0) or 0) if impuestos_node is not None else 0
        total_impuestos_retenidos = float(impuestos_node.get('TotalImpuestosRetenidos', 0) or 0) if impuestos_node is not None else 0
        
        # Extract individual tax amounts
        iva_trasladado = 0
        isr_retenido = 0
        iva_retenido = 0
        ieps = 0
        
        if impuestos_node is not None:
            # Traslados (IVA, IEPS)
            traslados = impuestos_node.find('cfdi:Traslados', ns)
            if traslados is not None:
                for traslado in traslados.findall('cfdi:Traslado', ns):
                    impuesto = traslado.get('Impuesto', '')
                    importe = float(traslado.get('Importe', 0) or 0)
                    if impuesto == '002':  # IVA
                        iva_trasladado += importe
                    elif impuesto == '003':  # IEPS
                        ieps += importe
            
            # Retenciones (ISR, IVA)
            retenciones = impuestos_node.find('cfdi:Retenciones', ns)
            if retenciones is not None:
                for retencion in retenciones.findall('cfdi:Retencion', ns):
                    impuesto = retencion.get('Impuesto', '')
                    importe = float(retencion.get('Importe', 0) or 0)
                    if impuesto == '001':  # ISR
                        isr_retenido += importe
                    elif impuesto == '002':  # IVA Retenido
                        iva_retenido += importe
        
        # Check for payroll (nómina) complement - ALWAYS treat as egreso
        nomina_element = root.find('.//nomina12:Nomina', ns)
        is_nomina = nomina_element is not None or es_nomina_por_tipo
        
        # Extract Nómina specific data if present
        nomina_data = {}
        if nomina_element is not None:
            nomina_data = {
                'fecha_pago': nomina_element.get('FechaPago', ''),
                'fecha_inicial_pago': nomina_element.get('FechaInicialPago', ''),
                'fecha_final_pago': nomina_element.get('FechaFinalPago', ''),
                'num_dias_pagados': nomina_element.get('NumDiasPagados', ''),
                'total_percepciones': float(nomina_element.get('TotalPercepciones', 0) or 0),
                'total_deducciones': float(nomina_element.get('TotalDeducciones', 0) or 0),
            }
        
        # Check for payroll keywords in concepts
        conceptos = root.findall('.//cfdi:Concepto', ns)
        conceptos_text = ' '.join([
            (c.get('Descripcion', '') + ' ' + c.get('ClaveProdServ', '')).lower() 
            for c in conceptos
        ])
        payroll_keywords = ['sueldo', 'salario', 'nómina', 'nomina', 'pago de nómina', 
                           'aguinaldo', 'liquidación', 'finiquito', '84111505']
        has_payroll_keywords = any(kw in conceptos_text for kw in payroll_keywords)
        
        return {
            'uuid': uuid,
            'tipo_cfdi': tipo_cfdi,
            'emisor_rfc': emisor.get('Rfc') if emisor is not None else '',
            'emisor_nombre': emisor.get('Nombre') if emisor is not None else '',
            'receptor_rfc': receptor.get('Rfc') if receptor is not None else '',
            'receptor_nombre': receptor.get('Nombre') if receptor is not None else '',
            'fecha_emision': root.get('Fecha'),
            'fecha_timbrado': fecha_timbrado,
            'moneda': root.get('Moneda', 'MXN'),
            'subtotal': float(root.get('SubTotal', 0)),
            'descuento': descuento,
            'total': float(root.get('Total', 0)),
            'metodo_pago': metodo_pago,
            'forma_pago': forma_pago,
            'uso_cfdi': uso_cfdi,
            'impuestos': total_impuestos_trasladados,
            'iva_trasladado': iva_trasladado,
            'isr_retenido': isr_retenido,
            'iva_retenido': iva_retenido,
            'ieps': ieps,
            'is_nomina': is_nomina or has_payroll_keywords,
            'nomina_data': nomina_data if nomina_data else None,
            'es_nomina_tipo_comprobante': es_nomina_por_tipo
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parseando XML CFDI: {str(e)}")

# ==================== AUTH ENDPOINTS MOVED TO routes/auth.py ====================
# The following endpoints are now handled by routes/auth.py:
# - POST /auth/register
# - POST /auth/login
# - GET /auth/me
# - GET /auth/auth0/config
# - GET /auth/auth0/login-url
# - POST /auth/auth0/callback
# - POST /auth/auth0/verify

# ==================== COMPANIES ENDPOINTS MOVED TO routes/companies.py ====================
# The following endpoints are now handled by routes/companies.py:
# - POST /companies
# - GET /companies
# - GET /companies/{company_id}
# - PUT /companies/{company_id}

# ==================== BANK-ACCOUNTS ENDPOINTS MOVED TO routes/bank_accounts.py ====================
# The following endpoints are now handled by routes/bank_accounts.py:
# - POST /bank-accounts
# - GET /bank-accounts
# - PUT /bank-accounts/{account_id}
# - DELETE /bank-accounts/{account_id}
# - GET /bank-accounts/summary


# ===== BELVO BANK INTEGRATION =====
# Belvo API configuration - set in .env or use sandbox for testing
BELVO_SECRET_ID = os.environ.get('BELVO_SECRET_ID', '')
BELVO_SECRET_PASSWORD = os.environ.get('BELVO_SECRET_PASSWORD', '')
BELVO_ENV = os.environ.get('BELVO_ENV', 'sandbox')  # sandbox or production

def get_belvo_client():
    """Initialize Belvo client"""
    if not BELVO_SECRET_ID or not BELVO_SECRET_PASSWORD:
        return None
    try:
        from belvo.client import Client
        env_url = 'sandbox' if BELVO_ENV == 'sandbox' else 'production'
        client = Client(BELVO_SECRET_ID, BELVO_SECRET_PASSWORD, env_url)
        return client
    except Exception as e:
        logger.error(f"Error initializing Belvo client: {e}")
        return None

@api_router.get("/belvo/status")
async def get_belvo_status(current_user: Dict = Depends(get_current_user)):
    """Check if Belvo is configured and connected"""
    client = get_belvo_client()
    configured = client is not None
    
    return {
        'configured': configured,
        'environment': BELVO_ENV if configured else None,
        'message': 'Belvo está configurado' if configured else 'Configura BELVO_SECRET_ID y BELVO_SECRET_PASSWORD en .env'
    }

@api_router.get("/belvo/institutions")
async def get_belvo_institutions(current_user: Dict = Depends(get_current_user)):
    """Get list of available Mexican bank institutions from Belvo"""
    client = get_belvo_client()
    if not client:
        raise HTTPException(status_code=400, detail="Belvo no está configurado. Agrega las credenciales en .env")
    
    try:
        # Get Mexican institutions that support transactions
        institutions = client.Institutions.list(country_codes='MX')
        
        # Filter for banks (retail) that support transactions
        banks = []
        for inst in institutions:
            if 'TRANSACTIONS' in inst.get('resources', []):
                banks.append({
                    'id': inst.get('name'),
                    'display_name': inst.get('display_name', inst.get('name')),
                    'type': inst.get('type'),
                    'country': inst.get('country_codes', ['MX'])[0] if inst.get('country_codes') else 'MX',
                    'logo': inst.get('logo'),
                    'primary_color': inst.get('primary_color'),
                    'resources': inst.get('resources', [])
                })
        
        return {'institutions': banks, 'count': len(banks)}
    except Exception as e:
        logger.error(f"Error fetching Belvo institutions: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo instituciones: {str(e)}")

@api_router.post("/belvo/connect")
async def create_belvo_connection(
    data: dict,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Create a new bank connection via Belvo"""
    company_id = await get_active_company_id(request, current_user)
    client = get_belvo_client()
    
    if not client:
        raise HTTPException(status_code=400, detail="Belvo no está configurado")
    
    institution_id = data.get('institution_id')
    bank_account_id = data.get('bank_account_id')  # Our internal bank account ID
    username = data.get('username')
    password = data.get('password')
    
    if not all([institution_id, bank_account_id, username, password]):
        raise HTTPException(status_code=400, detail="Se requieren institution_id, bank_account_id, username y password")
    
    # Verify bank account belongs to company
    bank_account = await db.bank_accounts.find_one({'id': bank_account_id, 'company_id': company_id}, {'_id': 0})
    if not bank_account:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    
    try:
        # Register the link with Belvo
        link = client.Links.create(
            institution=institution_id,
            username=username,
            password=password,
            access_mode='recurrent'  # For automatic updates
        )
        
        if not link:
            raise HTTPException(status_code=500, detail="Error creando conexión con el banco")
        
        # Create bank connection record
        connection = BankConnection(
            company_id=company_id,
            bank_account_id=bank_account_id,
            belvo_link_id=link.get('id'),
            institution_name=link.get('institution', institution_id),
            institution_id=institution_id,
            status='active' if link.get('status') == 'valid' else 'pending'
        )
        
        doc = connection.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        if doc.get('last_sync'):
            doc['last_sync'] = doc['last_sync'].isoformat()
        
        await db.bank_connections.insert_one(doc)
        
        # Update bank account with connection reference
        await db.bank_accounts.update_one(
            {'id': bank_account_id},
            {'$set': {'belvo_connection_id': connection.id, 'belvo_link_id': link.get('id')}}
        )
        
        await audit_log(company_id, 'BankConnection', connection.id, 'CREATE', current_user['id'])
        
        return {
            'status': 'success',
            'connection_id': connection.id,
            'link_id': link.get('id'),
            'message': 'Conexión bancaria creada exitosamente'
        }
        
    except Exception as e:
        logger.error(f"Error creating Belvo connection: {e}")
        raise HTTPException(status_code=500, detail=f"Error conectando con el banco: {str(e)}")

@api_router.get("/belvo/connections")
async def list_belvo_connections(request: Request, current_user: Dict = Depends(get_current_user)):
    """List all bank connections for the company"""
    company_id = await get_active_company_id(request, current_user)
    
    connections = await db.bank_connections.find({'company_id': company_id, 'activo': True}, {'_id': 0}).to_list(100)
    
    # Enrich with bank account info
    for conn in connections:
        bank_account = await db.bank_accounts.find_one({'id': conn.get('bank_account_id')}, {'_id': 0})
        if bank_account:
            conn['bank_account_name'] = bank_account.get('nombre')
            conn['bank_account_number'] = bank_account.get('numero_cuenta')
            conn['banco'] = bank_account.get('banco')
    
    return connections

@api_router.post("/belvo/sync/{connection_id}")
async def sync_belvo_transactions(
    connection_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
    date_from: str = None,
    date_to: str = None
):
    """Sync transactions from Belvo for a specific connection"""
    company_id = await get_active_company_id(request, current_user)
    client = get_belvo_client()
    
    if not client:
        raise HTTPException(status_code=400, detail="Belvo no está configurado")
    
    # Get connection
    connection = await db.bank_connections.find_one({
        'id': connection_id, 
        'company_id': company_id
    }, {'_id': 0})
    
    if not connection:
        raise HTTPException(status_code=404, detail="Conexión no encontrada")
    
    link_id = connection.get('belvo_link_id')
    bank_account_id = connection.get('bank_account_id')
    
    # Update sync status
    await db.bank_connections.update_one(
        {'id': connection_id},
        {'$set': {'sync_status': 'syncing'}}
    )
    
    try:
        # Set date range (default last 30 days)
        if not date_from:
            date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not date_to:
            date_to = datetime.now().strftime('%Y-%m-%d')
        
        # Fetch transactions from Belvo
        transactions = client.Transactions.create(
            link=link_id,
            date_from=date_from,
            date_to=date_to
        )
        
        if not transactions:
            transactions = []
        
        # Get bank account currency
        bank_account = await db.bank_accounts.find_one({'id': bank_account_id}, {'_id': 0})
        moneda = bank_account.get('moneda', 'MXN') if bank_account else 'MXN'
        
        imported = 0
        duplicates = 0
        
        for txn in transactions:
            belvo_id = txn.get('id')
            
            # Check for duplicate
            existing = await db.bank_movements_raw.find_one({
                'belvo_transaction_id': belvo_id,
                'company_id': company_id
            })
            
            if existing:
                duplicates += 1
                continue
            
            # Determine transaction type
            amount = txn.get('amount', 0)
            tipo = 'credito' if amount > 0 else 'debito'
            
            # Create raw movement record
            movement = BankMovementRaw(
                company_id=company_id,
                bank_connection_id=connection_id,
                bank_account_id=bank_account_id,
                belvo_transaction_id=belvo_id,
                fecha_movimiento=datetime.fromisoformat(txn.get('value_date', txn.get('accounting_date', datetime.now().isoformat())).replace('Z', '+00:00')),
                fecha_valor=datetime.fromisoformat(txn.get('value_date', datetime.now().isoformat()).replace('Z', '+00:00')) if txn.get('value_date') else None,
                descripcion=txn.get('description', ''),
                referencia=txn.get('reference', ''),
                monto=abs(amount),
                tipo_movimiento=tipo,
                saldo=txn.get('balance', 0),
                categoria_belvo=txn.get('category'),
                subcategoria_belvo=txn.get('subcategory'),
                merchant_name=txn.get('merchant', {}).get('name') if txn.get('merchant') else None,
                moneda=moneda,
                raw_data=txn
            )
            
            doc = movement.model_dump()
            doc['fecha_movimiento'] = doc['fecha_movimiento'].isoformat()
            if doc.get('fecha_valor'):
                doc['fecha_valor'] = doc['fecha_valor'].isoformat()
            doc['created_at'] = doc['created_at'].isoformat()
            
            await db.bank_movements_raw.insert_one(doc)
            imported += 1
        
        # Update connection
        await db.bank_connections.update_one(
            {'id': connection_id},
            {'$set': {
                'last_sync': datetime.now(timezone.utc).isoformat(),
                'sync_status': 'success',
                'sync_error': None
            }}
        )
        
        return {
            'status': 'success',
            'imported': imported,
            'duplicates': duplicates,
            'total_fetched': len(transactions),
            'message': f'Sincronización completada: {imported} nuevos movimientos'
        }
        
    except Exception as e:
        logger.error(f"Error syncing Belvo transactions: {e}")
        await db.bank_connections.update_one(
            {'id': connection_id},
            {'$set': {'sync_status': 'error', 'sync_error': str(e)}}
        )
        raise HTTPException(status_code=500, detail=f"Error sincronizando: {str(e)}")

@api_router.get("/belvo/movements-raw")
async def list_raw_movements(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    limit: int = Query(100, le=1000),
    procesado: bool = None
):
    """List raw bank movements from Belvo"""
    company_id = await get_active_company_id(request, current_user)
    
    query = {'company_id': company_id}
    if procesado is not None:
        query['procesado'] = procesado
    
    movements = await db.bank_movements_raw.find(query, {'_id': 0}).sort('fecha_movimiento', -1).limit(limit).to_list(limit)
    return movements

@api_router.post("/belvo/movements-raw/{movement_id}/process")
async def process_raw_movement(
    movement_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Convert a raw Belvo movement into a bank_transaction"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get raw movement
    raw = await db.bank_movements_raw.find_one({
        'id': movement_id,
        'company_id': company_id
    }, {'_id': 0})
    
    if not raw:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    if raw.get('procesado'):
        raise HTTPException(status_code=400, detail="Este movimiento ya fue procesado")
    
    # Create bank transaction from raw movement
    txn_id = str(uuid.uuid4())
    txn_doc = {
        'id': txn_id,
        'company_id': company_id,
        'bank_account_id': raw.get('bank_account_id'),
        'fecha_movimiento': raw.get('fecha_movimiento'),
        'fecha_valor': raw.get('fecha_valor'),
        'descripcion': raw.get('descripcion'),
        'referencia': raw.get('referencia'),
        'monto': raw.get('monto'),
        'tipo_movimiento': raw.get('tipo_movimiento'),
        'saldo': raw.get('saldo'),
        'moneda': raw.get('moneda', 'MXN'),
        'fuente': 'belvo',
        'belvo_movement_id': movement_id,
        'categoria': raw.get('categoria_belvo'),
        'merchant_name': raw.get('merchant_name'),
        'conciliado': False,
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    await db.bank_transactions.insert_one(txn_doc)
    
    # Mark raw movement as processed
    await db.bank_movements_raw.update_one(
        {'id': movement_id},
        {'$set': {'procesado': True}}
    )
    
    return {
        'status': 'success',
        'transaction_id': txn_id,
        'message': 'Movimiento procesado y agregado a transacciones bancarias'
    }

@api_router.post("/belvo/movements-raw/process-all")
async def process_all_raw_movements(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Process all unprocessed raw movements into bank_transactions"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get all unprocessed movements
    raw_movements = await db.bank_movements_raw.find({
        'company_id': company_id,
        'procesado': False
    }, {'_id': 0}).to_list(10000)
    
    processed = 0
    errors = 0
    
    for raw in raw_movements:
        try:
            txn_id = str(uuid.uuid4())
            txn_doc = {
                'id': txn_id,
                'company_id': company_id,
                'bank_account_id': raw.get('bank_account_id'),
                'fecha_movimiento': raw.get('fecha_movimiento'),
                'fecha_valor': raw.get('fecha_valor'),
                'descripcion': raw.get('descripcion'),
                'referencia': raw.get('referencia'),
                'monto': raw.get('monto'),
                'tipo_movimiento': raw.get('tipo_movimiento'),
                'saldo': raw.get('saldo'),
                'moneda': raw.get('moneda', 'MXN'),
                'fuente': 'belvo',
                'belvo_movement_id': raw.get('id'),
                'categoria': raw.get('categoria_belvo'),
                'merchant_name': raw.get('merchant_name'),
                'conciliado': False,
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            await db.bank_transactions.insert_one(txn_doc)
            await db.bank_movements_raw.update_one(
                {'id': raw.get('id')},
                {'$set': {'procesado': True}}
            )
            processed += 1
        except Exception as e:
            logger.error(f"Error processing movement {raw.get('id')}: {e}")
            errors += 1
    
    return {
        'status': 'success',
        'processed': processed,
        'errors': errors,
        'message': f'Se procesaron {processed} movimientos'
    }

@api_router.delete("/belvo/connections/{connection_id}")
async def delete_belvo_connection(
    connection_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Delete a bank connection"""
    company_id = await get_active_company_id(request, current_user)
    client = get_belvo_client()
    
    # Get connection
    connection = await db.bank_connections.find_one({
        'id': connection_id,
        'company_id': company_id
    }, {'_id': 0})
    
    if not connection:
        raise HTTPException(status_code=404, detail="Conexión no encontrada")
    
    # Try to delete from Belvo
    if client and connection.get('belvo_link_id'):
        try:
            client.Links.delete(connection.get('belvo_link_id'))
        except Exception as e:
            logger.warning(f"Could not delete Belvo link: {e}")
    
    # Mark as inactive
    await db.bank_connections.update_one(
        {'id': connection_id},
        {'$set': {'activo': False, 'status': 'disconnected'}}
    )
    
    # Remove reference from bank account
    await db.bank_accounts.update_one(
        {'id': connection.get('bank_account_id')},
        {'$unset': {'belvo_connection_id': '', 'belvo_link_id': ''}}
    )
    
    await audit_log(company_id, 'BankConnection', connection_id, 'DELETE', current_user['id'])
    
    return {'status': 'success', 'message': 'Conexión eliminada'}

# ==================== VENDORS/CUSTOMERS ENDPOINTS MOVED TO routes/vendors.py & routes/customers.py ====================
# Basic CRUD endpoints are now handled by the modular routers:
# Vendors: POST, GET, PUT /{id}, DELETE /{id}
# Customers: POST, GET, PUT /{id}, DELETE /{id}
# 
# The import/template endpoints below remain here for now:

# ===== PLANTILLAS E IMPORTACIÓN MASIVA =====

@api_router.get("/vendors/template")
async def download_vendors_template():
    """Download Excel template for importing vendors"""
    from openpyxl import Workbook
    from fastapi.responses import StreamingResponse
    import io
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Proveedores"
    
    # Headers
    headers = ['nombre', 'rfc', 'email', 'telefono', 'direccion', 'condiciones_pago', 'notas']
    ws.append(headers)
    
    # Example rows
    ws.append(['Proveedor Ejemplo SA de CV', 'PEJ123456ABC', 'contacto@proveedor.com', '5512345678', 'Av. Ejemplo 123, CDMX', '30 días', 'Proveedor de materiales'])
    ws.append(['Servicios Profesionales SA', 'SPS987654XYZ', 'info@servicios.com', '5587654321', 'Calle Servicios 456', '15 días', 'Servicios de consultoría'])
    
    # Style headers
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col)
        cell.font = cell.font.copy(bold=True)
        ws.column_dimensions[cell.column_letter].width = 20
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_proveedores.xlsx"}
    )

@api_router.get("/customers/template")
async def download_customers_template():
    """Download Excel template for importing customers"""
    from openpyxl import Workbook
    from fastapi.responses import StreamingResponse
    import io
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Clientes"
    
    # Headers
    headers = ['nombre', 'rfc', 'email', 'telefono', 'direccion', 'limite_credito', 'notas']
    ws.append(headers)
    
    # Example rows
    ws.append(['Cliente Ejemplo SA de CV', 'CEJ123456ABC', 'compras@cliente.com', '5512345678', 'Av. Cliente 123, CDMX', '100000', 'Cliente frecuente'])
    ws.append(['Comercializadora XYZ SA', 'CXY987654XYZ', 'pagos@xyz.com', '5587654321', 'Calle Comercio 456', '50000', 'Nuevo cliente'])
    
    # Style headers
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col)
        cell.font = cell.font.copy(bold=True)
        ws.column_dimensions[cell.column_letter].width = 20
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_clientes.xlsx"}
    )

@api_router.post("/vendors/import")
async def import_vendors(request: Request, file: UploadFile = File(...), current_user: Dict = Depends(get_current_user)):
    """Import vendors from Excel file"""
    from openpyxl import load_workbook
    import io
    
    company_id = await get_active_company_id(request, current_user)
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos Excel (.xlsx)")
    
    content = await file.read()
    wb = load_workbook(io.BytesIO(content))
    ws = wb.active
    
    imported = 0
    updated = 0
    errors = []
    
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row[0]:  # Skip empty rows
            continue
        
        try:
            nombre = str(row[0]).strip()
            rfc = str(row[1]).strip().upper() if row[1] else None
            
            vendor_data = {
                'nombre': nombre,
                'rfc': rfc,
                'email': str(row[2]).strip() if row[2] else None,
                'telefono': str(row[3]).strip() if row[3] else None,
                'direccion': str(row[4]).strip() if row[4] else None,
                'condiciones_pago': str(row[5]).strip() if len(row) > 5 and row[5] else None,
                'notas': str(row[6]).strip() if len(row) > 6 and row[6] else None
            }
            
            # Check if vendor with same RFC exists
            existing = await db.vendors.find_one({'company_id': company_id, 'rfc': rfc}, {'_id': 0}) if rfc else None
            
            if existing:
                # Update existing
                await db.vendors.update_one(
                    {'id': existing['id']},
                    {'$set': vendor_data}
                )
                updated += 1
            else:
                # Create new
                vendor = Vendor(company_id=company_id, **vendor_data)
                doc = vendor.model_dump()
                doc['created_at'] = doc['created_at'].isoformat()
                await db.vendors.insert_one(doc)
                imported += 1
                
        except Exception as e:
            errors.append(f"Fila {idx}: {str(e)}")
    
    await audit_log(company_id, 'Vendor', 'BULK', 'IMPORT', current_user['id'])
    
    return {
        'status': 'success',
        'imported': imported,
        'updated': updated,
        'errors': errors
    }

@api_router.post("/customers/import")
async def import_customers(request: Request, file: UploadFile = File(...), current_user: Dict = Depends(get_current_user)):
    """Import customers from Excel file"""
    from openpyxl import load_workbook
    import io
    
    company_id = await get_active_company_id(request, current_user)
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos Excel (.xlsx)")
    
    content = await file.read()
    wb = load_workbook(io.BytesIO(content))
    ws = wb.active
    
    imported = 0
    updated = 0
    errors = []
    
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row[0]:  # Skip empty rows
            continue
        
        try:
            nombre = str(row[0]).strip()
            rfc = str(row[1]).strip().upper() if row[1] else None
            
            customer_data = {
                'nombre': nombre,
                'rfc': rfc,
                'email': str(row[2]).strip() if row[2] else None,
                'telefono': str(row[3]).strip() if row[3] else None,
                'direccion': str(row[4]).strip() if row[4] else None,
                'limite_credito': float(row[5]) if len(row) > 5 and row[5] else 0,
                'notas': str(row[6]).strip() if len(row) > 6 and row[6] else None
            }
            
            # Check if customer with same RFC exists
            existing = await db.customers.find_one({'company_id': company_id, 'rfc': rfc}, {'_id': 0}) if rfc else None
            
            if existing:
                # Update existing
                await db.customers.update_one(
                    {'id': existing['id']},
                    {'$set': customer_data}
                )
                updated += 1
            else:
                # Create new
                customer = Customer(company_id=company_id, **customer_data)
                doc = customer.model_dump()
                doc['created_at'] = doc['created_at'].isoformat()
                await db.customers.insert_one(doc)
                imported += 1
                
        except Exception as e:
            errors.append(f"Fila {idx}: {str(e)}")
    
    await audit_log(company_id, 'Customer', 'BULK', 'IMPORT', current_user['id'])
    
    return {
        'status': 'success',
        'imported': imported,
        'updated': updated,
        'errors': errors
    }

@api_router.post("/cfdi/{cfdi_id}/create-party")
async def create_party_from_cfdi(
    cfdi_id: str,
    party_type: str = Query(..., description="'customer' or 'vendor'"),
    nombre: str = Query(...),
    rfc: str = Query(...),
    request: Request = None,
    current_user: Dict = Depends(get_current_user)
):
    """Create a customer or vendor from CFDI data and link it"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get the CFDI
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    if party_type == 'customer':
        # Check if already exists
        existing = await db.customers.find_one({
            'company_id': company_id,
            'rfc': {'$regex': f'^{rfc}$', '$options': 'i'}
        }, {'_id': 0, 'id': 1})
        
        if existing:
            # Link existing
            await db.cfdis.update_one({'id': cfdi_id}, {'$set': {'customer_id': existing['id']}})
            return {'status': 'linked', 'party_id': existing['id'], 'message': 'Cliente existente vinculado'}
        
        # Create new customer
        customer = Customer(company_id=company_id, nombre=nombre, rfc=rfc.upper())
        doc = customer.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.customers.insert_one(doc)
        
        # Link to CFDI
        await db.cfdis.update_one({'id': cfdi_id}, {'$set': {'customer_id': customer.id}})
        await audit_log(company_id, 'Customer', customer.id, 'CREATE_FROM_CFDI', current_user['id'])
        
        return {
            'status': 'created',
            'party_id': customer.id,
            'party_type': 'customer',
            'nombre': nombre,
            'rfc': rfc,
            'message': f'Cliente "{nombre}" creado y vinculado'
        }
    
    elif party_type == 'vendor':
        # Check if already exists
        existing = await db.vendors.find_one({
            'company_id': company_id,
            'rfc': {'$regex': f'^{rfc}$', '$options': 'i'}
        }, {'_id': 0, 'id': 1})
        
        if existing:
            # Link existing
            await db.cfdis.update_one({'id': cfdi_id}, {'$set': {'vendor_id': existing['id']}})
            return {'status': 'linked', 'party_id': existing['id'], 'message': 'Proveedor existente vinculado'}
        
        # Create new vendor
        vendor = Vendor(company_id=company_id, nombre=nombre, rfc=rfc.upper())
        doc = vendor.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.vendors.insert_one(doc)
        
        # Link to CFDI
        await db.cfdis.update_one({'id': cfdi_id}, {'$set': {'vendor_id': vendor.id}})
        await audit_log(company_id, 'Vendor', vendor.id, 'CREATE_FROM_CFDI', current_user['id'])
        
        return {
            'status': 'created',
            'party_id': vendor.id,
            'party_type': 'vendor',
            'nombre': nombre,
            'rfc': rfc,
            'message': f'Proveedor "{nombre}" creado y vinculado'
        }
    
    else:
        raise HTTPException(status_code=400, detail="party_type debe ser 'customer' o 'vendor'")

@api_router.get("/cashflow/weeks", response_model=List[CashFlowWeek])
async def get_cashflow_weeks(request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    weeks = await db.cashflow_weeks.find({'company_id': company_id}, {'_id': 0}).sort('fecha_inicio', 1).to_list(13)
    
    # If no weeks exist, generate them dynamically
    if not weeks:
        today = datetime.now(timezone.utc)
        start_of_current_week = today - timedelta(days=today.weekday())
        
        weeks = []
        for i in range(13):
            week_start = start_of_current_week + timedelta(weeks=i)
            week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
            weeks.append({
                'id': str(uuid.uuid4()),
                'company_id': company_id,
                'año': week_start.year,
                'numero_semana': week_start.isocalendar()[1],
                'fecha_inicio': week_start,
                'fecha_fin': week_end,
                'total_ingresos_reales': 0,
                'total_egresos_reales': 0,
                'total_ingresos_proyectados': 0,
                'total_egresos_proyectados': 0,
                'saldo_inicial': 0,
                'saldo_final_real': 0,
                'saldo_final_proyectado': 0,
                'created_at': today
            })
    
    # Get FX rates for conversion
    fx_rates = await db.fx_rates.find(
        {'company_id': company_id},
        {'_id': 0, 'moneda_origen': 1, 'moneda_destino': 1, 'tasa': 1}
    ).sort('fecha_vigencia', -1).to_list(100)
    
    # Build FX rates map
    fx_map = {'MXN': 1.0}
    for rate in fx_rates:
        if rate.get('moneda_destino') == 'MXN':
            fx_map[rate['moneda_origen']] = rate['tasa']
        elif rate.get('moneda_origen') == 'MXN':
            fx_map[rate['moneda_destino']] = 1 / rate['tasa']
    
    if 'USD' not in fx_map:
        fx_map['USD'] = 17.50
    if 'EUR' not in fx_map:
        fx_map['EUR'] = 19.00
    
    # Get initial balance from bank accounts with historical rates
    bank_accounts = await db.bank_accounts.find({'company_id': company_id, 'activo': True}, {'_id': 0}).to_list(100)
    saldo_inicial_total = 0.0
    for acc in bank_accounts:
        saldo = acc.get('saldo_inicial', 0)
        moneda = acc.get('moneda', 'MXN')
        fecha_saldo = acc.get('fecha_saldo')
        
        # Use historical rate if fecha_saldo is available
        if fecha_saldo:
            if isinstance(fecha_saldo, str):
                fecha_saldo = datetime.fromisoformat(fecha_saldo.replace('Z', '+00:00'))
            tasa = await get_fx_rate_by_date(company_id, moneda, fecha_saldo)
        else:
            tasa = fx_map.get(moneda, 1.0)
        
        saldo_inicial_total += saldo * tasa
    
    # Get CFDIs for calculating real inflows/outflows per week
    cfdis = await db.cfdis.find({'company_id': company_id}, {'_id': 0}).to_list(1000)
    
    # Track running balance
    running_balance = saldo_inicial_total
    
    for i, week in enumerate(weeks):
        for field in ['fecha_inicio', 'fecha_fin', 'created_at']:
            if isinstance(week.get(field), str):
                week[field] = datetime.fromisoformat(week[field].replace('Z', '+00:00'))
            # Ensure timezone aware
            if week.get(field) and week[field].tzinfo is None:
                week[field] = week[field].replace(tzinfo=timezone.utc)
        
        week_start = week['fecha_inicio']
        week_end = week['fecha_fin']
        
        # Calculate from CFDIs
        week_ingresos = 0
        week_egresos = 0
        for cfdi in cfdis:
            cfdi_date = cfdi.get('fecha_emision')
            if isinstance(cfdi_date, str):
                cfdi_date = datetime.fromisoformat(cfdi_date.replace('Z', '+00:00'))
            if cfdi_date and cfdi_date.tzinfo is None:
                cfdi_date = cfdi_date.replace(tzinfo=timezone.utc)
            
            if cfdi_date and week_start <= cfdi_date <= week_end:
                if cfdi.get('tipo_cfdi') == 'ingreso':
                    week_ingresos += cfdi.get('total', 0)
                else:
                    week_egresos += cfdi.get('total', 0)
        
        week['total_ingresos_reales'] = week_ingresos
        week['total_egresos_reales'] = week_egresos
        week['total_ingresos_proyectados'] = 0
        week['total_egresos_proyectados'] = 0
        
        # Set saldo_inicial from running balance
        week['saldo_inicial'] = running_balance
        
        # Calculate saldo_final
        week['saldo_final_real'] = week['saldo_inicial'] + week_ingresos - week_egresos
        week['saldo_final_proyectado'] = week['saldo_final_real']
        
        # Update running balance for next week
        running_balance = week['saldo_final_real']
    
    return weeks

@api_router.post("/transactions", response_model=Transaction)
async def create_transaction(transaction_data: TransactionCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    
    account = await db.bank_accounts.find_one({'id': transaction_data.bank_account_id, 'company_id': company_id}, {'_id': 0})
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    
    transaction_date = transaction_data.fecha_transaccion
    week = await db.cashflow_weeks.find_one({
        'company_id': company_id,
        'fecha_inicio': {'$lte': transaction_date.isoformat()},
        'fecha_fin': {'$gte': transaction_date.isoformat()}
    }, {'_id': 0})
    
    if not week:
        raise HTTPException(status_code=400, detail="No se encontró semana de cashflow para la fecha")
    
    transaction = Transaction(
        company_id=company_id,
        cashflow_week_id=week['id'],
        **transaction_data.model_dump()
    )
    
    doc = transaction.model_dump()
    for field in ['fecha_transaccion', 'created_at']:
        doc[field] = doc[field].isoformat()
    await db.transactions.insert_one(doc)
    
    await audit_log(transaction.company_id, 'Transaction', transaction.id, 'CREATE', current_user['id'])
    return transaction

@api_router.get("/transactions", response_model=List[Transaction])
async def list_transactions(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    limit: int = Query(100, le=1000),
    skip: int = Query(0, ge=0)
):
    company_id = await get_active_company_id(request, current_user)
    
    transactions = await db.transactions.find(
        {'company_id': company_id},
        {'_id': 0}
    ).sort('fecha_transaccion', -1).skip(skip).limit(limit).to_list(limit)
    
    for t in transactions:
        for field in ['fecha_transaccion', 'created_at']:
            if isinstance(t.get(field), str):
                t[field] = datetime.fromisoformat(t[field])
    return transactions

@api_router.post("/transactions/import")
async def import_transactions(file: UploadFile = File(...), current_user: Dict = Depends(get_current_user)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos Excel")
    
    content = await file.read()
    wb = openpyxl.load_workbook(io.BytesIO(content))
    ws = wb.active
    
    imported = 0
    errors = []
    
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row[0]:
            continue
        
        try:
            transaction_data = TransactionCreate(
                bank_account_id=str(row[0]),
                concepto=str(row[1]),
                monto=float(row[2]),
                tipo_transaccion=TransactionType(row[3].lower()),
                fecha_transaccion=row[4] if isinstance(row[4], datetime) else datetime.fromisoformat(str(row[4])),
                es_real=bool(row[5]) if len(row) > 5 else False,
                es_proyeccion=bool(row[6]) if len(row) > 6 else True,
                vendor_id=str(row[7]) if len(row) > 7 and row[7] else None,
                customer_id=str(row[8]) if len(row) > 8 and row[8] else None
            )
            await create_transaction(transaction_data, current_user)
            imported += 1
        except Exception as e:
            errors.append(f"Fila {idx}: {str(e)}")
    
    return {
        'status': 'success',
        'imported': imported,
        'errors': errors
    }

@api_router.post("/cfdi/upload")
async def upload_cfdi(request: Request, file: UploadFile = File(...), current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    
    if not file.filename.endswith('.xml'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos XML")
    
    xml_content = await file.read()
    xml_str = xml_content.decode('utf-8')
    
    parsed = parse_cfdi_xml(xml_str)
    
    existing = await db.cfdis.find_one({'company_id': company_id, 'uuid': parsed['uuid']}, {'_id': 0})
    if existing:
        raise HTTPException(status_code=400, detail="CFDI ya existe")
    
    # Get company RFC to determine if this is income or expense
    company = await db.companies.find_one({'id': company_id}, {'_id': 0, 'rfc': 1, 'nombre': 1})
    company_rfc = company.get('rfc', '').upper().strip() if company else ''
    company_nombre = company.get('nombre', '').upper().strip() if company else ''
    emisor_rfc = parsed['emisor_rfc'].upper().strip()
    emisor_nombre = parsed['emisor_nombre'].upper().strip()
    
    # Clasificación de CFDI:
    # 1. Si es nómina/sueldos -> SIEMPRE es egreso (pago a empleados)
    # 2. Si el EMISOR es la empresa (mismo RFC o nombre) = INGRESO (la empresa emitió, cobrará)
    # 3. Si el EMISOR es diferente = EGRESO/GASTO (otra empresa emitió, la empresa pagará)
    
    if parsed.get('is_nomina'):
        # Nómina/sueldos SIEMPRE es egreso, incluso si el RFC es de la empresa
        tipo_cfdi = 'egreso'
        logger.info(f"CFDI {parsed['uuid']} clasificado como EGRESO (nómina/sueldos)")
    elif company_rfc and emisor_rfc == company_rfc:
        tipo_cfdi = 'ingreso'
    elif company_nombre and emisor_nombre == company_nombre:
        tipo_cfdi = 'ingreso'
    else:
        tipo_cfdi = 'egreso'
    
    cfdi = CFDI(
        company_id=company_id,
        uuid=parsed['uuid'],
        tipo_cfdi=CFDIType(tipo_cfdi),
        emisor_rfc=parsed['emisor_rfc'],
        emisor_nombre=parsed['emisor_nombre'],
        receptor_rfc=parsed['receptor_rfc'],
        receptor_nombre=parsed['receptor_nombre'],
        fecha_emision=datetime.fromisoformat(parsed['fecha_emision']),
        fecha_timbrado=datetime.fromisoformat(parsed['fecha_timbrado']),
        moneda=parsed['moneda'],
        subtotal=parsed['subtotal'],
        descuento=parsed.get('descuento', 0),
        impuestos=parsed['impuestos'],
        total=parsed['total'],
        metodo_pago=parsed.get('metodo_pago', ''),
        forma_pago=parsed.get('forma_pago', ''),
        uso_cfdi=parsed.get('uso_cfdi', ''),
        iva_trasladado=parsed.get('iva_trasladado', 0),
        isr_retenido=parsed.get('isr_retenido', 0),
        iva_retenido=parsed.get('iva_retenido', 0),
        ieps=parsed.get('ieps', 0),
        estado_cancelacion='vigente',
        xml_original=xml_str
    )
    
    doc = cfdi.model_dump()
    for field in ['fecha_emision', 'fecha_timbrado', 'created_at']:
        doc[field] = doc[field].isoformat()
    await db.cfdis.insert_one(doc)
    
    await audit_log(cfdi.company_id, 'CFDI', cfdi.id, 'UPLOAD', current_user['id'])
    
    # Auto-categorize with AI if categories exist
    ai_category = None
    try:
        from ai_categorization_service import categorize_cfdi_with_ai
        
        # Get available categories for this CFDI type
        categories = await db.categories.find({
            'company_id': company_id, 
            'activo': True,
            'tipo': tipo_cfdi
        }, {'_id': 0}).to_list(100)
        
        if categories:
            # Get subcategories
            for cat in categories:
                subcats = await db.subcategories.find({'category_id': cat['id'], 'activo': True}, {'_id': 0}).to_list(100)
                cat['subcategorias'] = subcats
            
            # Prepare CFDI data for AI
            cfdi_data = {
                'uuid': cfdi.uuid,
                'tipo_cfdi': tipo_cfdi,
                'emisor_rfc': parsed['emisor_rfc'],
                'emisor_nombre': parsed['emisor_nombre'],
                'receptor_rfc': parsed['receptor_rfc'],
                'receptor_nombre': parsed['receptor_nombre'],
                'total': parsed['total'],
                'moneda': parsed['moneda'],
                'fecha_emision': parsed['fecha_emision']
            }
            
            # Call AI service
            ai_result = await categorize_cfdi_with_ai(cfdi_data, categories)
            
            if ai_result.get('success') and ai_result.get('category_id') and ai_result.get('confidence', 0) >= 70:
                update_data = {'category_id': ai_result['category_id']}
                if ai_result.get('subcategory_id'):
                    update_data['subcategory_id'] = ai_result['subcategory_id']
                
                await db.cfdis.update_one({'id': cfdi.id}, {'$set': update_data})
                ai_category = {
                    'category_id': ai_result['category_id'],
                    'subcategory_id': ai_result.get('subcategory_id'),
                    'confidence': ai_result.get('confidence'),
                    'reasoning': ai_result.get('reasoning')
                }
                await audit_log(company_id, 'CFDI', cfdi.id, 'AI_AUTO_CATEGORIZE', current_user['id'])
    except Exception as e:
        logger.warning(f"Auto-categorization failed for CFDI {cfdi.uuid}: {str(e)}")
    
    # NÓMINA: Auto-categorize as "Sueldos" and auto-reconcile with bank transactions
    nomina_auto_reconciled = None
    if parsed.get('is_nomina') or parsed.get('es_nomina_tipo_comprobante'):
        try:
            # 1. Find or create "Sueldos" category
            sueldos_category = await db.categories.find_one({
                'company_id': company_id,
                'nombre': {'$regex': '^sueldos?$', '$options': 'i'}
            }, {'_id': 0})
            
            if not sueldos_category:
                # Also check for "Nómina" or "Nominas"
                sueldos_category = await db.categories.find_one({
                    'company_id': company_id,
                    'nombre': {'$regex': '^n[oó]minas?$', '$options': 'i'}
                }, {'_id': 0})
            
            if not sueldos_category:
                # Create "Sueldos" category if doesn't exist
                new_cat_id = str(uuid.uuid4())
                sueldos_category = {
                    'id': new_cat_id,
                    'company_id': company_id,
                    'nombre': 'Sueldos',
                    'tipo': 'egreso',
                    'activo': True,
                    'created_at': datetime.now(timezone.utc).isoformat()
                }
                await db.categories.insert_one(sueldos_category)
                logger.info(f"Created 'Sueldos' category for company {company_id}")
            
            # Assign category to CFDI
            await db.cfdis.update_one({'id': cfdi.id}, {'$set': {'category_id': sueldos_category['id']}})
            
            # 2. Auto-reconcile with bank transactions by employee name and date
            receptor_nombre = parsed.get('receptor_nombre', '').upper().strip()
            fecha_emision = parsed.get('fecha_emision', '')[:10]  # YYYY-MM-DD
            nomina_data = parsed.get('nomina_data', {})
            fecha_pago_nomina = nomina_data.get('fecha_pago', fecha_emision)[:10] if nomina_data else fecha_emision
            total_cfdi = parsed.get('total', 0)
            
            # Search for bank transactions matching:
            # - Similar amount (within 5%)
            # - Similar date (within 7 days of fecha_pago)
            # - Name match in descripcion
            if receptor_nombre and total_cfdi > 0:
                # Parse dates for search range
                try:
                    fecha_ref = datetime.strptime(fecha_pago_nomina, '%Y-%m-%d')
                    fecha_desde = (fecha_ref - timedelta(days=7)).isoformat()
                    fecha_hasta = (fecha_ref + timedelta(days=7)).isoformat()
                    
                    # Find matching bank transactions
                    bank_txns = await db.bank_transactions.find({
                        'company_id': company_id,
                        'tipo_movimiento': 'debito',  # Payroll is a debit (money going out)
                        'conciliado': {'$ne': True},
                        'fecha_movimiento': {'$gte': fecha_desde, '$lte': fecha_hasta}
                    }, {'_id': 0}).to_list(100)
                    
                    best_match = None
                    best_score = 0
                    
                    for txn in bank_txns:
                        score = 0
                        txn_monto = abs(txn.get('monto', 0))
                        txn_desc = txn.get('descripcion', '').upper()
                        
                        # Check amount match (within 5%)
                        if txn_monto > 0:
                            diff_pct = abs(txn_monto - total_cfdi) / total_cfdi * 100
                            if diff_pct <= 5:
                                score += 50
                            elif diff_pct <= 10:
                                score += 30
                        
                        # Check name match in description
                        receptor_parts = receptor_nombre.split()
                        matches = sum(1 for part in receptor_parts if len(part) > 2 and part in txn_desc)
                        if matches >= 2:
                            score += 40
                        elif matches >= 1:
                            score += 20
                        
                        if score > best_score and score >= 50:
                            best_score = score
                            best_match = txn
                    
                    # Auto-reconcile if good match found
                    if best_match and best_score >= 50:
                        recon_id = str(uuid.uuid4())
                        recon_doc = {
                            'id': recon_id,
                            'company_id': company_id,
                            'bank_transaction_id': best_match['id'],
                            'cfdi_id': cfdi.id,
                            'metodo_conciliacion': 'auto_nomina',
                            'porcentaje_match': best_score,
                            'notas': f'Auto-conciliado: Nómina de {receptor_nombre}',
                            'fecha_conciliacion': datetime.now(timezone.utc).isoformat(),
                            'created_at': datetime.now(timezone.utc).isoformat()
                        }
                        await db.reconciliations.insert_one(recon_doc)
                        
                        # Update bank transaction as reconciled
                        await db.bank_transactions.update_one(
                            {'id': best_match['id']},
                            {'$set': {'conciliado': True, 'fecha_conciliacion': datetime.now(timezone.utc).isoformat()}}
                        )
                        
                        # Update CFDI as reconciled
                        await db.cfdis.update_one(
                            {'id': cfdi.id},
                            {'$set': {'estado_conciliacion': 'conciliado'}}
                        )
                        
                        nomina_auto_reconciled = {
                            'bank_transaction_id': best_match['id'],
                            'bank_descripcion': best_match.get('descripcion', '')[:50],
                            'match_score': best_score,
                            'empleado': receptor_nombre
                        }
                        
                        logger.info(f"Auto-reconciled nómina CFDI {cfdi.uuid} for {receptor_nombre} with bank txn {best_match['id']}")
                except Exception as inner_e:
                    logger.warning(f"Nómina auto-reconciliation failed: {str(inner_e)}")
        except Exception as e:
            logger.warning(f"Nómina processing failed for CFDI {cfdi.uuid}: {str(e)}")
    
    # Auto-detect customer/vendor by RFC
    auto_linked = None
    try:
        if tipo_cfdi == 'ingreso':
            # For income, the receptor (customer) is who we billed
            customer = await db.customers.find_one({
                'company_id': company_id, 
                'rfc': {'$regex': f'^{parsed["receptor_rfc"]}$', '$options': 'i'}
            }, {'_id': 0, 'id': 1, 'nombre': 1})
            if customer:
                await db.cfdis.update_one({'id': cfdi.id}, {'$set': {'customer_id': customer['id']}})
                auto_linked = {'type': 'customer', 'id': customer['id'], 'nombre': customer['nombre']}
        else:
            # For expense, the emisor (vendor) is who we're paying
            vendor = await db.vendors.find_one({
                'company_id': company_id, 
                'rfc': {'$regex': f'^{parsed["emisor_rfc"]}$', '$options': 'i'}
            }, {'_id': 0, 'id': 1, 'nombre': 1})
            if vendor:
                await db.cfdis.update_one({'id': cfdi.id}, {'$set': {'vendor_id': vendor['id']}})
                auto_linked = {'type': 'vendor', 'id': vendor['id'], 'nombre': vendor['nombre']}
    except Exception as e:
        logger.warning(f"Auto-link failed for CFDI {cfdi.uuid}: {str(e)}")
    
    # Detect new RFC - suggest creating customer/vendor
    new_rfc_detected = None
    if not auto_linked:
        try:
            if tipo_cfdi == 'ingreso':
                # Check if receptor RFC exists
                rfc_to_check = parsed.get('receptor_rfc', '')
                nombre_sugerido = parsed.get('receptor_nombre', rfc_to_check)
                existing = await db.customers.find_one({
                    'company_id': company_id,
                    'rfc': {'$regex': f'^{rfc_to_check}$', '$options': 'i'}
                }, {'_id': 0})
                if not existing and rfc_to_check:
                    new_rfc_detected = {
                        'type': 'customer',
                        'rfc': rfc_to_check,
                        'nombre_sugerido': nombre_sugerido,
                        'message': f'RFC {rfc_to_check} no está registrado como cliente. ¿Desea crearlo?'
                    }
            else:
                # Check if emisor RFC exists  
                rfc_to_check = parsed.get('emisor_rfc', '')
                nombre_sugerido = parsed.get('emisor_nombre', rfc_to_check)
                existing = await db.vendors.find_one({
                    'company_id': company_id,
                    'rfc': {'$regex': f'^{rfc_to_check}$', '$options': 'i'}
                }, {'_id': 0})
                if not existing and rfc_to_check:
                    new_rfc_detected = {
                        'type': 'vendor',
                        'rfc': rfc_to_check,
                        'nombre_sugerido': nombre_sugerido,
                        'message': f'RFC {rfc_to_check} no está registrado como proveedor. ¿Desea crearlo?'
                    }
        except Exception as e:
            logger.warning(f"New RFC detection failed: {str(e)}")
    
    return {
        'status': 'success', 
        'cfdi_id': cfdi.id, 
        'uuid': cfdi.uuid,
        'ai_categorized': ai_category is not None,
        'ai_category': ai_category,
        'auto_linked': auto_linked,
        'new_rfc_detected': new_rfc_detected,
        'is_nomina': parsed.get('is_nomina', False),
        'nomina_auto_reconciled': nomina_auto_reconciled
    }

@api_router.get("/cfdi", response_model=List[CFDI])
async def list_cfdis(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    limit: int = Query(100, le=1000),
    skip: int = Query(0, ge=0)
):
    company_id = await get_active_company_id(request, current_user)
    
    cfdis = await db.cfdis.find(
        {'company_id': company_id},
        {'_id': 0, 'xml_original': 0}
    ).sort('fecha_emision', -1).skip(skip).limit(limit).to_list(limit)
    
    for c in cfdis:
        for field in ['fecha_emision', 'fecha_timbrado', 'created_at']:
            if isinstance(c.get(field), str):
                c[field] = datetime.fromisoformat(c[field])
        
        # Calculate saldo_pendiente for partial payments support
        # Use monto_cobrado for ingresos (sales), monto_pagado for egresos (expenses)
        cfdi_total = c.get('total', 0)
        if c.get('tipo_cfdi') == 'ingreso':
            monto_cubierto = c.get('monto_cobrado', 0) or 0
        else:
            monto_cubierto = c.get('monto_pagado', 0) or 0
        c['saldo_pendiente'] = max(0, cfdi_total - monto_cubierto)
    
    return cfdis

@api_router.delete("/cfdi/{cfdi_id}")
async def delete_cfdi(cfdi_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    await db.cfdis.delete_one({'id': cfdi_id, 'company_id': company_id})
    await audit_log(company_id, 'CFDI', cfdi_id, 'DELETE', current_user['id'])
    
    return {'status': 'success', 'message': 'CFDI eliminado correctamente'}

@api_router.get("/transactions/template")
async def download_transactions_template():
    """Download Excel template for importing transactions"""
    import io
    from openpyxl import Workbook
    from fastapi.responses import StreamingResponse
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Transacciones"
    
    # Headers
    headers = [
        'concepto', 'monto', 'tipo_transaccion', 'fecha_transaccion', 
        'es_proyeccion', 'categoria', 'referencia', 'notas'
    ]
    ws.append(headers)
    
    # Example row
    ws.append([
        'Pago a proveedor', 10000.00, 'egreso', '2026-01-20', 
        'FALSE', 'operativo', 'REF-001', 'Pago factura #123'
    ])
    ws.append([
        'Cobro cliente', 25000.00, 'ingreso', '2026-01-22', 
        'FALSE', 'ventas', 'REF-002', 'Factura #456'
    ])
    
    # Add validation notes
    ws2 = wb.create_sheet("Instrucciones")
    ws2.append(["Campo", "Descripción", "Valores Válidos"])
    ws2.append(["concepto", "Descripción de la transacción", "Texto libre"])
    ws2.append(["monto", "Monto de la transacción", "Número positivo"])
    ws2.append(["tipo_transaccion", "Tipo de movimiento", "ingreso, egreso"])
    ws2.append(["fecha_transaccion", "Fecha del movimiento", "YYYY-MM-DD"])
    ws2.append(["es_proyeccion", "Es proyección futura?", "TRUE, FALSE"])
    ws2.append(["categoria", "Categoría del gasto/ingreso", "Texto libre"])
    ws2.append(["referencia", "Referencia o número de documento", "Texto libre"])
    ws2.append(["notas", "Notas adicionales", "Texto libre"])
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_transacciones.xlsx"}
    )

@api_router.post("/bank-transactions", response_model=BankTransaction)
async def create_bank_transaction(transaction_data: BankTransactionCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    account = await db.bank_accounts.find_one({'id': transaction_data.bank_account_id, 'company_id': company_id}, {'_id': 0})
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    
    # Use account's currency if not specified in transaction
    txn_data = transaction_data.model_dump()
    if not txn_data.get('moneda'):
        txn_data['moneda'] = account.get('moneda', 'MXN')
    
    bank_transaction = BankTransaction(company_id=company_id, **txn_data)
    doc = bank_transaction.model_dump()
    for field in ['fecha_movimiento', 'fecha_valor', 'created_at']:
        doc[field] = doc[field].isoformat()
    await db.bank_transactions.insert_one(doc)
    
    await audit_log(bank_transaction.company_id, 'BankTransaction', bank_transaction.id, 'CREATE', current_user['id'])
    return bank_transaction

@api_router.get("/bank-transactions", response_model=List[BankTransaction])
async def list_bank_transactions(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    limit: int = Query(100, le=1000),
    skip: int = Query(0, ge=0)
):
    company_id = await get_active_company_id(request, current_user)
    transactions = await db.bank_transactions.find(
        {'company_id': company_id},
        {'_id': 0}
    ).sort('fecha_movimiento', -1).skip(skip).limit(limit).to_list(limit)
    
    for t in transactions:
        for field in ['fecha_movimiento', 'fecha_valor', 'created_at']:
            if isinstance(t.get(field), str):
                t[field] = datetime.fromisoformat(t[field])
    return transactions

@api_router.delete("/bank-transactions/{transaction_id}")
async def delete_bank_transaction(transaction_id: str, current_user: Dict = Depends(get_current_user)):
    """Delete a bank transaction"""
    # Check if transaction exists
    txn = await db.bank_transactions.find_one({
        'id': transaction_id, 
        'company_id': current_user['company_id']
    })
    if not txn:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    # Check if it's reconciled
    if txn.get('conciliado'):
        raise HTTPException(status_code=400, detail="No se puede eliminar un movimiento conciliado")
    
    # Delete the transaction
    result = await db.bank_transactions.delete_one({
        'id': transaction_id,
        'company_id': current_user['company_id']
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    await audit_log(current_user['company_id'], 'BankTransaction', transaction_id, 'DELETE', current_user['id'])
    return {"status": "success", "message": "Movimiento eliminado"}

@api_router.post("/bank-transactions/transfer-account")
async def transfer_transactions_to_account(
    data: dict,
    current_user: Dict = Depends(get_current_user)
):
    """
    Transfer transactions from one account to another with optional currency conversion.
    Supports:
    - Transfer between accounts of same bank or different banks
    - Currency conversion using FX rates when moving between MXN/USD accounts
    - Optional custom FX rate override
    """
    company_id = current_user['company_id']
    
    from_account_id = data.get('from_account_id')
    to_account_id = data.get('to_account_id')
    convert_currency = data.get('convert_currency', True)  # Whether to convert amounts
    custom_fx_rate = data.get('custom_fx_rate')  # Optional: user-provided exchange rate
    transaction_ids = data.get('transaction_ids')  # Optional: specific transactions to transfer
    
    if not from_account_id or not to_account_id:
        raise HTTPException(status_code=400, detail="Se requieren from_account_id y to_account_id")
    
    # Verify both accounts exist and belong to company
    from_account = await db.bank_accounts.find_one({'id': from_account_id, 'company_id': company_id}, {'_id': 0})
    to_account = await db.bank_accounts.find_one({'id': to_account_id, 'company_id': company_id}, {'_id': 0})
    
    if not from_account:
        raise HTTPException(status_code=404, detail="Cuenta origen no encontrada")
    if not to_account:
        raise HTTPException(status_code=404, detail="Cuenta destino no encontrada")
    
    from_currency = from_account.get('moneda', 'MXN')
    to_currency = to_account.get('moneda', 'MXN')
    
    # Get FX rate if currencies are different
    fx_rate = 1.0
    if from_currency != to_currency and convert_currency:
        if custom_fx_rate:
            fx_rate = float(custom_fx_rate)
        else:
            # Get latest FX rate from database
            if from_currency == 'USD' and to_currency == 'MXN':
                rate_doc = await db.fx_rates.find_one(
                    {'company_id': company_id, '$or': [{'moneda_cotizada': 'USD'}, {'moneda_origen': 'USD'}]},
                    {'_id': 0},
                    sort=[('fecha_vigencia', -1)]
                )
                fx_rate = rate_doc.get('tipo_cambio') or rate_doc.get('tasa') or 17.5 if rate_doc else 17.5
            elif from_currency == 'MXN' and to_currency == 'USD':
                rate_doc = await db.fx_rates.find_one(
                    {'company_id': company_id, '$or': [{'moneda_cotizada': 'USD'}, {'moneda_origen': 'USD'}]},
                    {'_id': 0},
                    sort=[('fecha_vigencia', -1)]
                )
                base_rate = rate_doc.get('tipo_cambio') or rate_doc.get('tasa') or 17.5 if rate_doc else 17.5
                fx_rate = 1 / base_rate  # Inverse for MXN to USD
            else:
                # For other currency pairs, try to find direct rate
                rate_doc = await db.fx_rates.find_one(
                    {'company_id': company_id, 'moneda_origen': from_currency, 'moneda_cotizada': to_currency},
                    {'_id': 0},
                    sort=[('fecha_vigencia', -1)]
                )
                fx_rate = rate_doc.get('tasa') or 1.0 if rate_doc else 1.0
    
    # Build query for transactions
    txn_query = {'bank_account_id': from_account_id, 'company_id': company_id}
    if transaction_ids and len(transaction_ids) > 0:
        txn_query['id'] = {'$in': transaction_ids}
    
    # Get transactions to transfer
    transactions = await db.bank_transactions.find(txn_query, {'_id': 0}).to_list(10000)
    
    if len(transactions) == 0:
        return {
            "status": "warning",
            "message": "No se encontraron movimientos para transferir",
            "modified_count": 0
        }
    
    # Transfer each transaction with currency conversion if needed
    transferred_count = 0
    total_original = 0
    total_converted = 0
    
    for txn in transactions:
        original_monto = txn.get('monto', 0)
        total_original += original_monto
        
        # Calculate converted amount
        if from_currency != to_currency and convert_currency:
            converted_monto = round(original_monto * fx_rate, 2)
        else:
            converted_monto = original_monto
        
        total_converted += converted_monto
        
        # Update transaction
        update_data = {
            'bank_account_id': to_account_id,
            'moneda': to_currency
        }
        
        if from_currency != to_currency and convert_currency:
            update_data['monto'] = converted_monto
            update_data['monto_original'] = original_monto
            update_data['moneda_original'] = from_currency
            update_data['tipo_cambio_conversion'] = fx_rate
        
        await db.bank_transactions.update_one(
            {'id': txn['id'], 'company_id': company_id},
            {'$set': update_data}
        )
        transferred_count += 1
    
    await audit_log(company_id, 'BankTransaction', 'bulk_transfer', 'UPDATE', current_user['id'], 
                    {
                        'from': from_account_id, 
                        'to': to_account_id, 
                        'count': transferred_count,
                        'from_currency': from_currency,
                        'to_currency': to_currency,
                        'fx_rate': fx_rate,
                        'convert_currency': convert_currency
                    })
    
    return {
        "status": "success",
        "message": f"Se transfirieron {transferred_count} movimientos de {from_account.get('nombre', '')} a {to_account.get('nombre', '')}",
        "modified_count": transferred_count,
        "from_currency": from_currency,
        "to_currency": to_currency,
        "fx_rate_used": fx_rate if from_currency != to_currency else None,
        "total_original": round(total_original, 2),
        "total_converted": round(total_converted, 2),
        "currency_converted": from_currency != to_currency and convert_currency
    }

@api_router.put("/bank-transactions/{transaction_id}")
async def update_bank_transaction(transaction_id: str, data: dict, current_user: Dict = Depends(get_current_user)):
    """Update a bank transaction"""
    company_id = current_user['company_id']
    
    # Check if transaction exists
    txn = await db.bank_transactions.find_one({
        'id': transaction_id, 
        'company_id': company_id
    })
    if not txn:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    
    # Fields that can be updated
    allowed_fields = ['bank_account_id', 'descripcion', 'referencia', 'monto', 'tipo_movimiento', 
                      'fecha_movimiento', 'fecha_valor', 'moneda', 'notas']
    
    update_data = {}
    for field in allowed_fields:
        if field in data:
            update_data[field] = data[field]
    
    # If bank_account_id changed, update moneda from the new account
    if 'bank_account_id' in update_data and update_data['bank_account_id']:
        new_account = await db.bank_accounts.find_one({'id': update_data['bank_account_id'], 'company_id': company_id}, {'_id': 0})
        if new_account:
            update_data['moneda'] = new_account.get('moneda', 'MXN')
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    
    result = await db.bank_transactions.update_one(
        {'id': transaction_id, 'company_id': company_id},
        {'$set': update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="No se pudo actualizar el movimiento")
    
    await audit_log(company_id, 'BankTransaction', transaction_id, 'UPDATE', current_user['id'], txn, update_data)
    
    # Return updated transaction
    updated = await db.bank_transactions.find_one({'id': transaction_id}, {'_id': 0})
    return updated

@api_router.post("/bank-transactions/check-duplicates")
async def check_duplicate_transactions(
    transactions: List[dict],
    current_user: Dict = Depends(get_current_user)
):
    """Check for duplicate transactions before import"""
    company_id = current_user['company_id']
    duplicates = []
    
    for txn in transactions:
        # Check if a transaction with same date, description and amount exists
        query = {
            'company_id': company_id,
            'monto': txn.get('monto'),
            'descripcion': txn.get('descripcion')
        }
        
        # Parse date if string
        fecha = txn.get('fecha_movimiento')
        if fecha:
            if isinstance(fecha, str):
                try:
                    fecha_dt = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
                    # Check within same day
                    start_of_day = fecha_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_of_day = fecha_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                    query['fecha_movimiento'] = {'$gte': start_of_day.isoformat(), '$lte': end_of_day.isoformat()}
                except:
                    pass
        
        existing = await db.bank_transactions.find_one(query, {'_id': 0})
        if existing:
            duplicates.append({
                'descripcion': txn.get('descripcion'),
                'monto': txn.get('monto'),
                'fecha': str(fecha)[:10] if fecha else ''
            })
    
    return {'duplicates': duplicates, 'count': len(duplicates)}

# ==================== RECONCILIATIONS ENDPOINTS MOVED TO routes/reconciliations.py ====================
# All reconciliation endpoints are now handled by routes/reconciliations.py:
# - POST /reconciliations
# - GET /reconciliations
# - DELETE /reconciliations/{id}
# - GET /reconciliations/by-cfdi/{cfdi_id}
# - GET /reconciliations/summary
# - POST /reconciliations/mark-without-uuid
# - DELETE /reconciliations/bulk/all

# ===== CONCEPTOS MANUALES DE PROYECCIÓN =====
@api_router.post("/manual-projections", response_model=ManualProjectionConcept)
async def create_manual_projection(data: ManualProjectionConceptCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    concept = ManualProjectionConcept(company_id=company_id, **data.model_dump())
    doc = concept.model_dump()
    if doc.get('created_at'):
        doc['created_at'] = doc['created_at'].isoformat()
    await db.manual_projections.insert_one(doc)
    await audit_log(company_id, 'ManualProjection', concept.id, 'CREATE', current_user['id'])
    return concept

@api_router.get("/manual-projections")
async def list_manual_projections(
    request: Request, 
    current_user: Dict = Depends(get_current_user),
    tipo: Optional[str] = Query(None, description="ingreso o egreso"),
    activo: Optional[bool] = Query(True)
):
    company_id = await get_active_company_id(request, current_user)
    query = {'company_id': company_id}
    if tipo:
        query['tipo'] = tipo
    if activo is not None:
        query['activo'] = activo
    concepts = await db.manual_projections.find(query, {'_id': 0}).sort('created_at', -1).to_list(500)
    return concepts

@api_router.put("/manual-projections/{concept_id}")
async def update_manual_projection(
    concept_id: str, 
    data: ManualProjectionConceptCreate, 
    request: Request, 
    current_user: Dict = Depends(get_current_user)
):
    company_id = await get_active_company_id(request, current_user)
    existing = await db.manual_projections.find_one({'id': concept_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Concepto no encontrado")
    
    update_data = data.model_dump()
    await db.manual_projections.update_one(
        {'id': concept_id},
        {'$set': update_data}
    )
    await audit_log(company_id, 'ManualProjection', concept_id, 'UPDATE', current_user['id'])
    updated = await db.manual_projections.find_one({'id': concept_id}, {'_id': 0})
    return updated

@api_router.delete("/manual-projections/{concept_id}")
async def delete_manual_projection(concept_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    existing = await db.manual_projections.find_one({'id': concept_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Concepto no encontrado")
    await db.manual_projections.delete_one({'id': concept_id})
    await audit_log(company_id, 'ManualProjection', concept_id, 'DELETE', current_user['id'])
    return {"message": "Concepto eliminado exitosamente"}

# ==================== PAYMENTS ENDPOINTS PARTIALLY MOVED TO routes/payments.py ====================
# Basic CRUD endpoints moved:
# - POST /payments
# - GET /payments
# - PUT /payments/{id}
# - POST /payments/{id}/complete
# - DELETE /payments/{id}
# - DELETE /payments/bulk/all
#
# Specialized endpoints remain here:
# - GET /payments/{id}/match-candidates
# - POST /payments/{id}/auto-reconcile
# - POST /payments/from-bank-with-cfdi-match
# - GET /payments/summary (uses CFDI-based logic)
# - GET /payments/breakdown


@api_router.get("/payments/{payment_id}/match-candidates")
async def get_payment_match_candidates(
    payment_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Find bank transactions that could match this payment.
    Searches by:
    - UUID of the linked CFDI in the transaction description
    - Similar amount (+/- 1%)
    - Date within 30 days
    """
    company_id = await get_active_company_id(request, current_user)
    
    payment = await db.payments.find_one({'id': payment_id, 'company_id': company_id}, {'_id': 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    
    candidates = []
    
    # Get the linked CFDI if exists
    cfdi = None
    cfdi_uuid = None
    if payment.get('cfdi_id'):
        cfdi = await db.cfdis.find_one({'id': payment['cfdi_id']}, {'_id': 0})
        if cfdi:
            cfdi_uuid = cfdi.get('uuid', '')
    
    # Search bank transactions
    # Criteria: not yet reconciled, same company, similar amount or matching UUID
    monto = payment.get('monto', 0)
    moneda = payment.get('moneda', 'MXN')
    tipo_esperado = 'credito' if payment['tipo'] == 'cobro' else 'debito'
    
    # Build query
    query = {
        'company_id': company_id,
        'conciliado': False
    }
    
    # Get all unreconciled transactions
    transactions = await db.bank_transactions.find(query, {'_id': 0}).to_list(500)
    
    for txn in transactions:
        score = 0
        match_reasons = []
        
        # Check if UUID is in description
        if cfdi_uuid and cfdi_uuid.upper() in (txn.get('descripcion', '') + txn.get('referencia', '')).upper():
            score += 100
            match_reasons.append(f"UUID encontrado en descripción")
        
        # Check amount (within 1% tolerance or exact)
        txn_monto = txn.get('monto', 0)
        if txn_monto > 0:
            diff_pct = abs(txn_monto - monto) / monto * 100 if monto > 0 else 100
            if diff_pct < 0.01:  # Exact match
                score += 80
                match_reasons.append(f"Monto exacto")
            elif diff_pct < 1:  # Within 1%
                score += 60
                match_reasons.append(f"Monto similar ({diff_pct:.2f}% diferencia)")
            elif diff_pct < 5:  # Within 5%
                score += 30
                match_reasons.append(f"Monto cercano ({diff_pct:.2f}% diferencia)")
        
        # Check transaction type matches
        if txn.get('tipo_movimiento') == tipo_esperado:
            score += 20
            match_reasons.append(f"Tipo coincide ({tipo_esperado})")
        
        # Check currency matches
        if txn.get('moneda', 'MXN') == moneda:
            score += 10
            match_reasons.append(f"Moneda coincide ({moneda})")
        
        # Only include if score is meaningful
        if score >= 30:
            # Get bank account info
            bank_account = await db.bank_accounts.find_one({'id': txn.get('bank_account_id')}, {'_id': 0, 'banco': 1, 'nombre': 1})
            
            candidates.append({
                'transaction_id': txn['id'],
                'fecha': txn.get('fecha_movimiento'),
                'descripcion': txn.get('descripcion', '')[:100],
                'referencia': txn.get('referencia', ''),
                'monto': txn_monto,
                'tipo': txn.get('tipo_movimiento'),
                'moneda': txn.get('moneda', 'MXN'),
                'banco': bank_account.get('banco', '') if bank_account else '',
                'cuenta': bank_account.get('nombre', '') if bank_account else '',
                'score': score,
                'match_reasons': match_reasons
            })
    
    # Sort by score descending
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    return {
        'payment_id': payment_id,
        'payment_monto': monto,
        'payment_moneda': moneda,
        'payment_tipo': payment['tipo'],
        'cfdi_uuid': cfdi_uuid,
        'candidates': candidates[:10],  # Top 10 matches
        'total_found': len(candidates)
    }


@api_router.post("/payments/{payment_id}/auto-reconcile")
async def auto_reconcile_payment(
    payment_id: str,
    request: Request,
    transaction_id: str = Query(..., description="ID del movimiento bancario a conciliar"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Reconcile a payment with a bank transaction after user authorization.
    """
    company_id = await get_active_company_id(request, current_user)
    
    payment = await db.payments.find_one({'id': payment_id, 'company_id': company_id}, {'_id': 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    
    transaction = await db.bank_transactions.find_one({'id': transaction_id, 'company_id': company_id}, {'_id': 0})
    if not transaction:
        raise HTTPException(status_code=404, detail="Movimiento bancario no encontrado")
    
    if transaction.get('conciliado'):
        raise HTTPException(status_code=400, detail="El movimiento ya está conciliado")
    
    # Mark transaction as reconciled and link to payment
    await db.bank_transactions.update_one(
        {'id': transaction_id},
        {'$set': {
            'conciliado': True,
            'payment_id': payment_id,
            'cfdi_ids': [payment.get('cfdi_id')] if payment.get('cfdi_id') else [],
            'fecha_conciliacion': datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Update payment with transaction reference
    await db.payments.update_one(
        {'id': payment_id},
        {'$set': {
            'bank_transaction_id': transaction_id,
            'conciliado': True
        }}
    )
    
    await audit_log(company_id, 'Payment', payment_id, 'AUTO_RECONCILE', current_user['id'])
    
    return {
        'status': 'success',
        'message': 'Pago conciliado exitosamente',
        'payment_id': payment_id,
        'transaction_id': transaction_id
    }


@api_router.get("/bank-transactions/{txn_id}/match-cfdi")
async def find_matching_cfdi_for_transaction(
    txn_id: str,
    request: Request,
    current_user: Dict = Depends(get_current_user),
    tolerance_days: int = Query(60, description="Tolerancia de días para buscar CFDIs (default: 60)")
):
    """
    P0 - Matching Automático de CFDIs
    Find CFDIs that match a bank transaction by amount and date (±tolerance_days).
    Used when creating payments from bank movements to suggest automatic CFDI links.
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Get the bank transaction
    txn = await db.bank_transactions.find_one({'id': txn_id, 'company_id': company_id}, {'_id': 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Movimiento bancario no encontrado")
    
    monto = txn.get('monto', 0)
    moneda = txn.get('moneda', 'MXN')
    fecha_txn_str = txn.get('fecha_movimiento')
    tipo_movimiento = txn.get('tipo_movimiento', 'credito')  # credito = cobro, debito = pago
    
    # Parse the transaction date
    if isinstance(fecha_txn_str, str):
        try:
            fecha_txn = datetime.fromisoformat(fecha_txn_str.replace('Z', '+00:00'))
        except:
            fecha_txn = datetime.now(timezone.utc)
    else:
        fecha_txn = fecha_txn_str or datetime.now(timezone.utc)
    
    # Define date range (±tolerance_days)
    fecha_inicio = (fecha_txn - timedelta(days=tolerance_days)).isoformat()
    fecha_fin = (fecha_txn + timedelta(days=tolerance_days)).isoformat()
    
    # Determine CFDI type based on transaction type
    # credito (deposit) = ingreso (we received payment for a sale)
    # debito (withdrawal) = egreso (we paid for a purchase) OR nomina
    cfdi_tipo = 'ingreso' if tipo_movimiento == 'credito' else 'egreso'
    
    # Build query to find matching CFDIs
    # Look for CFDIs with similar amount and within date range
    # For debito, also include nomina type
    if tipo_movimiento == 'debito':
        query = {
            'company_id': company_id,
            'tipo_cfdi': {'$in': ['egreso', 'nomina']},
            'estatus': 'vigente',
            'fecha_emision': {'$gte': fecha_inicio, '$lte': fecha_fin}
        }
    else:
        query = {
            'company_id': company_id,
            'tipo_cfdi': cfdi_tipo,
            'estatus': 'vigente',
            'fecha_emision': {'$gte': fecha_inicio, '$lte': fecha_fin}
        }
    
    # Get candidate CFDIs
    cfdis = await db.cfdis.find(query, {'_id': 0}).to_list(200)
    
    # Get transaction description for name matching
    txn_descripcion_upper = (txn.get('descripcion', '') + ' ' + txn.get('referencia', '')).upper()
    
    matches = []
    for cfdi in cfdis:
        cfdi_total = cfdi.get('total', 0)
        cfdi_moneda = cfdi.get('moneda', 'MXN')
        is_nomina = cfdi.get('tipo_cfdi') == 'nomina' or cfdi.get('is_nomina', False)
        
        # Calculate pending amount
        if cfdi.get('tipo_cfdi') == 'ingreso':
            monto_cubierto = cfdi.get('monto_cobrado', 0) or 0
        else:
            monto_cubierto = cfdi.get('monto_pagado', 0) or 0
        
        saldo_pendiente = cfdi_total - monto_cubierto
        
        # Skip fully paid CFDIs
        if saldo_pendiente < 0.01:
            continue
        
        # Calculate match score
        score = 0
        match_reasons = []
        
        # Amount matching (compare with transaction amount)
        # Allow for some tolerance (0.5% for banking fees, rounding)
        if monto > 0:
            # Check if amounts match closely
            diff_pct = abs(monto - saldo_pendiente) / saldo_pendiente * 100 if saldo_pendiente > 0 else 100
            
            if diff_pct < 0.5:  # Exact or near-exact match
                score += 50
                match_reasons.append("Monto exacto")
            elif diff_pct < 2:  # Within 2%
                score += 35
                match_reasons.append(f"Monto muy cercano ({diff_pct:.1f}% dif)")
            elif diff_pct < 5:  # Within 5%
                score += 20
                match_reasons.append(f"Monto cercano ({diff_pct:.1f}% dif)")
            elif diff_pct < 10:  # Within 10%
                score += 10
                match_reasons.append(f"Monto aproximado ({diff_pct:.1f}% dif)")
            else:
                continue  # Too different, skip this CFDI
        
        # Date proximity bonus
        cfdi_fecha_str = cfdi.get('fecha_emision')
        if cfdi_fecha_str:
            try:
                cfdi_fecha = datetime.fromisoformat(cfdi_fecha_str.replace('Z', '+00:00')) if isinstance(cfdi_fecha_str, str) else cfdi_fecha_str
                days_diff = abs((fecha_txn - cfdi_fecha).days)
                
                if days_diff <= 7:
                    score += 30
                    match_reasons.append("Fecha muy cercana (≤7 días)")
                elif days_diff <= 15:
                    score += 20
                    match_reasons.append(f"Fecha cercana ({days_diff} días)")
                elif days_diff <= 30:
                    score += 10
                    match_reasons.append(f"Fecha dentro de 30 días")
                else:
                    score += 5
                    match_reasons.append(f"Fecha dentro de {days_diff} días")
            except:
                pass
        
        # Currency match bonus
        if cfdi_moneda == moneda:
            score += 10
            match_reasons.append(f"Moneda coincide ({moneda})")
        
        # Check if CFDI UUID appears in transaction description or reference
        cfdi_uuid = cfdi.get('uuid', '')
        if cfdi_uuid and cfdi_uuid.upper()[:8] in txn_descripcion_upper:
            score += 40
            match_reasons.append("UUID parcial en descripción")
        
        # NAME MATCHING: Check if receptor/emisor name appears in transaction description
        # This is especially important for nóminas where receptor is the employee
        nombres_buscar = []
        if is_nomina:
            # For nóminas, search for employee name (receptor)
            receptor = cfdi.get('receptor_nombre', '')
            if receptor:
                nombres_buscar.append(receptor.upper())
        else:
            # For regular egresos, search for provider name (emisor)
            emisor = cfdi.get('emisor_nombre', '')
            if emisor:
                nombres_buscar.append(emisor.upper())
            # Also check receptor in case it's in description
            receptor = cfdi.get('receptor_nombre', '')
            if receptor:
                nombres_buscar.append(receptor.upper())
        
        # Check name parts in transaction description
        for nombre in nombres_buscar:
            nombre_parts = [p for p in nombre.split() if len(p) > 2]
            if nombre_parts:
                # Count how many name parts appear in description
                matches_count = sum(1 for part in nombre_parts if part in txn_descripcion_upper)
                if matches_count >= 3:
                    score += 50
                    match_reasons.append(f"Nombre completo coincide")
                    break
                elif matches_count >= 2:
                    score += 35
                    match_reasons.append(f"Nombre parcial coincide ({matches_count} partes)")
                    break
                elif matches_count >= 1 and len(nombre_parts) <= 2:
                    score += 20
                    match_reasons.append(f"Nombre parcial coincide")
                    break
        
        # Only include if score is meaningful
        if score >= 20:
            matches.append({
                'cfdi_id': cfdi.get('id'),
                'uuid': cfdi_uuid,
                'uuid_short': cfdi_uuid[:8] if cfdi_uuid else '',
                'tipo_cfdi': cfdi_tipo,
                'fecha_emision': cfdi.get('fecha_emision'),
                'emisor_nombre': cfdi.get('emisor_nombre', ''),
                'receptor_nombre': cfdi.get('receptor_nombre', ''),
                'total': cfdi_total,
                'saldo_pendiente': saldo_pendiente,
                'moneda': cfdi_moneda,
                'score': score,
                'match_reasons': match_reasons,
                'confidence': 'alta' if score >= 60 else 'media' if score >= 40 else 'baja'
            })
    
    # Sort by score descending
    matches.sort(key=lambda x: x['score'], reverse=True)
    
    # Prepare response
    best_match = matches[0] if matches else None
    
    return {
        'transaction_id': txn_id,
        'transaction_monto': monto,
        'transaction_moneda': moneda,
        'transaction_fecha': fecha_txn_str,
        'transaction_tipo': tipo_movimiento,
        'cfdi_tipo_esperado': cfdi_tipo,
        'tolerance_days': tolerance_days,
        'best_match': best_match,
        'all_matches': matches[:10],  # Top 10
        'total_matches': len(matches),
        'auto_link_recommended': best_match is not None and best_match['score'] >= 60
    }


@api_router.post("/payments/from-bank-with-cfdi-match")
async def create_payment_from_bank_with_cfdi_match(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    bank_transaction_id: str = Query(..., description="ID del movimiento bancario"),
    cfdi_id: Optional[str] = Query(None, description="ID del CFDI a vincular (opcional, se detecta automáticamente si no se provee)"),
    auto_detect: bool = Query(True, description="Detectar CFDI automáticamente por monto y fecha")
):
    """
    P0 - Create a payment from a bank transaction with automatic CFDI matching.
    If auto_detect=True and no cfdi_id provided, will try to find the best matching CFDI.
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Get the bank transaction
    txn = await db.bank_transactions.find_one({'id': bank_transaction_id, 'company_id': company_id}, {'_id': 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Movimiento bancario no encontrado")
    
    if txn.get('conciliado'):
        raise HTTPException(status_code=400, detail="Este movimiento ya está conciliado")
    
    # Check if payment already exists for this bank transaction (prevent duplicates)
    existing_payment = await db.payments.find_one({
        'company_id': company_id,
        'bank_transaction_id': bank_transaction_id
    }, {'_id': 0, 'id': 1})
    
    if existing_payment:
        raise HTTPException(status_code=400, detail="Ya existe un pago para este movimiento bancario")
    
    # Get bank account info
    bank_account = await db.bank_accounts.find_one({'id': txn.get('bank_account_id')}, {'_id': 0})
    moneda = txn.get('moneda') or (bank_account.get('moneda') if bank_account else 'MXN')
    
    # Determine payment type
    tipo = 'cobro' if txn.get('tipo_movimiento') == 'credito' else 'pago'
    
    # Auto-detect CFDI if requested and not provided
    matched_cfdi = None
    match_info = None
    
    if cfdi_id:
        # Use provided CFDI
        matched_cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
        if not matched_cfdi:
            raise HTTPException(status_code=404, detail="CFDI no encontrado")
    elif auto_detect:
        # Try to find matching CFDI automatically
        # Use internal call to match-cfdi endpoint logic
        monto = txn.get('monto', 0)
        fecha_txn_str = txn.get('fecha_movimiento')
        tipo_movimiento = txn.get('tipo_movimiento', 'credito')
        
        if isinstance(fecha_txn_str, str):
            try:
                fecha_txn = datetime.fromisoformat(fecha_txn_str.replace('Z', '+00:00'))
            except:
                fecha_txn = datetime.now(timezone.utc)
        else:
            fecha_txn = fecha_txn_str or datetime.now(timezone.utc)
        
        # Define date range (±60 days as requested by user)
        fecha_inicio = (fecha_txn - timedelta(days=60)).isoformat()
        fecha_fin = (fecha_txn + timedelta(days=60)).isoformat()
        
        cfdi_tipo = 'ingreso' if tipo_movimiento == 'credito' else 'egreso'
        
        query = {
            'company_id': company_id,
            'tipo_cfdi': cfdi_tipo,
            'estatus': 'vigente',
            'fecha_emision': {'$gte': fecha_inicio, '$lte': fecha_fin}
        }
        
        cfdis = await db.cfdis.find(query, {'_id': 0}).to_list(100)
        
        best_score = 0
        best_cfdi = None
        
        for cfdi in cfdis:
            cfdi_total = cfdi.get('total', 0)
            monto_cubierto = cfdi.get('monto_cobrado' if cfdi_tipo == 'ingreso' else 'monto_pagado', 0) or 0
            saldo_pendiente = cfdi_total - monto_cubierto
            
            if saldo_pendiente < 0.01:
                continue
            
            score = 0
            if monto > 0 and saldo_pendiente > 0:
                diff_pct = abs(monto - saldo_pendiente) / saldo_pendiente * 100
                if diff_pct < 0.5:
                    score += 50
                elif diff_pct < 2:
                    score += 35
                elif diff_pct < 5:
                    score += 20
                elif diff_pct < 10:
                    score += 10
                else:
                    continue
            
            # Date proximity
            cfdi_fecha_str = cfdi.get('fecha_emision')
            if cfdi_fecha_str:
                try:
                    cfdi_fecha = datetime.fromisoformat(cfdi_fecha_str.replace('Z', '+00:00')) if isinstance(cfdi_fecha_str, str) else cfdi_fecha_str
                    days_diff = abs((fecha_txn - cfdi_fecha).days)
                    if days_diff <= 7:
                        score += 30
                    elif days_diff <= 15:
                        score += 20
                    elif days_diff <= 30:
                        score += 10
                    else:
                        score += 5
                except:
                    pass
            
            # Currency match
            if cfdi.get('moneda', 'MXN') == moneda:
                score += 10
            
            if score > best_score:
                best_score = score
                best_cfdi = cfdi
        
        # Only auto-link if confidence is high (score >= 60)
        if best_score >= 60 and best_cfdi:
            matched_cfdi = best_cfdi
            match_info = {
                'auto_detected': True,
                'score': best_score,
                'confidence': 'alta' if best_score >= 60 else 'media'
            }
    
    # Create the payment
    payment_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    payment_doc = {
        'id': payment_id,
        'company_id': company_id,
        'bank_account_id': txn.get('bank_account_id'),
        'cfdi_id': matched_cfdi.get('id') if matched_cfdi else None,
        'tipo': tipo,
        'concepto': txn.get('descripcion') or f"Movimiento bancario {txn.get('referencia', '')}",
        'monto': txn.get('monto', 0),
        'moneda': moneda,
        'metodo_pago': 'transferencia',
        'fecha_vencimiento': txn.get('fecha_movimiento'),
        'fecha_pago': now.isoformat(),
        'estatus': 'completado',
        'referencia': txn.get('referencia', ''),
        'beneficiario': txn.get('merchant_name') or txn.get('descripcion', '')[:50] if txn.get('descripcion') else '',
        'es_real': True,
        'bank_transaction_id': bank_transaction_id,
        'created_at': now.isoformat()
    }
    
    # Get historical exchange rate for non-MXN currencies
    if moneda != 'MXN':
        rate = await db.fx_rates.find_one(
            {'company_id': company_id, '$or': [
                {'moneda_cotizada': moneda},
                {'moneda_origen': moneda}
            ]},
            {'_id': 0},
            sort=[('fecha_vigencia', -1)]
        )
        if rate:
            payment_doc['tipo_cambio_historico'] = rate.get('tipo_cambio') or rate.get('tasa') or 1
        else:
            default_rates = {'USD': 17.50, 'EUR': 19.00}
            payment_doc['tipo_cambio_historico'] = default_rates.get(moneda, 1)
    
    await db.payments.insert_one(payment_doc)
    
    # Update CFDI if linked
    if matched_cfdi:
        if tipo == 'cobro':
            current_cobrado = matched_cfdi.get('monto_cobrado', 0) or 0
            new_cobrado = current_cobrado + payment_doc['monto']
            await db.cfdis.update_one(
                {'id': matched_cfdi['id']},
                {'$set': {'monto_cobrado': new_cobrado}}
            )
        else:
            current_pagado = matched_cfdi.get('monto_pagado', 0) or 0
            new_pagado = current_pagado + payment_doc['monto']
            await db.cfdis.update_one(
                {'id': matched_cfdi['id']},
                {'$set': {'monto_pagado': new_pagado}}
            )
    
    # Mark bank transaction as reconciled
    await db.bank_transactions.update_one(
        {'id': bank_transaction_id},
        {'$set': {
            'conciliado': True,
            'payment_id': payment_id,
            'fecha_conciliacion': now.isoformat()
        }}
    )
    
    # Create reconciliation record
    recon_doc = {
        'id': str(uuid.uuid4()),
        'company_id': company_id,
        'bank_transaction_id': bank_transaction_id,
        'cfdi_id': matched_cfdi.get('id') if matched_cfdi else None,
        'metodo_conciliacion': 'automatica' if match_info else 'manual',
        'tipo_conciliacion': 'con_uuid' if matched_cfdi else 'sin_uuid',
        'porcentaje_match': match_info.get('score', 100) if match_info else 100,
        'fecha_conciliacion': now.isoformat(),
        'user_id': current_user['id'],
        'notas': f"Creado desde módulo Cobranza y Pagos. {'Auto-detectado.' if match_info else ''}",
        'created_at': now.isoformat()
    }
    await db.reconciliations.insert_one(recon_doc)
    
    await audit_log(company_id, 'Payment', payment_id, 'CREATE_FROM_BANK', current_user['id'])
    
    return {
        'status': 'success',
        'payment_id': payment_id,
        'payment_tipo': tipo,
        'payment_monto': payment_doc['monto'],
        'cfdi_linked': matched_cfdi is not None,
        'cfdi_id': matched_cfdi.get('id') if matched_cfdi else None,
        'cfdi_uuid': matched_cfdi.get('uuid') if matched_cfdi else None,
        'match_info': match_info,
        'message': f"{'Cobro' if tipo == 'cobro' else 'Pago'} creado" + 
                   (f" y vinculado a CFDI {matched_cfdi.get('uuid', '')[:8]}..." if matched_cfdi else " sin CFDI asociado")
    }


@api_router.post("/bank-transactions/batch-create-payments")
async def batch_create_payments_from_bank(
    request: Request,
    data: dict,
    current_user: Dict = Depends(get_current_user)
):
    """
    Create multiple payments from bank transactions with automatic CFDI matching.
    Expects: { "transaction_ids": ["id1", "id2", ...], "auto_detect": true }
    """
    company_id = await get_active_company_id(request, current_user)
    
    transaction_ids = data.get('transaction_ids', [])
    auto_detect = data.get('auto_detect', True)
    
    if not transaction_ids:
        raise HTTPException(status_code=400, detail="Se requiere al menos un ID de transacción")
    
    results = []
    created = 0
    linked_with_cfdi = 0
    errors = 0
    
    for txn_id in transaction_ids:
        try:
            # Check if payment already exists for this bank transaction (prevent duplicates)
            existing_payment = await db.payments.find_one({
                'company_id': company_id,
                'bank_transaction_id': txn_id
            }, {'_id': 0, 'id': 1})
            
            if existing_payment:
                results.append({'transaction_id': txn_id, 'status': 'skipped', 'message': 'Ya tiene pago creado'})
                continue
            
            # Get the bank transaction
            txn = await db.bank_transactions.find_one({'id': txn_id, 'company_id': company_id}, {'_id': 0})
            if not txn:
                results.append({'transaction_id': txn_id, 'status': 'error', 'message': 'No encontrado'})
                errors += 1
                continue
            
            if txn.get('conciliado'):
                results.append({'transaction_id': txn_id, 'status': 'skipped', 'message': 'Ya conciliado'})
                continue
            
            # Get bank account info
            bank_account = await db.bank_accounts.find_one({'id': txn.get('bank_account_id')}, {'_id': 0})
            moneda = txn.get('moneda') or (bank_account.get('moneda') if bank_account else 'MXN')
            
            # Determine payment type
            tipo = 'cobro' if txn.get('tipo_movimiento') == 'credito' else 'pago'
            
            # Try to find matching CFDI if auto_detect is enabled
            matched_cfdi = None
            if auto_detect:
                monto = txn.get('monto', 0)
                fecha_txn_str = txn.get('fecha_movimiento')
                tipo_movimiento = txn.get('tipo_movimiento', 'credito')
                
                if isinstance(fecha_txn_str, str):
                    try:
                        fecha_txn = datetime.fromisoformat(fecha_txn_str.replace('Z', '+00:00'))
                    except:
                        fecha_txn = datetime.now(timezone.utc)
                else:
                    fecha_txn = fecha_txn_str or datetime.now(timezone.utc)
                
                fecha_inicio = (fecha_txn - timedelta(days=60)).isoformat()
                fecha_fin = (fecha_txn + timedelta(days=60)).isoformat()
                
                cfdi_tipo = 'ingreso' if tipo_movimiento == 'credito' else 'egreso'
                
                query = {
                    'company_id': company_id,
                    'tipo_cfdi': cfdi_tipo,
                    'estatus': 'vigente',
                    'fecha_emision': {'$gte': fecha_inicio, '$lte': fecha_fin}
                }
                
                cfdis = await db.cfdis.find(query, {'_id': 0}).to_list(50)
                
                best_score = 0
                best_cfdi = None
                
                for cfdi in cfdis:
                    cfdi_total = cfdi.get('total', 0)
                    monto_cubierto = cfdi.get('monto_cobrado' if cfdi_tipo == 'ingreso' else 'monto_pagado', 0) or 0
                    saldo_pendiente = cfdi_total - monto_cubierto
                    
                    if saldo_pendiente < 0.01:
                        continue
                    
                    score = 0
                    if monto > 0 and saldo_pendiente > 0:
                        diff_pct = abs(monto - saldo_pendiente) / saldo_pendiente * 100
                        if diff_pct < 0.5:
                            score += 50
                        elif diff_pct < 2:
                            score += 35
                        elif diff_pct < 5:
                            score += 20
                        elif diff_pct < 10:
                            score += 10
                        else:
                            continue
                    
                    cfdi_fecha_str = cfdi.get('fecha_emision')
                    if cfdi_fecha_str:
                        try:
                            cfdi_fecha = datetime.fromisoformat(cfdi_fecha_str.replace('Z', '+00:00')) if isinstance(cfdi_fecha_str, str) else cfdi_fecha_str
                            days_diff = abs((fecha_txn - cfdi_fecha).days)
                            if days_diff <= 7:
                                score += 30
                            elif days_diff <= 15:
                                score += 20
                            elif days_diff <= 30:
                                score += 10
                            else:
                                score += 5
                        except:
                            pass
                    
                    if cfdi.get('moneda', 'MXN') == moneda:
                        score += 10
                    
                    if score > best_score:
                        best_score = score
                        best_cfdi = cfdi
                
                if best_score >= 60 and best_cfdi:
                    matched_cfdi = best_cfdi
            
            # Create the payment
            payment_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            
            payment_doc = {
                'id': payment_id,
                'company_id': company_id,
                'bank_account_id': txn.get('bank_account_id'),
                'cfdi_id': matched_cfdi.get('id') if matched_cfdi else None,
                'tipo': tipo,
                'concepto': txn.get('descripcion') or f"Movimiento bancario {txn.get('referencia', '')}",
                'monto': txn.get('monto', 0),
                'moneda': moneda,
                'metodo_pago': 'transferencia',
                'fecha_vencimiento': txn.get('fecha_movimiento'),
                'fecha_pago': now.isoformat(),
                'estatus': 'completado',
                'referencia': txn.get('referencia', ''),
                'beneficiario': txn.get('merchant_name') or (txn.get('descripcion', '')[:50] if txn.get('descripcion') else ''),
                'es_real': True,
                'bank_transaction_id': txn_id,
                'created_at': now.isoformat()
            }
            
            await db.payments.insert_one(payment_doc)
            
            # Update CFDI if linked
            if matched_cfdi:
                if tipo == 'cobro':
                    current_cobrado = matched_cfdi.get('monto_cobrado', 0) or 0
                    new_cobrado = current_cobrado + payment_doc['monto']
                    await db.cfdis.update_one(
                        {'id': matched_cfdi['id']},
                        {'$set': {'monto_cobrado': new_cobrado}}
                    )
                else:
                    current_pagado = matched_cfdi.get('monto_pagado', 0) or 0
                    new_pagado = current_pagado + payment_doc['monto']
                    await db.cfdis.update_one(
                        {'id': matched_cfdi['id']},
                        {'$set': {'monto_pagado': new_pagado}}
                    )
                linked_with_cfdi += 1
            
            # Mark bank transaction as reconciled
            await db.bank_transactions.update_one(
                {'id': txn_id},
                {'$set': {
                    'conciliado': True,
                    'payment_id': payment_id,
                    'fecha_conciliacion': now.isoformat()
                }}
            )
            
            # Create reconciliation record
            recon_doc = {
                'id': str(uuid.uuid4()),
                'company_id': company_id,
                'bank_transaction_id': txn_id,
                'cfdi_id': matched_cfdi.get('id') if matched_cfdi else None,
                'metodo_conciliacion': 'automatica' if matched_cfdi else 'manual',
                'tipo_conciliacion': 'con_uuid' if matched_cfdi else 'sin_uuid',
                'porcentaje_match': 100,
                'fecha_conciliacion': now.isoformat(),
                'user_id': current_user['id'],
                'notas': 'Creado en lote desde módulo Cobranza y Pagos',
                'created_at': now.isoformat()
            }
            await db.reconciliations.insert_one(recon_doc)
            
            created += 1
            results.append({
                'transaction_id': txn_id,
                'payment_id': payment_id,
                'status': 'created',
                'tipo': tipo,
                'cfdi_linked': matched_cfdi is not None,
                'cfdi_uuid': matched_cfdi.get('uuid')[:8] + '...' if matched_cfdi else None
            })
            
        except Exception as e:
            logger.error(f"Error creating payment from txn {txn_id}: {e}")
            results.append({'transaction_id': txn_id, 'status': 'error', 'message': str(e)})
            errors += 1
    
    return {
        'status': 'success',
        'created': created,
        'linked_with_cfdi': linked_with_cfdi,
        'errors': errors,
        'results': results,
        'message': f'Se crearon {created} pagos/cobros' + 
                   (f', {linked_with_cfdi} vinculados con CFDI' if linked_with_cfdi > 0 else '') +
                   (f', {errors} errores' if errors > 0 else '')
    }


# GET /payments moved to routes/payments.py

@api_router.get("/payments/summary")
async def get_payments_summary(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    fecha_corte: Optional[str] = Query(None, description="Fecha de corte para totales")
):
    company_id = await get_active_company_id(request, current_user)
    
    if not fecha_corte:
        fecha_corte = (datetime.now(timezone.utc) + timedelta(days=15)).isoformat()
    
    # Get current exchange rate for USD -> MXN
    fx_rate_usd = await db.fx_rates.find_one(
        {'moneda_origen': 'USD', 'moneda_destino': 'MXN'},
        sort=[('timestamp', -1)]
    )
    usd_to_mxn = fx_rate_usd['tasa'] if fx_rate_usd else 17.5
    
    fx_rate_eur = await db.fx_rates.find_one(
        {'moneda_origen': 'EUR', 'moneda_destino': 'MXN'},
        sort=[('timestamp', -1)]
    )
    eur_to_mxn = fx_rate_eur['tasa'] if fx_rate_eur else 19.0
    
    def convert_to_mxn(monto, moneda):
        """Convert amount to MXN"""
        if not monto:
            return 0
        if moneda == 'USD':
            return monto * usd_to_mxn
        elif moneda == 'EUR':
            return monto * eur_to_mxn
        return monto  # Already MXN
    
    # Get all CFDIs to calculate pending amounts
    all_cfdis = await db.cfdis.find({
        'company_id': company_id,
        'estado_cancelacion': {'$ne': 'cancelado'}
    }, {'_id': 0}).to_list(5000)
    
    # Calculate pending amounts from CFDIs by currency
    total_por_cobrar_mxn = 0
    total_por_cobrar_usd = 0
    total_por_pagar_mxn = 0
    total_por_pagar_usd = 0
    cobros_pendientes_count = 0
    pagos_pendientes_count = 0
    
    for cfdi in all_cfdis:
        total = cfdi.get('total', 0) or 0
        moneda = cfdi.get('moneda', 'MXN')
        tipo = cfdi.get('tipo', '')
        
        if tipo == 'ingreso':
            monto_cobrado = cfdi.get('monto_cobrado', 0) or 0
            pendiente = total - monto_cobrado
            if pendiente > 0.01:
                if moneda == 'USD':
                    total_por_cobrar_usd += pendiente
                else:
                    total_por_cobrar_mxn += pendiente
                cobros_pendientes_count += 1
        elif tipo == 'egreso':
            monto_pagado = cfdi.get('monto_pagado', 0) or 0
            pendiente = total - monto_pagado
            if pendiente > 0.01:
                if moneda == 'USD':
                    total_por_pagar_usd += pendiente
                else:
                    total_por_pagar_mxn += pendiente
                pagos_pendientes_count += 1
    
    # Get completed payments this month by currency
    start_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    completed_payments = await db.payments.find({
        'company_id': company_id,
        'estatus': 'completado',
        'fecha_pago': {'$gte': start_of_month.isoformat()}
    }, {'_id': 0}).to_list(1000)
    
    # Calculate paid/collected this month by currency
    pagado_mes_mxn = 0
    pagado_mes_usd = 0
    cobrado_mes_mxn = 0
    cobrado_mes_usd = 0
    
    for p in completed_payments:
        monto = p.get('monto', 0) or 0
        moneda = p.get('moneda', 'MXN')
        if p['tipo'] == 'pago':
            if moneda == 'USD':
                pagado_mes_usd += monto
            else:
                pagado_mes_mxn += monto
        else:  # cobro
            if moneda == 'USD':
                cobrado_mes_usd += monto
            else:
                cobrado_mes_mxn += monto
    
    # Get pending payments with domiciliacion
    pending_payments = await db.payments.find({
        'company_id': company_id,
        'estatus': 'pendiente'
    }, {'_id': 0}).to_list(1000)
    
    domiciliados = [p for p in pending_payments if p.get('domiciliacion_activa')]
    monto_domiciliado = sum(
        convert_to_mxn(p['monto'], p.get('moneda', 'MXN')) 
        for p in domiciliados
    )
    
    # Calculate totals in MXN
    total_por_cobrar_total = total_por_cobrar_mxn + convert_to_mxn(total_por_cobrar_usd, 'USD')
    total_por_pagar_total = total_por_pagar_mxn + convert_to_mxn(total_por_pagar_usd, 'USD')
    total_pagado_mes = pagado_mes_mxn + convert_to_mxn(pagado_mes_usd, 'USD')
    total_cobrado_mes = cobrado_mes_mxn + convert_to_mxn(cobrado_mes_usd, 'USD')
    
    return {
        'fecha_corte': fecha_corte,
        'total_por_pagar': round(total_por_pagar_total, 2),
        'total_por_pagar_mxn': round(total_por_pagar_mxn, 2),
        'total_por_pagar_usd': round(total_por_pagar_usd, 2),
        'total_por_cobrar': round(total_por_cobrar_total, 2),
        'total_por_cobrar_mxn': round(total_por_cobrar_mxn, 2),
        'total_por_cobrar_usd': round(total_por_cobrar_usd, 2),
        'pagos_pendientes': pagos_pendientes_count,
        'cobros_pendientes': cobros_pendientes_count,
        'total_pagado_mes': round(total_pagado_mes, 2),
        'pagado_mes_mxn': round(pagado_mes_mxn, 2),
        'pagado_mes_usd': round(pagado_mes_usd, 2),
        'total_cobrado_mes': round(total_cobrado_mes, 2),
        'cobrado_mes_mxn': round(cobrado_mes_mxn, 2),
        'cobrado_mes_usd': round(cobrado_mes_usd, 2),
        'domiciliaciones_activas': len(domiciliados),
        'monto_domiciliado': round(monto_domiciliado, 2),
        'tc_usd': usd_to_mxn,
        'tc_eur': eur_to_mxn
    }


@api_router.get("/payments/breakdown")
async def get_payments_breakdown(
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """
    Get complete breakdown for Cobranza y Pagos module.
    
    Source of truth: Bank reconciliations
    - Cobrado = Reconciled deposits (créditos)
    - Pagado = Reconciled withdrawals (débitos)
    - Por Cobrar / Por Pagar = From CFDIs pending
    - Proyecciones = For variance analysis
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Get FX rates
    fx_rate_usd = await db.fx_rates.find_one(
        {'company_id': company_id, '$or': [{'moneda_cotizada': 'USD'}, {'moneda_origen': 'USD'}]},
        {'_id': 0},
        sort=[('fecha_vigencia', -1)]
    )
    usd_to_mxn = fx_rate_usd.get('tipo_cambio') or fx_rate_usd.get('tasa') if fx_rate_usd else 17.5
    
    def convert_to_mxn(monto, moneda):
        if not monto:
            return 0
        if moneda == 'USD':
            return monto * usd_to_mxn
        return monto
    
    # ===== SECTION 1: FROM CFDI / SAT (PENDING) =====
    all_cfdis = await db.cfdis.find({
        'company_id': company_id,
        'estatus': 'vigente'
    }, {'_id': 0}).to_list(5000)
    
    por_cobrar_list = []
    total_por_cobrar_mxn = 0
    total_por_cobrar_usd = 0
    
    por_pagar_list = []
    total_por_pagar_mxn = 0
    total_por_pagar_usd = 0
    
    for cfdi in all_cfdis:
        total = cfdi.get('total', 0) or 0
        moneda = cfdi.get('moneda', 'MXN')
        tipo_cfdi = cfdi.get('tipo_cfdi', cfdi.get('tipo', ''))
        
        if tipo_cfdi == 'ingreso':
            monto_cobrado = cfdi.get('monto_cobrado', 0) or 0
            pendiente = total - monto_cobrado
            if pendiente > 0.01:
                por_cobrar_list.append({
                    'cfdi_id': cfdi.get('id'),
                    'uuid': cfdi.get('uuid', '')[:8] + '...' if cfdi.get('uuid') else '',
                    'emisor': cfdi.get('emisor_nombre', ''),
                    'receptor': cfdi.get('receptor_nombre', ''),
                    'fecha': cfdi.get('fecha_emision'),
                    'total': total,
                    'cobrado': monto_cobrado,
                    'pendiente': pendiente,
                    'moneda': moneda
                })
                if moneda == 'USD':
                    total_por_cobrar_usd += pendiente
                else:
                    total_por_cobrar_mxn += pendiente
                    
        elif tipo_cfdi == 'egreso':
            monto_pagado = cfdi.get('monto_pagado', 0) or 0
            pendiente = total - monto_pagado
            if pendiente > 0.01:
                por_pagar_list.append({
                    'cfdi_id': cfdi.get('id'),
                    'uuid': cfdi.get('uuid', '')[:8] + '...' if cfdi.get('uuid') else '',
                    'emisor': cfdi.get('emisor_nombre', ''),
                    'receptor': cfdi.get('receptor_nombre', ''),
                    'fecha': cfdi.get('fecha_emision'),
                    'total': total,
                    'pagado': monto_pagado,
                    'pendiente': pendiente,
                    'moneda': moneda
                })
                if moneda == 'USD':
                    total_por_pagar_usd += pendiente
                else:
                    total_por_pagar_mxn += pendiente
    
    # ===== SECTION 2: FROM BANK RECONCILIATIONS (SOURCE OF TRUTH) =====
    # Get all reconciled bank transactions
    reconciled_txns = await db.bank_transactions.find({
        'company_id': company_id,
        'conciliado': True
    }, {'_id': 0}).to_list(10000)
    
    # Get reconciliation details
    all_reconciliations = await db.reconciliations.find({
        'company_id': company_id
    }, {'_id': 0}).to_list(10000)
    
    recon_by_txn = {r.get('bank_transaction_id'): r for r in all_reconciliations}
    
    # Get bank accounts for reference
    bank_accounts = await db.bank_accounts.find({'company_id': company_id}, {'_id': 0}).to_list(100)
    account_map = {a['id']: a for a in bank_accounts}
    
    # Cobrado (deposits = créditos conciliados)
    cobrado_list = []
    total_cobrado_mxn = 0
    total_cobrado_usd = 0
    cobrado_con_cfdi_count = 0
    cobrado_sin_cfdi_count = 0
    
    # Pagado (withdrawals = débitos conciliados)
    pagado_list = []
    total_pagado_mxn = 0
    total_pagado_usd = 0
    pagado_con_cfdi_count = 0
    pagado_sin_cfdi_count = 0
    
    for txn in reconciled_txns:
        monto = txn.get('monto', 0) or 0
        moneda = txn.get('moneda', 'MXN')
        tipo_mov = txn.get('tipo_movimiento', '')
        
        # Get account info
        account = account_map.get(txn.get('bank_account_id'), {})
        banco = account.get('banco', '')
        cuenta_nombre = account.get('nombre', '')
        
        # Get reconciliation info
        recon = recon_by_txn.get(txn.get('id'), {})
        cfdi_id = recon.get('cfdi_id')
        tipo_conciliacion = recon.get('tipo_conciliacion', 'sin_uuid')
        
        item = {
            'id': txn.get('id'),
            'fecha': txn.get('fecha_movimiento'),
            'descripcion': txn.get('descripcion', '')[:80],
            'referencia': txn.get('referencia', ''),
            'monto': monto,
            'moneda': moneda,
            'banco': banco,
            'cuenta': cuenta_nombre,
            'cfdi_id': cfdi_id,
            'tipo_conciliacion': tipo_conciliacion,
            'tiene_cfdi': cfdi_id is not None
        }
        
        if tipo_mov == 'credito':
            # Deposit = Cobrado
            cobrado_list.append(item)
            if moneda == 'USD':
                total_cobrado_usd += monto
            else:
                total_cobrado_mxn += monto
            
            if cfdi_id:
                cobrado_con_cfdi_count += 1
            else:
                cobrado_sin_cfdi_count += 1
        else:
            # Withdrawal = Pagado
            pagado_list.append(item)
            if moneda == 'USD':
                total_pagado_usd += monto
            else:
                total_pagado_mxn += monto
            
            if cfdi_id:
                pagado_con_cfdi_count += 1
            else:
                pagado_sin_cfdi_count += 1
    
    # Sort by date descending
    cobrado_list.sort(key=lambda x: x.get('fecha', ''), reverse=True)
    pagado_list.sort(key=lambda x: x.get('fecha', ''), reverse=True)
    
    # ===== SECTION 3: PROJECTIONS =====
    projections = await db.manual_projections.find({
        'company_id': company_id,
        'activo': True
    }, {'_id': 0}).to_list(500)
    
    proyeccion_cobros = []
    proyeccion_pagos = []
    total_proyeccion_cobros_mxn = 0
    total_proyeccion_pagos_mxn = 0
    
    for proj in projections:
        monto = proj.get('monto', 0) or 0
        moneda = proj.get('moneda', 'MXN')
        tipo = proj.get('tipo', 'egreso')
        
        item = {
            'id': proj.get('id'),
            'nombre': proj.get('nombre', ''),
            'monto': monto,
            'moneda': moneda,
            'semana': proj.get('semana'),
            'mes': proj.get('mes'),
            'recurrente': proj.get('recurrente', False),
            'categoria': proj.get('categoria', '')
        }
        
        monto_mxn = convert_to_mxn(monto, moneda)
        
        if tipo == 'ingreso':
            proyeccion_cobros.append(item)
            total_proyeccion_cobros_mxn += monto_mxn
        else:
            proyeccion_pagos.append(item)
            total_proyeccion_pagos_mxn += monto_mxn
    
    # ===== CALCULATE VARIANCE =====
    total_real_cobros = total_cobrado_mxn + convert_to_mxn(total_cobrado_usd, 'USD')
    total_real_pagos = total_pagado_mxn + convert_to_mxn(total_pagado_usd, 'USD')
    
    varianza_cobros = total_real_cobros - total_proyeccion_cobros_mxn
    varianza_pagos = total_real_pagos - total_proyeccion_pagos_mxn
    
    return {
        # Section 1: Por Cobrar / Por Pagar (from CFDI/SAT - PENDING)
        'cfdi_por_cobrar': {
            'items': por_cobrar_list[:50],
            'total_count': len(por_cobrar_list),
            'total_mxn': round(total_por_cobrar_mxn, 2),
            'total_usd': round(total_por_cobrar_usd, 2),
            'total_equiv_mxn': round(total_por_cobrar_mxn + convert_to_mxn(total_por_cobrar_usd, 'USD'), 2)
        },
        'cfdi_por_pagar': {
            'items': por_pagar_list[:50],
            'total_count': len(por_pagar_list),
            'total_mxn': round(total_por_pagar_mxn, 2),
            'total_usd': round(total_por_pagar_usd, 2),
            'total_equiv_mxn': round(total_por_pagar_mxn + convert_to_mxn(total_por_pagar_usd, 'USD'), 2)
        },
        
        # Section 2: Cobrado / Pagado (from RECONCILED bank transactions - SOURCE OF TRUTH)
        'cobrado': {
            'items': cobrado_list[:100],
            'total_count': len(cobrado_list),
            'total_mxn': round(total_cobrado_mxn, 2),
            'total_usd': round(total_cobrado_usd, 2),
            'total_equiv_mxn': round(total_cobrado_mxn + convert_to_mxn(total_cobrado_usd, 'USD'), 2),
            'con_cfdi': cobrado_con_cfdi_count,
            'sin_cfdi': cobrado_sin_cfdi_count
        },
        'pagado': {
            'items': pagado_list[:100],
            'total_count': len(pagado_list),
            'total_mxn': round(total_pagado_mxn, 2),
            'total_usd': round(total_pagado_usd, 2),
            'total_equiv_mxn': round(total_pagado_mxn + convert_to_mxn(total_pagado_usd, 'USD'), 2),
            'con_cfdi': pagado_con_cfdi_count,
            'sin_cfdi': pagado_sin_cfdi_count
        },
        
        # Section 3: Proyecciones
        'proyeccion_cobros': {
            'items': proyeccion_cobros[:50],
            'total_count': len(proyeccion_cobros),
            'total_equiv_mxn': round(total_proyeccion_cobros_mxn, 2)
        },
        'proyeccion_pagos': {
            'items': proyeccion_pagos[:50],
            'total_count': len(proyeccion_pagos),
            'total_equiv_mxn': round(total_proyeccion_pagos_mxn, 2)
        },
        
        # Section 4: Variance Summary
        'varianza': {
            'cobros_real_vs_proyectado': round(varianza_cobros, 2),
            'cobros_pct': round((varianza_cobros / total_proyeccion_cobros_mxn * 100), 1) if total_proyeccion_cobros_mxn > 0 else 0,
            'pagos_real_vs_proyectado': round(varianza_pagos, 2),
            'pagos_pct': round((varianza_pagos / total_proyeccion_pagos_mxn * 100), 1) if total_proyeccion_pagos_mxn > 0 else 0,
            'flujo_neto_real': round(total_real_cobros - total_real_pagos, 2),
            'flujo_neto_proyectado': round(total_proyeccion_cobros_mxn - total_proyeccion_pagos_mxn, 2)
        },
        
        'tc_usd': usd_to_mxn
    }

# PUT /payments/{id}, POST /payments/{id}/complete, DELETE /payments/{id}, DELETE /payments/bulk/all
# moved to routes/payments.py

# DELETE /reconciliations/bulk/all moved to routes/reconciliations.py

# ==================== CATEGORIES/SUBCATEGORIES ENDPOINTS MOVED TO routes/categories.py ====================
# The following endpoints are now handled by routes/categories.py:
# - GET /categories
# - POST /categories
# - PUT /categories/{category_id}
# - DELETE /categories/{category_id}
# - POST /subcategories
# - DELETE /subcategories/{subcategory_id}


# ===== CATEGORIZACIÓN AUTOMÁTICA CON IA =====
from ai_categorization_service import categorize_cfdi_with_ai, batch_categorize_cfdis

@api_router.post("/cfdi/{cfdi_id}/ai-categorize")
async def ai_categorize_single_cfdi(cfdi_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Use AI to suggest a category for a single CFDI"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get the CFDI
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0, 'xml_original': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    # Get available categories for this company (matching the CFDI type)
    categories = await db.categories.find({
        'company_id': company_id, 
        'activo': True,
        'tipo': cfdi.get('tipo_cfdi', 'egreso')
    }, {'_id': 0}).to_list(100)
    
    # Get subcategories for each category
    for cat in categories:
        subcats = await db.subcategories.find({'category_id': cat['id'], 'activo': True}, {'_id': 0}).to_list(100)
        cat['subcategorias'] = subcats
    
    if not categories:
        return {
            'success': False,
            'error': f'No hay categorías de tipo "{cfdi.get("tipo_cfdi", "egreso")}" disponibles',
            'suggestion': None
        }
    
    # Call AI service
    result = await categorize_cfdi_with_ai(cfdi, categories)
    
    return {
        'success': result.get('success', False),
        'cfdi_id': cfdi_id,
        'cfdi_uuid': cfdi.get('uuid'),
        'suggestion': {
            'category_id': result.get('category_id'),
            'subcategory_id': result.get('subcategory_id'),
            'confidence': result.get('confidence', 0),
            'reasoning': result.get('reasoning', '')
        },
        'error': result.get('error')
    }

@api_router.post("/cfdi/ai-categorize-batch")
async def ai_categorize_batch_cfdis(request: Request, current_user: Dict = Depends(get_current_user), apply_suggestions: bool = Query(False, description="Apply high-confidence suggestions automatically")):
    """Use AI to categorize all uncategorized CFDIs"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get uncategorized CFDIs
    uncategorized_cfdis = await db.cfdis.find({
        'company_id': company_id,
        '$or': [
            {'category_id': None},
            {'category_id': {'$exists': False}}
        ]
    }, {'_id': 0, 'xml_original': 0}).to_list(100)
    
    if not uncategorized_cfdis:
        return {
            'success': True,
            'message': 'No hay CFDIs sin categorizar',
            'processed': 0,
            'results': []
        }
    
    # Get all categories
    categories = await db.categories.find({'company_id': company_id, 'activo': True}, {'_id': 0}).to_list(100)
    for cat in categories:
        subcats = await db.subcategories.find({'category_id': cat['id'], 'activo': True}, {'_id': 0}).to_list(100)
        cat['subcategorias'] = subcats
    
    # Process each CFDI
    results = []
    applied_count = 0
    
    for cfdi in uncategorized_cfdis:
        # Filter categories by CFDI type
        matching_categories = [c for c in categories if c['tipo'] == cfdi.get('tipo_cfdi', 'egreso')]
        
        if not matching_categories:
            results.append({
                'cfdi_id': cfdi['id'],
                'cfdi_uuid': cfdi.get('uuid'),
                'success': False,
                'error': f'No hay categorías de tipo "{cfdi.get("tipo_cfdi", "egreso")}"'
            })
            continue
        
        result = await categorize_cfdi_with_ai(cfdi, matching_categories)
        
        # Apply suggestion if high confidence and apply_suggestions is True
        if apply_suggestions and result.get('success') and result.get('confidence', 0) >= 70:
            update_data = {}
            if result.get('category_id'):
                update_data['category_id'] = result['category_id']
            if result.get('subcategory_id'):
                update_data['subcategory_id'] = result['subcategory_id']
            
            if update_data:
                await db.cfdis.update_one({'id': cfdi['id']}, {'$set': update_data})
                await audit_log(company_id, 'CFDI', cfdi['id'], 'AI_CATEGORIZE', current_user['id'])
                result['applied'] = True
                applied_count += 1
            else:
                result['applied'] = False
        else:
            result['applied'] = False
        
        results.append({
            'cfdi_id': cfdi['id'],
            'cfdi_uuid': cfdi.get('uuid'),
            'emisor': cfdi.get('emisor_nombre', cfdi.get('emisor_rfc')),
            'total': cfdi.get('total'),
            **result
        })
    
    return {
        'success': True,
        'processed': len(uncategorized_cfdis),
        'applied': applied_count,
        'results': results
    }

# ===== CATEGORIZAR CFDI/TRANSACCIÓN =====
@api_router.put("/cfdi/{cfdi_id}/categorize")
async def categorize_cfdi(
    cfdi_id: str, 
    request: Request, 
    current_user: Dict = Depends(get_current_user), 
    category_id: str = None, 
    subcategory_id: str = None, 
    customer_id: str = None,
    vendor_id: str = None,
    etiquetas: List[str] = None
):
    company_id = await get_active_company_id(request, current_user)
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    update_data = {}
    if category_id:
        update_data['category_id'] = category_id
    if subcategory_id:
        update_data['subcategory_id'] = subcategory_id
    if customer_id:
        update_data['customer_id'] = customer_id
    if vendor_id:
        update_data['vendor_id'] = vendor_id
    if etiquetas is not None:
        update_data['etiquetas'] = etiquetas
    
    await db.cfdis.update_one({'id': cfdi_id}, {'$set': update_data})
    await audit_log(company_id, 'CFDI', cfdi_id, 'CATEGORIZE', current_user['id'])
    return {'status': 'success', 'message': 'CFDI categorizado'}

@api_router.put("/cfdi/{cfdi_id}/reconciliation-status")
async def update_cfdi_reconciliation(cfdi_id: str, status: str, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    if status not in ['pendiente', 'conciliado', 'no_conciliable']:
        raise HTTPException(status_code=400, detail="Estado inválido")
    
    await db.cfdis.update_one({'id': cfdi_id}, {'$set': {'estado_conciliacion': status}})
    await audit_log(company_id, 'CFDI', cfdi_id, 'UPDATE_RECONCILIATION', current_user['id'])
    return {'status': 'success', 'message': f'Estado actualizado a {status}'}

@api_router.put("/cfdi/{cfdi_id}/notes")
async def update_cfdi_notes(cfdi_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Update notes for a CFDI"""
    company_id = await get_active_company_id(request, current_user)
    cfdi = await db.cfdis.find_one({'id': cfdi_id, 'company_id': company_id}, {'_id': 0})
    if not cfdi:
        raise HTTPException(status_code=404, detail="CFDI no encontrado")
    
    body = await request.json()
    notas = body.get('notas', '')
    
    await db.cfdis.update_one({'id': cfdi_id}, {'$set': {'notas': notas}})
    await audit_log(company_id, 'CFDI', cfdi_id, 'UPDATE_NOTES', current_user['id'])
    return {'status': 'success', 'message': 'Notas actualizadas'}

# ===== DIOT (Declaración Informativa de Operaciones con Terceros) =====
@api_router.get("/diot/preview")
async def get_diot_preview(request: Request, current_user: Dict = Depends(get_current_user), fecha_desde: str = None, fecha_hasta: str = None):
    """
    Get DIOT data preview - ONLY PAID EGRESO CFDIs WITH IVA ACREDITABLE
    
    IMPORTANT: DIOT only includes CFDIs that:
    1. Are type 'egreso' (expenses)
    2. Have been PAID (pagados) - via payment record or bank reconciliation
    3. Generate IVA acreditable (IVA > 0)
    
    EXCLUSIONS (per SAT rules):
    - Nómina (uso_cfdi = 'CN01' or tipo_comprobante = 'N')
    - CFDIs with no IVA (no IVA acreditable to report)
    - Sueldos y salarios
    - Asimilados a salarios
    
    The date filter is based on PAYMENT DATE, not emission date.
    """
    company_id = await get_active_company_id(request, current_user)
    
    # Get all EGRESO CFDIs EXCLUDING NOMINA and non-IVA items
    # DIOT exclusions: CN01 (sin efectos fiscales/nómina), tipo_comprobante='N' (nómina)
    cfdi_query = {
        'company_id': company_id,
        'tipo_cfdi': 'egreso',
        # Exclude nómina and non-deductible items
        'uso_cfdi': {'$nin': ['CN01', 'CP01', 'D01', 'D02', 'D03', 'D04', 'D05', 'D06', 'D07', 'D08', 'D09', 'D10']},
        # Must have IVA acreditable
        '$or': [
            {'impuestos': {'$gt': 0}},
            {'iva_trasladado': {'$gt': 0}}
        ]
    }
    cfdis = await db.cfdis.find(cfdi_query, {'_id': 0}).to_list(10000)
    
    # Get categories
    categories = {c['id']: c for c in await db.categories.find({'company_id': company_id}, {'_id': 0}).to_list(1000)}
    subcategories = {s['id']: s for s in await db.subcategories.find({'company_id': company_id}, {'_id': 0}).to_list(1000)}
    
    # Get payments to check which CFDIs are paid
    payments = await db.payments.find({'company_id': company_id, 'tipo': 'pago', 'estatus': 'completado'}, {'_id': 0}).to_list(10000)
    payments_by_cfdi = {}
    for p in payments:
        cfdi_id = p.get('cfdi_id')
        if cfdi_id:
            if cfdi_id not in payments_by_cfdi:
                payments_by_cfdi[cfdi_id] = []
            payments_by_cfdi[cfdi_id].append(p)
    
    # Get reconciliations to find bank transaction info (for TC from bank statement)
    reconciliations = await db.reconciliations.find({'company_id': company_id}, {'_id': 0}).to_list(10000)
    recon_by_cfdi = {r['cfdi_id']: r for r in reconciliations if r.get('cfdi_id')}
    
    # Get bank transactions (for payment date and TC)
    bank_txns = await db.bank_transactions.find({'company_id': company_id}, {'_id': 0}).to_list(10000)
    bank_txn_by_id = {t['id']: t for t in bank_txns}
    
    # Parse date filters
    fecha_desde_dt = None
    fecha_hasta_dt = None
    if fecha_desde:
        try:
            fecha_desde_dt = datetime.fromisoformat(fecha_desde.replace('Z', '+00:00')) if 'T' in fecha_desde else datetime.strptime(fecha_desde, '%Y-%m-%d')
        except:
            pass
    if fecha_hasta:
        try:
            fecha_hasta_dt = datetime.fromisoformat(fecha_hasta.replace('Z', '+00:00')) if 'T' in fecha_hasta else datetime.strptime(fecha_hasta, '%Y-%m-%d')
            fecha_hasta_dt = fecha_hasta_dt.replace(hour=23, minute=59, second=59)
        except:
            pass
    
    # Cache for FX rates by date
    fx_rates_cache = {}
    
    async def get_fx_rate_for_date(moneda: str, fecha: str) -> float:
        """Get FX rate for a specific date, with caching"""
        cache_key = f"{moneda}_{fecha[:10]}"
        if cache_key in fx_rates_cache:
            return fx_rates_cache[cache_key]
        
        # Try to find exact date rate
        rate = await db.fx_rates.find_one({
            'company_id': company_id,
            '$or': [
                {'moneda_cotizada': moneda},
                {'moneda_origen': moneda}
            ],
            'fecha_vigencia': {'$regex': f'^{fecha[:10]}'}
        }, {'_id': 0})
        
        if rate:
            tc = rate.get('tipo_cambio') or rate.get('tasa') or 1
            fx_rates_cache[cache_key] = tc
            return tc
        
        # Fallback: find closest rate before the date
        rate = await db.fx_rates.find_one({
            'company_id': company_id,
            '$or': [
                {'moneda_cotizada': moneda},
                {'moneda_origen': moneda}
            ],
            'fecha_vigencia': {'$lte': fecha}
        }, {'_id': 0}, sort=[('fecha_vigencia', -1)])
        
        if rate:
            tc = rate.get('tipo_cambio') or rate.get('tasa') or 1
            fx_rates_cache[cache_key] = tc
            return tc
        
        # Default fallback
        default_rate = 17.5 if moneda == 'USD' else 19.0 if moneda == 'EUR' else 1
        fx_rates_cache[cache_key] = default_rate
        return default_rate
    
    records = []
    total_iva_acreditable = 0
    total_iva_retenido = 0
    total_monto = 0
    total_monto_mxn = 0
    
    for cfdi in cfdis:
        # Get CFDI currency
        moneda = cfdi.get('moneda', 'MXN')
        
        # Get payment info if exists
        cfdi_payments = payments_by_cfdi.get(cfdi['id'], [])
        fecha_pago_str = ''
        pagado = False
        tipo_cambio_pago = 1.0
        fecha_pago_dt = None
        
        # Check if paid via payment record
        if cfdi_payments:
            pagado = True
            latest_payment = max(cfdi_payments, key=lambda p: p.get('fecha_pago', datetime.min) if p.get('fecha_pago') else datetime.min)
            fecha_pago = latest_payment.get('fecha_pago')
            if fecha_pago:
                if isinstance(fecha_pago, datetime):
                    fecha_pago_str = fecha_pago.strftime('%Y-%m-%d')
                    fecha_pago_dt = fecha_pago
                else:
                    fecha_pago_str = str(fecha_pago)[:10]
                    try:
                        fecha_pago_dt = datetime.fromisoformat(str(fecha_pago).replace('Z', '+00:00'))
                    except:
                        pass
            # Use stored TC if available
            if latest_payment.get('tipo_cambio_historico'):
                tipo_cambio_pago = latest_payment.get('tipo_cambio_historico')
        
        # Also check if paid via reconciliation (bank transaction)
        recon = recon_by_cfdi.get(cfdi['id'])
        if recon and not pagado:
            bank_txn = bank_txn_by_id.get(recon.get('bank_transaction_id'))
            if bank_txn:
                pagado = True
                fecha_mov = bank_txn.get('fecha_movimiento')
                if fecha_mov:
                    if isinstance(fecha_mov, datetime):
                        fecha_pago_str = fecha_mov.strftime('%Y-%m-%d')
                        fecha_pago_dt = fecha_mov
                    else:
                        fecha_pago_str = str(fecha_mov)[:10]
                        try:
                            fecha_pago_dt = datetime.fromisoformat(str(fecha_mov).replace('Z', '+00:00'))
                        except:
                            pass
        elif recon and pagado:
            # Already paid but reconciled - use bank transaction date as fecha_pago
            bank_txn = bank_txn_by_id.get(recon.get('bank_transaction_id'))
            if bank_txn:
                fecha_mov = bank_txn.get('fecha_movimiento')
                if fecha_mov:
                    if isinstance(fecha_mov, datetime):
                        fecha_pago_str = fecha_mov.strftime('%Y-%m-%d')
                        fecha_pago_dt = fecha_mov
                    else:
                        fecha_pago_str = str(fecha_mov)[:10]
                        try:
                            fecha_pago_dt = datetime.fromisoformat(str(fecha_mov).replace('Z', '+00:00'))
                        except:
                            pass
        
        # DIOT ONLY INCLUDES PAID CFDIs - Skip unpaid ones
        if not pagado:
            continue
        
        # Filter by payment date if date range is specified
        if fecha_pago_dt:
            # Normalize to naive datetime for comparison
            fecha_pago_naive = fecha_pago_dt.replace(tzinfo=None) if hasattr(fecha_pago_dt, 'tzinfo') and fecha_pago_dt.tzinfo else fecha_pago_dt
            if fecha_desde_dt:
                fecha_desde_naive = fecha_desde_dt.replace(tzinfo=None) if hasattr(fecha_desde_dt, 'tzinfo') and fecha_desde_dt.tzinfo else fecha_desde_dt
                if fecha_pago_naive < fecha_desde_naive:
                    continue
            if fecha_hasta_dt:
                fecha_hasta_naive = fecha_hasta_dt.replace(tzinfo=None) if hasattr(fecha_hasta_dt, 'tzinfo') and fecha_hasta_dt.tzinfo else fecha_hasta_dt
                if fecha_pago_naive > fecha_hasta_naive:
                    continue
        elif fecha_desde_dt or fecha_hasta_dt:
            # If we have date filters but no payment date, skip this record
            continue
        
        # Get FX rate for payment date if currency is not MXN
        if moneda != 'MXN' and fecha_pago_str:
            tipo_cambio_pago = await get_fx_rate_for_date(moneda, fecha_pago_str)
        elif moneda != 'MXN':
            # Use emission date FX rate as fallback
            fecha_emision = cfdi.get('fecha_emision', '')
            if fecha_emision:
                fecha_str = fecha_emision.strftime('%Y-%m-%d') if isinstance(fecha_emision, datetime) else str(fecha_emision)[:10]
                tipo_cambio_pago = await get_fx_rate_for_date(moneda, fecha_str)
        
        # Determine tipo_tercero based on RFC
        rfc = cfdi.get('emisor_rfc', '')
        if len(rfc) == 13:
            tipo_tercero = '04'  # Persona Moral Nacional
            tipo_tercero_desc = 'Proveedor Nacional (PM)'
        elif len(rfc) == 12:
            tipo_tercero = '04'  # Persona Física Nacional
            tipo_tercero_desc = 'Proveedor Nacional (PF)'
        elif rfc.startswith('XEXX') or rfc.startswith('XAXX'):
            tipo_tercero = '05'  # Extranjero
            tipo_tercero_desc = 'Proveedor Extranjero'
        else:
            tipo_tercero = '04'
            tipo_tercero_desc = 'Proveedor Nacional'
        
        subtotal = cfdi.get('subtotal', 0) or 0
        impuestos = cfdi.get('impuestos', 0) or 0
        total = cfdi.get('total', 0) or 0
        
        # Calculate MXN amounts
        subtotal_mxn = subtotal * tipo_cambio_pago if moneda != 'MXN' else subtotal
        total_mxn = total * tipo_cambio_pago if moneda != 'MXN' else total
        
        # Get IVA components from CFDI (parsed from XML)
        # IVA acreditable (trasladado)
        iva_acreditable = cfdi.get('iva_trasladado', 0) or impuestos
        if iva_acreditable == 0 and impuestos > 0:
            iva_acreditable = impuestos
        
        # IVA retenido (from CFDI) - check both field names for compatibility
        iva_retenido = cfdi.get('iva_retenido', 0) or cfdi.get('retencion_iva', 0) or 0
        
        # ISR retenido (if present) - check both field names for compatibility
        isr_retenido = cfdi.get('isr_retenido', 0) or cfdi.get('retencion_isr', 0) or 0
        
        # Convert IVA to MXN
        iva_acreditable_mxn = iva_acreditable * tipo_cambio_pago if moneda != 'MXN' else iva_acreditable
        iva_retenido_mxn = iva_retenido * tipo_cambio_pago if moneda != 'MXN' else iva_retenido
        isr_retenido_mxn = isr_retenido * tipo_cambio_pago if moneda != 'MXN' else isr_retenido
        
        categoria = categories.get(cfdi.get('category_id'), {}).get('nombre', '')
        subcategoria = subcategories.get(cfdi.get('subcategory_id'), {}).get('nombre', '')
        
        # Get fecha emision
        fecha_emision = cfdi.get('fecha_emision', '')
        if isinstance(fecha_emision, datetime):
            fecha_emision_str = fecha_emision.strftime('%Y-%m-%d')
        else:
            fecha_emision_str = str(fecha_emision)[:10] if fecha_emision else ''
        
        records.append({
            'tipo_tercero': tipo_tercero,
            'tipo_tercero_desc': tipo_tercero_desc,
            'tipo_operacion': '85',  # Otros (default)
            'tipo_operacion_desc': 'Otros',
            'rfc': rfc,
            'nombre': cfdi.get('emisor_nombre', ''),
            'pais': 'MX',
            'nacionalidad': 'Nacional',
            # Original amounts (in CFDI currency)
            'moneda': moneda,
            'valor_actos_pagados': total,
            'subtotal': subtotal,
            # MXN amounts (converted)
            'valor_actos_pagados_mxn': round(total_mxn, 2),
            'subtotal_mxn': round(subtotal_mxn, 2),
            'tipo_cambio': round(tipo_cambio_pago, 4),
            # For DIOT report (always in MXN)
            'valor_actos_0': 0,
            'valor_actos_exentos': 0,
            'valor_actos_16': round(subtotal_mxn, 2),
            'iva_retenido': round(iva_retenido_mxn, 2),
            'isr_retenido': round(isr_retenido_mxn, 2),
            'iva_acreditable': round(iva_acreditable_mxn, 2),
            # Original IVA (in CFDI currency)
            'iva_retenido_original': round(iva_retenido, 2),
            'isr_retenido_original': round(isr_retenido, 2),
            'iva_acreditable_original': round(iva_acreditable, 2),
            # Dates
            'fecha_emision': fecha_emision_str,
            'fecha_pago': fecha_pago_str,
            'pagado': pagado,
            'uuid': cfdi.get('uuid', ''),
            'categoria': categoria,
            'subcategoria': subcategoria,
            'cfdi_id': cfdi.get('id', '')
        })
        
        total_iva_acreditable += iva_acreditable_mxn
        total_iva_retenido += iva_retenido_mxn
        total_monto += total
        total_monto_mxn += total_mxn
    
    return {
        'records': records,
        'summary': {
            'totalOperaciones': len(records),
            'totalIVA': round(total_iva_acreditable, 2),
            'totalIVARetenido': round(total_iva_retenido, 2),
            'totalMonto': round(total_monto, 2),
            'totalMontoMXN': round(total_monto_mxn, 2)
        }
    }

# ===== EXPORTAR DIOT =====
@api_router.get("/export/diot")
async def export_diot(request: Request, current_user: Dict = Depends(get_current_user), fecha_desde: str = None, fecha_hasta: str = None):
    """Export CFDIs in DIOT format (CSV) - ONLY EGRESO WITH IVA, EXCLUDES NOMINA"""
    from fastapi.responses import StreamingResponse
    import io
    import csv
    
    company_id = await get_active_company_id(request, current_user)
    
    # DIOT query: Only egreso CFDIs with IVA acreditable, excluding nómina
    query = {
        'company_id': company_id,
        'tipo_cfdi': 'egreso',
        # Exclude nómina and non-deductible items (CN01 = sin efectos fiscales / nómina)
        'uso_cfdi': {'$nin': ['CN01', 'CP01', 'D01', 'D02', 'D03', 'D04', 'D05', 'D06', 'D07', 'D08', 'D09', 'D10']},
        # Must have IVA acreditable
        '$or': [
            {'impuestos': {'$gt': 0}},
            {'iva_trasladado': {'$gt': 0}}
        ]
    }
    if fecha_desde:
        query['fecha_emision'] = {'$gte': fecha_desde}
    if fecha_hasta:
        if 'fecha_emision' in query:
            query['fecha_emision']['$lte'] = fecha_hasta
        else:
            query['fecha_emision'] = {'$lte': fecha_hasta}
    
    cfdis = await db.cfdis.find(query, {'_id': 0}).sort('fecha_emision', 1).to_list(10000)
    
    # Get categories
    categories = {c['id']: c for c in await db.categories.find({'company_id': company_id}, {'_id': 0}).to_list(1000)}
    subcategories = {s['id']: s for s in await db.subcategories.find({'company_id': company_id}, {'_id': 0}).to_list(1000)}
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # DIOT Header
    writer.writerow([
        'Tipo Tercero', 'Tipo Operación', 'RFC', 'Nombre/Razón Social',
        'País', 'Nacionalidad', 'Valor Actos o Actividades Pagados',
        'Valor Actos o Actividades 0%', 'Valor Actos o Actividades Exentos',
        'Valor Actos o Actividades Tasa 16%', 'IVA Retenido', 'IVA Acreditable',
        'Fecha Emisión', 'UUID', 'Categoría', 'Subcategoría', 'Estado Conciliación'
    ])
    
    for cfdi in cfdis:
        tipo_tercero = '04' if cfdi.get('tipo_cfdi') == 'egreso' else '05'
        tipo_operacion = '03'
        categoria = categories.get(cfdi.get('category_id'), {}).get('nombre', '')
        subcategoria = subcategories.get(cfdi.get('subcategory_id'), {}).get('nombre', '')
        
        writer.writerow([
            tipo_tercero,
            tipo_operacion,
            cfdi.get('emisor_rfc', ''),
            cfdi.get('emisor_nombre', ''),
            'MX',
            'Nacional',
            cfdi.get('total', 0),
            0,
            0,
            cfdi.get('subtotal', 0),
            0,
            cfdi.get('impuestos', 0),
            cfdi.get('fecha_emision', '')[:10] if cfdi.get('fecha_emision') else '',
            cfdi.get('uuid', ''),
            categoria,
            subcategoria,
            cfdi.get('estado_conciliacion', 'pendiente')
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=DIOT_export.csv"}
    )

# ===== PLANTILLA ESTADO DE CUENTA - MOVED TO routes/bank_transactions.py =====

@api_router.post("/bank-transactions/import")
async def import_bank_statement(request: Request, file: UploadFile = File(...), bank_account_id: str = Form(...), current_user: Dict = Depends(get_current_user)):
    """Import bank statement from Excel"""
    import pandas as pd
    import io
    
    company_id = await get_active_company_id(request, current_user)
    
    # Verify bank account
    account = await db.bank_accounts.find_one({'id': bank_account_id, 'company_id': company_id}, {'_id': 0})
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos Excel (.xlsx, .xls)")
    
    content = await file.read()
    df = pd.read_excel(io.BytesIO(content))
    
    # Only require minimal columns - saldo is OPTIONAL
    required_cols = ['fecha_movimiento', 'descripcion', 'monto']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Columnas faltantes: {', '.join(missing)}")
    
    imported = 0
    errors = []
    
    for idx, row in df.iterrows():
        try:
            # Parse fecha_movimiento - handle different formats
            fecha_mov = row['fecha_movimiento']
            if pd.isna(fecha_mov):
                errors.append(f"Fila {idx + 2}: fecha_movimiento vacía")
                continue
            
            # Convert to string and handle datetime objects
            if hasattr(fecha_mov, 'strftime'):
                fecha_str = fecha_mov.strftime('%Y-%m-%d')
            else:
                fecha_str = str(fecha_mov)[:19]
            
            # Parse monto
            monto = row['monto']
            if pd.isna(monto):
                errors.append(f"Fila {idx + 2}: monto vacío")
                continue
            monto = float(monto)
            
            # Determine tipo_movimiento from monto sign or column
            tipo_mov = 'credito'
            if 'tipo_movimiento' in df.columns and not pd.isna(row.get('tipo_movimiento')):
                tipo_mov = str(row['tipo_movimiento']).lower().strip()
                if tipo_mov in ['debito', 'débito', 'cargo', 'retiro', 'egreso']:
                    tipo_mov = 'debito'
                else:
                    tipo_mov = 'credito'
            elif monto < 0:
                tipo_mov = 'debito'
                monto = abs(monto)
            
            # Get description
            descripcion = row['descripcion']
            if pd.isna(descripcion):
                descripcion = 'Movimiento bancario'
            descripcion = str(descripcion)[:500]
            
            # Get optional saldo
            saldo = 0
            if 'saldo' in df.columns and not pd.isna(row.get('saldo')):
                try:
                    saldo = float(row['saldo'])
                except:
                    saldo = 0
            
            # Get optional fecha_valor
            fecha_valor = fecha_str
            if 'fecha_valor' in df.columns and not pd.isna(row.get('fecha_valor')):
                fv = row['fecha_valor']
                if hasattr(fv, 'strftime'):
                    fecha_valor = fv.strftime('%Y-%m-%d')
                else:
                    fecha_valor = str(fv)[:19]
            
            txn = {
                'id': str(uuid.uuid4()),
                'company_id': company_id,
                'bank_account_id': bank_account_id,
                'fecha_movimiento': fecha_str,
                'fecha_valor': fecha_valor,
                'descripcion': descripcion,
                'referencia': str(row.get('referencia', '')) if not pd.isna(row.get('referencia')) else '',
                'monto': monto,
                'tipo_movimiento': tipo_mov,
                'saldo': saldo,
                'conciliado': False,
                'estado_conciliacion': 'pendiente',
                'categoria': str(row.get('categoria', '')) if not pd.isna(row.get('categoria')) else '',
                'notas': str(row.get('notas', '')) if not pd.isna(row.get('notas')) else '',
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            await db.bank_transactions.insert_one(txn)
            imported += 1
        except Exception as e:
            errors.append(f"Fila {idx + 2}: {str(e)}")
    
    return {
        'status': 'success',
        'importados': imported,
        'errores': len(errors),
        'detalle_errores': errors[:10]
    }


def parse_bank_statement_pdf(pdf_content: bytes, bank_name: str = "auto") -> List[Dict]:
    """
    Parse bank statement PDF and extract transactions.
    Supports: Banorte, BBVA, Santander, HSBC, and generic formats.
    """
    import pdfplumber
    import re
    from datetime import datetime
    
    transactions = []
    
    try:
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            full_text = ""
            all_tables = []
            
            for page in pdf.pages:
                text = page.extract_text() or ""
                full_text += text + "\n"
                
                # Extract tables from each page
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)
            
            # Try to detect bank from content
            detected_bank = bank_name
            if bank_name == "auto":
                text_lower = full_text.lower()
                if "banbajio" in text_lower or "bajio" in text_lower or "banco del bajio" in text_lower:
                    detected_bank = "banbajio"
                elif "banorte" in text_lower:
                    detected_bank = "banorte"
                elif "bbva" in text_lower or "bancomer" in text_lower:
                    detected_bank = "bbva"
                elif "santander" in text_lower:
                    detected_bank = "santander"
                elif "hsbc" in text_lower:
                    detected_bank = "hsbc"
                elif "scotiabank" in text_lower:
                    detected_bank = "scotiabank"
                elif "banamex" in text_lower or "citibanamex" in text_lower:
                    detected_bank = "banamex"
                else:
                    detected_bank = "generic"
            
            # Try extracting saldo inicial from text
            saldo_inicial = None
            saldo_patterns = [
                r'SALDO\s+INICIAL[:\s]+\$?\s*([\d,]+\.?\d*)',
                r'SALDO\s+ANTERIOR[:\s]+\$?\s*([\d,]+\.?\d*)',
                r'SALDO\s+AL\s+\d+[:\s]+\$?\s*([\d,]+\.?\d*)',
            ]
            for pattern in saldo_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    saldo_str = match.group(1).replace(',', '')
                    saldo_inicial = float(saldo_str)
                    break
            
            # Parse based on detected bank
            if detected_bank == "banbajio":
                transactions = parse_banbajio_pdf(full_text, all_tables, pdf, saldo_inicial)
            elif detected_bank in ["banorte", "bbva", "santander", "hsbc", "banamex", "scotiabank"]:
                transactions = parse_mexican_bank_pdf(full_text, all_tables, pdf, saldo_inicial)
            else:
                transactions = parse_mexican_bank_pdf(full_text, all_tables, pdf, saldo_inicial)
            
    except Exception as e:
        logging.error(f"Error parsing PDF: {str(e)}")
        raise
    
    return transactions


def parse_banbajio_pdf(text: str, tables: List, pdf, saldo_inicial: float = None) -> List[Dict]:
    """
    Parser específico para estados de cuenta de BanBajío.
    Formato: DD MMM | Descripción | Referencia | Depósitos | Retiros | Saldo
    """
    import re
    from datetime import datetime
    
    transactions = []
    current_year = datetime.now().year
    
    # Try to extract year from PDF text (look for patterns like "DICIEMBRE 2025" or "DIC 2025")
    year_match = re.search(r'(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)[A-Z]*\s*(\d{4})', text.upper())
    if year_match:
        current_year = int(year_match.group(2))
    else:
        # Also try "PERIODO: ... 2025" pattern
        period_match = re.search(r'PERIODO[:\s]+.*?(\d{4})', text.upper())
        if period_match:
            current_year = int(period_match.group(1))
    
    months_es = {
        'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'
    }
    
    # Skip keywords for summary/header rows
    skip_keywords = [
        'SALDO INICIAL', 'SALDO ANTERIOR', 'SALDO FINAL', 'SALDO AL',
        'TOTAL', 'RESUMEN', 'MOVIMIENTOS', 'DESCRIPCION', 'FECHA',
        'REFERENCIA', 'ABONOS', 'CARGOS', 'DEPOSITOS', 'RETIROS',
        'PROMEDIO', 'PERIODO', 'ESTADO DE CUENTA', 'CLIENTE', 'RFC'
    ]
    
    def clean_description(desc: str) -> str:
        """Clean up description by removing extra spaces between characters"""
        # Remove pattern like "C O M I S I O N" -> "COMISION"
        # Also handle "CO MISION" -> "COMISION"
        
        # First, try to detect and fix space-separated text
        # Pattern: uppercase letters separated by single spaces at the start
        if re.match(r'^[A-Z][A-Z\s]{3,}', desc):
            # Count ratio of spaces to letters
            letters = len(re.findall(r'[A-Za-z]', desc[:20]))
            spaces = len(re.findall(r'\s', desc[:20]))
            
            if spaces > 0 and letters / (spaces + letters) < 0.6:
                # Lots of spaces - likely space-separated
                cleaned = re.sub(r'(\w)\s+(?=\w)', r'\1', desc)
                return cleaned
        
        # Also fix common patterns like "CO MISION" -> "COMISION"
        common_fixes = [
            (r'CO\s+MISION', 'COMISION'),
            (r'IVA\s+CO', 'IVA CO'),
            (r'EN\s+VÍO', 'ENVÍO'),
            (r'EN\s+VIO', 'ENVIO'),
            (r'DE\s+POSITO', 'DEPOSITO'),
            (r'PA\s+GO', 'PAGO'),
            (r'RE\s+TIRO', 'RETIRO'),
            (r'TRANS\s+FERENCIA', 'TRANSFERENCIA'),
        ]
        for pattern, replacement in common_fixes:
            desc = re.sub(pattern, replacement, desc, flags=re.IGNORECASE)
        
        return desc
    
    def extract_amount(val: str) -> float:
        """Extract numeric amount from string"""
        if not val:
            return 0
        val = re.sub(r'[^\d.,\-]', '', str(val))
        val = val.replace(',', '')
        try:
            return float(val)
        except:
            return 0
    
    # Process line by line - BanBajío format
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue
        
        line_upper = line.upper()
        
        # Skip header/summary rows
        if any(skip in line_upper for skip in skip_keywords):
            continue
        
        # BanBajío format: "DD MMM DESCRIPCION ... $MONTO $SALDO" or with reference
        # Pattern 1: DD MMM at start (e.g., "1 DIC", "15 ENE", "31 DIC")
        date_match = re.match(r'^(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s+(.+)', line, re.IGNORECASE)
        
        if not date_match:
            continue
        
        day = int(date_match.group(1))
        month = date_match.group(2).upper()
        rest_of_line = date_match.group(3)
        
        # Validate date
        if day < 1 or day > 31 or month not in months_es:
            continue
        
        fecha = f"{current_year}-{months_es[month]}-{str(day).zfill(2)}"
        
        # Extract all amounts from the line (format: numbers with decimals like 1,234.56 or 1234.56)
        amounts = re.findall(r'([\d,]+\.\d{2})', rest_of_line)
        amounts = [float(a.replace(',', '')) for a in amounts]
        
        if len(amounts) < 1:
            continue
        
        # Extract description - everything before the first amount
        first_amount_pos = rest_of_line.find(str(int(amounts[0])).replace(',', '').split('.')[0] if amounts else '')
        if first_amount_pos == -1:
            first_amount_match = re.search(r'[\d,]+\.\d{2}', rest_of_line)
            first_amount_pos = first_amount_match.start() if first_amount_match else len(rest_of_line)
        
        descripcion = rest_of_line[:first_amount_pos].strip()
        
        # Clean description - remove trailing reference numbers
        descripcion = re.sub(r'\s+\d{5,}$', '', descripcion)  # Remove trailing long numbers
        descripcion = descripcion.strip()
        
        # Determine deposit vs withdrawal based on amounts
        deposito = 0
        retiro = 0
        saldo = 0
        
        # BanBajío typically has: DEPOSITO | RETIRO | SALDO (3 amounts)
        # or just: MONTO | SALDO (2 amounts)
        if len(amounts) >= 3:
            # Last amount is saldo, one of the previous two is the movement
            saldo = amounts[-1]
            
            # Check which column has the movement based on position in text
            # Find positions of amounts in text
            amount_positions = []
            for amt in amounts[:-1]:  # Exclude saldo
                amt_str = f"{amt:,.2f}".replace(',', '')
                pos = rest_of_line.rfind(amt_str[:6])  # Use first 6 chars to find
                amount_positions.append((amt, pos))
            
            # Sort by position
            amount_positions.sort(key=lambda x: x[1])
            
            if len(amount_positions) >= 2:
                # First non-zero is the movement
                for amt, pos in amount_positions:
                    if amt > 0:
                        # Determine if deposit or withdrawal by description
                        desc_upper = descripcion.upper()
                        if any(kw in desc_upper for kw in ['DEPOSITO', 'ABONO', 'DEVOLUCION', 'SPEI:', 'TRASPASO DE RECURSOS A']):
                            if 'ENVÍO SPEI' in desc_upper or 'ENVIO SPEI' in desc_upper:
                                retiro = amt  # Envío SPEI es retiro
                            else:
                                deposito = amt
                        elif any(kw in desc_upper for kw in ['COMISION', 'IVA ', 'PAGO ', 'ENVÍO', 'ENVIO', 'RETIRO', 'COMPRA', 'CARGO']):
                            retiro = amt
                        else:
                            # If description has "POR OPERACION CAMBIOS" it's usually a deposit
                            if 'OPERACION CAMBIOS' in desc_upper:
                                deposito = amt
                            else:
                                retiro = amt
                        break
        elif len(amounts) == 2:
            # MONTO | SALDO
            monto = amounts[0]
            saldo = amounts[1]
            
            # Determine type by description
            desc_upper = descripcion.upper()
            deposit_keywords = ['DEPOSITO', 'DEPÓSITO', 'ABONO', 'DEVOLUCION', 'DEVOLUCIÓN']
            withdrawal_keywords = ['COMISION', 'COMISIÓN', 'IVA ', 'PAGO ', 'ENVÍO', 'ENVIO', 'RETIRO', 
                                   'COMPRA', 'CARGO', 'TRASPASO DE RECURSOS A', 'DOMICILIACION']
            
            # SPEI transactions
            if 'SPEI' in desc_upper:
                if 'ENVÍO SPEI' in desc_upper or 'ENVIO SPEI' in desc_upper:
                    retiro = monto  # Envío = outgoing
                elif 'DEPÓSITO SPEI' in desc_upper or 'DEPOSITO SPEI' in desc_upper:
                    deposito = monto
                elif 'DEVOLUCIÓN' in desc_upper or 'DEVOLUCION' in desc_upper:
                    deposito = monto
                else:
                    retiro = monto  # Default SPEI to withdrawal
            elif any(kw in desc_upper for kw in deposit_keywords):
                deposito = monto
            elif any(kw in desc_upper for kw in withdrawal_keywords):
                retiro = monto
            elif 'OPERACION CAMBIOS' in desc_upper:
                deposito = monto  # Currency exchange deposit
            else:
                retiro = monto  # Default to withdrawal for unclassified
        elif len(amounts) == 1:
            # Just one amount - try to determine from description
            monto = amounts[0]
            desc_upper = descripcion.upper()
            
            if any(kw in desc_upper for kw in ['DEPOSITO', 'DEPÓSITO', 'ABONO']):
                deposito = monto
            else:
                retiro = monto
            saldo = 0
        
        # Only add if we have a movement
        if deposito > 0 or retiro > 0:
            # Clean description
            descripcion_clean = clean_description(descripcion)
            transactions.append({
                'fecha': fecha,
                'descripcion': descripcion_clean[:300] or 'Movimiento bancario',
                'deposito': deposito,
                'retiro': retiro,
                'saldo': saldo,
                'referencia': ''
            })
    
    return transactions


def parse_mexican_bank_pdf(text: str, tables: List, pdf, saldo_inicial: float = None) -> List[Dict]:
    """
    Universal parser for Mexican bank PDFs.
    Enhanced to better handle BanBajío and other Mexican bank formats.
    """
    import re
    from datetime import datetime
    
    transactions = []
    current_year = datetime.now().year
    
    months_es = {
        'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12',
        'ENERO': '01', 'FEBRERO': '02', 'MARZO': '03', 'ABRIL': '04',
        'MAYO': '05', 'JUNIO': '06', 'JULIO': '07', 'AGOSTO': '08',
        'SEPTIEMBRE': '09', 'OCTUBRE': '10', 'NOVIEMBRE': '11', 'DICIEMBRE': '12'
    }
    
    def is_valid_date(day: int, month: str) -> bool:
        """Check if day and month are valid"""
        if month.upper() not in months_es:
            return False
        if day < 1 or day > 31:
            return False
        return True
    
    def parse_date(date_str: str) -> str:
        """Parse date from various formats: DD MMM, DD/MM/YYYY, YYYY-MM-DD"""
        date_str = date_str.strip()
        
        # Format: DD MMM (e.g., "1 DIC", "15 ENE")
        match = re.match(r'(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)', date_str.upper())
        if match:
            day = int(match.group(1))
            month = months_es.get(match.group(2), '01')
            return f"{current_year}-{month}-{str(day).zfill(2)}"
        
        # Format: DD/MM/YYYY or DD-MM-YYYY
        match = re.match(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', date_str)
        if match:
            day = match.group(1).zfill(2)
            month = match.group(2).zfill(2)
            year = match.group(3)
            if len(year) == 2:
                year = f"20{year}"
            return f"{year}-{month}-{day}"
        
        # Format: YYYY-MM-DD
        match = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_str)
        if match:
            return date_str
        
        return None
    
    def extract_amount(val: str) -> float:
        """Extract numeric amount from string, handling various formats"""
        if not val:
            return 0
        # Remove currency symbols and spaces
        val = re.sub(r'[^\d.,\-]', '', str(val))
        # Handle negative values
        is_negative = '-' in val
        val = val.replace('-', '')
        # Handle comma as thousands separator
        if ',' in val and '.' in val:
            val = val.replace(',', '')
        elif ',' in val:
            # Could be decimal separator or thousands
            parts = val.split(',')
            if len(parts[-1]) == 2:  # Likely decimal
                val = val.replace(',', '.')
            else:  # Thousands separator
                val = val.replace(',', '')
        try:
            amount = float(val)
            return -amount if is_negative else amount
        except:
            return 0
    
    # Words to skip - these are summary/header lines
    skip_keywords = [
        'SALDO INICIAL', 'SALDO ANTERIOR', 'SALDO FINAL', 'SALDO AL',
        'TOTAL', 'RESUMEN', 'DEPOSITOS', 'RETIROS', 'CARGOS',
        'FECHA', 'NO. REF', 'DESCRIPCION', 'OPERACION', 'CONCEPTO',
        '(+)', '(-)', 'PROMEDIO', 'MENSUAL', 'MINIMO', 'PERIODO',
        'ESTADO DE CUENTA', 'CUENTA', 'CLIENTE', 'RFC', 'DOMICILIO'
    ]
    
    # First try to extract from tables (more structured)
    if tables:
        for table in tables:
            if not table:
                continue
            for row in table:
                if not row or len(row) < 3:
                    continue
                
                # Convert all cells to strings
                row_str = [str(cell).strip() if cell else '' for cell in row]
                row_joined = ' '.join(row_str).upper()
                
                # Skip header/summary rows
                if any(skip in row_joined for skip in skip_keywords):
                    continue
                
                # Try to find date in first few cells
                fecha = None
                for i, cell in enumerate(row_str[:3]):
                    fecha = parse_date(cell)
                    if fecha:
                        break
                
                if not fecha:
                    continue
                
                # Extract description (usually longest non-numeric field)
                descripcion = ""
                amounts = []
                
                for cell in row_str:
                    # Check if it's a numeric value
                    cell_clean = re.sub(r'[^\d.,\-]', '', cell)
                    if cell_clean and re.match(r'^-?[\d,]+\.?\d*$', cell_clean.replace(',', '')):
                        amt = extract_amount(cell)
                        if amt != 0:
                            amounts.append(amt)
                    elif len(cell) > len(descripcion) and not re.match(r'^[\d\$\.,\s/-]+$', cell):
                        descripcion = cell
                
                if not amounts or not descripcion:
                    continue
                
                # Determine deposit vs withdrawal
                deposito = 0
                retiro = 0
                saldo = abs(amounts[-1]) if len(amounts) > 1 else 0
                
                if len(amounts) >= 3:
                    # Format: ... | DEPOSITO | RETIRO | SALDO
                    dep_val = amounts[-3]
                    ret_val = amounts[-2]
                    if dep_val > 0 and ret_val == 0:
                        deposito = dep_val
                    elif ret_val > 0 and dep_val == 0:
                        retiro = ret_val
                    elif dep_val > 0:
                        deposito = dep_val
                elif len(amounts) >= 2:
                    monto = amounts[-2]
                    # Use description to guess type
                    desc_upper = descripcion.upper()
                    deposit_keywords = ['DEPOSITO', 'ABONO', 'INGRESO', 'TRANSFERENCIA RECIBIDA', 'PAGO RECIBIDO', 'CREDITO']
                    withdrawal_keywords = ['RETIRO', 'CARGO', 'PAGO', 'COMISION', 'IVA', 'TRANSFERENCIA ENVIADA', 'DEBITO']
                    
                    if any(kw in desc_upper for kw in deposit_keywords):
                        deposito = abs(monto)
                    elif any(kw in desc_upper for kw in withdrawal_keywords):
                        retiro = abs(monto)
                    elif monto < 0:
                        retiro = abs(monto)
                    else:
                        deposito = monto
                
                if deposito > 0 or retiro > 0:
                    transactions.append({
                        'fecha': fecha,
                        'descripcion': descripcion[:200].strip() or 'Movimiento bancario',
                        'deposito': deposito,
                        'retiro': retiro,
                        'saldo': saldo,
                        'referencia': ''
                    })
    
    # If no transactions from tables, try line-by-line parsing
    if not transactions:
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 10:
                continue
            
            line_upper = line.upper()
            
            # Skip summary and header lines
            if any(skip in line_upper for skip in skip_keywords):
                continue
            
            # Try multiple date patterns
            fecha = None
            rest_of_line = line
            
            # Pattern 1: DD MMM at start
            match = re.match(r'^(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s+(.+)', line, re.IGNORECASE)
            if match:
                day = int(match.group(1))
                month = match.group(2).upper()
                if is_valid_date(day, month):
                    fecha = f"{current_year}-{months_es[month]}-{str(day).zfill(2)}"
                    rest_of_line = match.group(3)
            
            # Pattern 2: DD/MM/YYYY at start
            if not fecha:
                match = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\s+(.+)', line)
                if match:
                    fecha = parse_date(f"{match.group(1)}/{match.group(2)}/{match.group(3)}")
                    rest_of_line = match.group(4)
            
            if not fecha:
                continue
            
            # Extract amounts
            amounts = re.findall(r'([\d,]+\.\d{2})', rest_of_line)
            amounts = [float(a.replace(',', '')) for a in amounts]
            
            if len(amounts) < 1:
                continue
            
            # Get description
            first_amount_match = re.search(r'[\d,]+\.\d{2}', rest_of_line)
            if first_amount_match:
                descripcion = rest_of_line[:first_amount_match.start()].strip()
            else:
                descripcion = rest_of_line[:50]
            
            # Clean description
            descripcion = re.sub(r'^\d+\s+', '', descripcion).strip()
            
            # Determine deposit vs withdrawal
            deposito = 0
            retiro = 0
            saldo = amounts[-1] if len(amounts) > 1 else 0
            
            if len(amounts) >= 3:
                dep_val = amounts[-3]
                ret_val = amounts[-2]
                if dep_val > 0 and (ret_val == 0 or ret_val == saldo):
                    deposito = dep_val
                elif ret_val > 0 and (dep_val == 0 or dep_val == saldo):
                    retiro = ret_val
            elif len(amounts) >= 2:
                monto = amounts[0]
                desc_upper = descripcion.upper()
                if any(kw in desc_upper for kw in ['DEPOSITO', 'ABONO', 'INGRESO', 'RECIBID']):
                    deposito = monto
                else:
                    retiro = monto
            elif len(amounts) == 1:
                # Single amount - try to determine from description
                monto = amounts[0]
                desc_upper = descripcion.upper()
                if any(kw in desc_upper for kw in ['DEPOSITO', 'ABONO', 'INGRESO', 'RECIBID', 'TRANSFERENCIA']):
                    deposito = monto
                else:
                    retiro = monto
                saldo = 0
            
            if deposito > 0 or retiro > 0:
                transactions.append({
                    'fecha': fecha,
                    'descripcion': descripcion[:200] or 'Movimiento bancario',
                    'deposito': deposito,
                    'retiro': retiro,
                    'saldo': saldo,
                    'referencia': ''
                })
    
    return transactions


def parse_banorte_pdf(text: str, tables: List, saldo_inicial: float = None) -> List[Dict]:
    """
    Parse Banorte bank statement format.
    Column order: FECHA | NO. REF. | DESCRIPCION | DEPOSITOS | RETIROS | SALDO
    
    Key insight: Determine deposit vs withdrawal based on COLUMN POSITION,
    not by description keywords. If amount is in DEPOSITOS column -> deposit.
    If amount is in RETIROS column -> withdrawal.
    """
    import re
    from datetime import datetime
    
    transactions = []
    current_year = datetime.now().year
    
    months_es = {
        'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'
    }
    
    def parse_amount(cell: str) -> float:
        """Parse a monetary amount from a cell"""
        if not cell or not cell.strip():
            return 0
        # Remove $ and spaces, replace comma thousands separator
        clean = re.sub(r'[\$\s]', '', str(cell))
        clean = clean.replace(',', '')
        try:
            val = float(clean) if clean else 0
            return val if val > 0 else 0
        except:
            return 0
    
    # Process tables - looking for transaction tables with DEPOSITOS/RETIROS columns
    for table in tables:
        if not table or len(table) < 2:
            continue
        
        # Find header row and identify column positions
        header_row = None
        header_idx = 0
        deposito_col = None
        retiro_col = None
        saldo_col = None
        
        # Search for header in first few rows
        for idx, row in enumerate(table[:3]):
            if not row:
                continue
            row_text = ' '.join([str(cell or '').upper() for cell in row])
            
            # Check if this row contains column headers
            if 'DEPOSITO' in row_text or 'RETIRO' in row_text:
                header_row = row
                header_idx = idx
                
                # Find exact column indices
                for col_idx, cell in enumerate(row):
                    cell_upper = str(cell or '').upper().strip()
                    if 'DEPOSITO' in cell_upper:
                        deposito_col = col_idx
                    elif 'RETIRO' in cell_upper or 'CARGO' in cell_upper:
                        retiro_col = col_idx
                    elif 'SALDO' in cell_upper:
                        saldo_col = col_idx
                break
        
        # If we found column positions, process data rows
        if deposito_col is not None or retiro_col is not None:
            for row in table[header_idx + 1:]:
                if not row or not any(row):
                    continue
                
                try:
                    row_cleaned = [str(cell or '').strip() for cell in row]
                    row_text = ' '.join(row_cleaned).upper()
                    
                    # Skip header-like rows
                    if 'SALDO INICIAL' in row_text or 'SALDO ANTERIOR' in row_text:
                        continue
                    if 'FECHA' in row_text and 'DEPOSITO' in row_text:
                        continue
                    
                    # Extract date from any cell
                    fecha = None
                    for cell in row_cleaned:
                        # Pattern: DD MMM (e.g., "01 DIC", "15 ENE", "1DIC")
                        date_match = re.search(r'(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)', cell.upper())
                        if date_match:
                            day = date_match.group(1).zfill(2)
                            month = months_es.get(date_match.group(2), '01')
                            fecha = f"{current_year}-{month}-{day}"
                            break
                        # Pattern: DD/MM/YYYY
                        date_match2 = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', cell)
                        if date_match2:
                            day = date_match2.group(1).zfill(2)
                            month = date_match2.group(2).zfill(2)
                            year = date_match2.group(3)
                            if len(year) == 2:
                                year = f"20{year}"
                            fecha = f"{year}-{month}-{day}"
                            break
                    
                    if not fecha:
                        continue
                    
                    # Extract amounts from specific columns
                    deposito = 0
                    retiro = 0
                    saldo = 0
                    
                    if deposito_col is not None and deposito_col < len(row_cleaned):
                        deposito = parse_amount(row_cleaned[deposito_col])
                    
                    if retiro_col is not None and retiro_col < len(row_cleaned):
                        retiro = parse_amount(row_cleaned[retiro_col])
                    
                    if saldo_col is not None and saldo_col < len(row_cleaned):
                        saldo = parse_amount(row_cleaned[saldo_col])
                    
                    # Get description - find the longest text that's not a number
                    descripcion = ""
                    for idx, cell in enumerate(row_cleaned):
                        # Skip amount columns
                        if idx in [deposito_col, retiro_col, saldo_col]:
                            continue
                        if cell and len(cell) > len(descripcion) and not re.match(r'^[\d\$\.,\s/-]+$', cell):
                            descripcion = cell
                    
                    # Only add if we have an actual movement
                    if deposito > 0 or retiro > 0:
                        transactions.append({
                            'fecha': fecha,
                            'descripcion': descripcion or 'Movimiento bancario',
                            'deposito': deposito,
                            'retiro': retiro,
                            'saldo': saldo,
                            'referencia': ''
                        })
                        
                except Exception:
                    continue
        
        else:
            # No clear column headers - try position-based parsing
            # In Banorte PDFs, columns are typically: FECHA | REF | DESC | DEPOSITOS | RETIROS | SALDO
            # The last 3 numeric columns are amounts
            for row in table[1:]:
                if not row or not any(row):
                    continue
                
                try:
                    row_cleaned = [str(cell or '').strip() for cell in row]
                    row_text = ' '.join(row_cleaned).upper()
                    
                    # Skip headers and saldo inicial
                    if any(kw in row_text for kw in ['SALDO INICIAL', 'SALDO ANTERIOR', 'FECHA', 'DEPOSITO']):
                        continue
                    
                    # Extract date
                    fecha = None
                    for cell in row_cleaned:
                        date_match = re.search(r'(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)', cell.upper())
                        if date_match:
                            day = date_match.group(1).zfill(2)
                            month = months_es.get(date_match.group(2), '01')
                            fecha = f"{current_year}-{month}-{day}"
                            break
                    
                    if not fecha:
                        continue
                    
                    # Find all amount cells and their positions
                    amount_cells = []
                    for idx, cell in enumerate(row_cleaned):
                        val = parse_amount(cell)
                        if val > 0:
                            amount_cells.append((idx, val))
                    
                    if len(amount_cells) < 1:
                        continue
                    
                    # Get description
                    descripcion = ""
                    for cell in row_cleaned:
                        if cell and len(cell) > len(descripcion) and not re.match(r'^[\d\$\.,\s/-]+$', cell):
                            descripcion = cell
                    
                    # With 3 amounts: DEPOSITO, RETIRO, SALDO
                    # With 2 amounts: either (DEPOSITO, SALDO) or (RETIRO, SALDO)
                    # With 1 amount: just SALDO (skip) or need keyword detection
                    
                    deposito = 0
                    retiro = 0
                    saldo = 0
                    
                    if len(amount_cells) >= 3:
                        # Last 3 are: DEPOSITO, RETIRO, SALDO
                        deposito = amount_cells[-3][1]
                        retiro = amount_cells[-2][1]
                        saldo = amount_cells[-1][1]
                    elif len(amount_cells) == 2:
                        # Could be (DEP, SALDO) or (RET, SALDO)
                        # Check column position - if first amount is more to the left, likely DEPOSITO column
                        first_col = amount_cells[0][0]
                        num_cols = len(row_cleaned)
                        
                        # If first amount is in first half, likely deposit
                        # If in second half (closer to SALDO), likely retiro
                        if first_col < num_cols * 0.6:
                            deposito = amount_cells[0][1]
                        else:
                            retiro = amount_cells[0][1]
                        saldo = amount_cells[-1][1]
                    
                    if deposito > 0 or retiro > 0:
                        transactions.append({
                            'fecha': fecha,
                            'descripcion': descripcion or 'Movimiento bancario',
                            'deposito': deposito,
                            'retiro': retiro,
                            'saldo': saldo,
                            'referencia': ''
                        })
                        
                except Exception:
                    continue
    
    # If no transactions from tables, try line-by-line text parsing
    if not transactions:
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if any(kw in line.upper() for kw in ['SALDO INICIAL', 'SALDO ANTERIOR', 'FECHA']):
                continue
            
            # Find date at start
            date_match = re.match(r'^(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\b', line.upper())
            if not date_match:
                continue
            
            day = date_match.group(1).zfill(2)
            month = months_es.get(date_match.group(2), '01')
            fecha = f"{current_year}-{month}-{day}"
            
            rest = line[date_match.end():].strip()
            
            # Find all amounts
            amounts = re.findall(r'\$?\s*([\d,]+\.\d{2})', rest)
            amounts = [float(a.replace(',', '')) for a in amounts if a]
            
            if len(amounts) < 2:
                continue
            
            # Description is text before first amount
            first_amt = re.search(r'\$?\s*[\d,]+\.\d{2}', rest)
            descripcion = rest[:first_amt.start()].strip() if first_amt else rest[:50]
            
            # Parse based on number of amounts
            deposito = 0
            retiro = 0
            saldo = amounts[-1]
            
            if len(amounts) >= 3:
                deposito = amounts[-3]
                retiro = amounts[-2]
            elif len(amounts) == 2:
                # Single movement amount - use keyword detection as fallback
                monto = amounts[0]
                normalized_desc = normalize_text_for_keywords(descripcion)
                is_dep = is_deposit_transaction(normalized_desc)
                if is_dep is True:
                    deposito = monto
                else:
                    retiro = monto
            
            if deposito > 0 or retiro > 0:
                transactions.append({
                    'fecha': fecha,
                    'descripcion': descripcion or 'Movimiento bancario',
                    'deposito': deposito,
                    'retiro': retiro,
                    'saldo': saldo,
                    'referencia': ''
                })
    
    return transactions


def parse_bbva_pdf(text: str, tables: List, saldo_inicial: float = None) -> List[Dict]:
    """Parse BBVA bank statement format"""
    return parse_generic_pdf(text, tables, saldo_inicial)


# Keywords for deposit/withdrawal detection (shared across parsers)
DEPOSIT_KEYWORDS = [
    'DEPOSITO', 'ABONO', 'TRANSFERENCIA RECIBIDA', 'SPEI REC', 
    'PAGO RECIBIDO', 'DEP ', 'COBRANZA', 'INGRESO', 'CREDITO',
    'RECEPCION', 'BONIFICACION', 'DEVOLUCION', 'REEMBOLSO',
    'TRANSFER IN', 'CREDIT', 'NOMINA', 'INTERES GANADO'
]

WITHDRAWAL_KEYWORDS = [
    'RETIRO', 'CARGO', 'COMISION', 'IVA ', 'PAGO ', 'TRANSFERENCIA ENV',
    'SPEI ENV', 'SERVICIO', 'ENVIO', 'DISPOSICION', 'CHEQUE',
    'DOMICILIACION', 'ANUALIDAD', 'MANEJO', 'TRASPASO', 'COMPRA',
    'TRANSFER OUT', 'DEBIT', 'FEE', 'PAYMENT'
]


def normalize_text_for_keywords(text: str) -> str:
    """
    Normalize text by removing single-space separations between letters.
    This handles PDFs that have 'D E P O S I T O' instead of 'DEPOSITO'.
    """
    import re
    
    if not text:
        return ""
    
    # Pattern to match single letters separated by single spaces
    # e.g., "D E P O S I T O" -> "DEPOSITO"
    # But preserve multi-letter words: "PAGO DE SERVICIO" stays as is
    
    result = text.upper()
    
    # Replace patterns like "A B C" (single letters with spaces) with "ABC"
    # This regex finds sequences of single letters separated by single spaces
    pattern = r'\b([A-Z])\s+(?=[A-Z]\b)'
    
    # Keep replacing until no more changes
    prev = ""
    while prev != result:
        prev = result
        result = re.sub(pattern, r'\1', result)
    
    return result


def is_deposit_transaction(desc: str) -> bool:
    """Determine if transaction is a deposit based on description keywords"""
    # Normalize text to handle spaced-out letters like "D E POSITO"
    normalized = normalize_text_for_keywords(desc)
    
    # Check for deposit keywords
    for kw in DEPOSIT_KEYWORDS:
        if kw in normalized:
            return True
    
    # Check for withdrawal keywords
    for kw in WITHDRAWAL_KEYWORDS:
        if kw in normalized:
            return False
    
    return None  # Unknown - will default to withdrawal


def parse_generic_pdf(text: str, tables: List, saldo_inicial: float = None) -> List[Dict]:
    """
    Parse generic bank statement with common patterns.
    Uses column position detection first, then falls back to keyword detection.
    """
    import re
    from datetime import datetime
    
    transactions = []
    current_year = datetime.now().year
    
    def parse_amount(cell: str) -> float:
        """Parse a monetary amount from a cell"""
        if not cell or not cell.strip():
            return 0
        clean = re.sub(r'[\$\s]', '', str(cell))
        clean = clean.replace(',', '')
        try:
            val = float(clean) if clean else 0
            return val if val > 0 else 0
        except:
            return 0
    
    # Common date patterns
    date_patterns = [
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',  # DD/MM/YYYY or DD-MM-YYYY
        r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',    # YYYY-MM-DD
    ]
    
    months_es = {
        'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'
    }
    
    # Try table extraction first
    for table in tables:
        if not table or len(table) < 2:
            continue
        
        # Look for header row with column names
        deposito_col = None
        retiro_col = None
        cargo_col = None
        abono_col = None
        saldo_col = None
        header_idx = 0
        
        for idx, row in enumerate(table[:3]):
            if not row:
                continue
            row_text = ' '.join([str(cell or '').upper() for cell in row])
            
            if any(kw in row_text for kw in ['DEPOSITO', 'RETIRO', 'CARGO', 'ABONO', 'SALDO']):
                header_idx = idx
                for col_idx, cell in enumerate(row):
                    cell_upper = str(cell or '').upper()
                    if 'DEPOSITO' in cell_upper or 'ABONO' in cell_upper:
                        deposito_col = col_idx
                    elif 'RETIRO' in cell_upper or 'CARGO' in cell_upper:
                        retiro_col = col_idx
                    elif 'SALDO' in cell_upper:
                        saldo_col = col_idx
                break
        
        # Process data rows
        for row in table[header_idx + 1:]:
            if not row or not any(row):
                continue
            
            try:
                row_str = ' '.join([str(cell or '') for cell in row])
                row_cleaned = [str(cell or '').strip() for cell in row]
                
                # Skip header-like rows
                if any(kw in row_str.upper() for kw in ['SALDO INICIAL', 'SALDO ANTERIOR', 'FECHA', 'DEPOSITO']):
                    continue
                
                # Find date
                fecha = None
                for cell in row_cleaned:
                    # Spanish month format
                    date_match = re.search(r'(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)', cell.upper())
                    if date_match:
                        day = date_match.group(1).zfill(2)
                        month = months_es.get(date_match.group(2), '01')
                        fecha = f"{current_year}-{month}-{day}"
                        break
                    
                    # Numeric date format
                    for pattern in date_patterns:
                        match = re.search(pattern, cell)
                        if match:
                            groups = match.groups()
                            if len(groups[0]) == 4:  # YYYY-MM-DD
                                fecha = f"{groups[0]}-{groups[1].zfill(2)}-{groups[2].zfill(2)}"
                            else:  # DD-MM-YYYY
                                year = groups[2] if len(groups[2]) == 4 else f"20{groups[2]}"
                                fecha = f"{year}-{groups[1].zfill(2)}-{groups[0].zfill(2)}"
                            break
                    if fecha:
                        break
                
                if not fecha:
                    continue
                
                # Extract amounts based on column positions if available
                deposito = 0
                retiro = 0
                saldo = 0
                
                if deposito_col is not None and deposito_col < len(row_cleaned):
                    deposito = parse_amount(row_cleaned[deposito_col])
                
                if retiro_col is not None and retiro_col < len(row_cleaned):
                    retiro = parse_amount(row_cleaned[retiro_col])
                
                if saldo_col is not None and saldo_col < len(row_cleaned):
                    saldo = parse_amount(row_cleaned[saldo_col])
                
                # Find description
                descripcion = ""
                for idx, cell in enumerate(row_cleaned):
                    if idx in [deposito_col, retiro_col, saldo_col]:
                        continue
                    cell_str = str(cell or '').strip()
                    if cell_str and len(cell_str) > len(descripcion) and not re.match(r'^[\d\$\.,\s/-]+$', cell_str):
                        descripcion = cell_str
                
                # If no column positions found, use position-based detection
                if deposito_col is None and retiro_col is None:
                    amounts = []
                    for cell in row_cleaned:
                        val = parse_amount(cell)
                        if val > 0:
                            amounts.append(val)
                    
                    if amounts:
                        saldo = amounts[-1] if len(amounts) > 1 else 0
                        monto = amounts[0] if amounts else 0
                        
                        # Use keyword detection
                        normalized_desc = normalize_text_for_keywords(descripcion)
                        is_dep = is_deposit_transaction(normalized_desc)
                        
                        if is_dep is True:
                            deposito = monto
                        else:
                            retiro = monto
                
                if deposito > 0 or retiro > 0:
                    transactions.append({
                        'fecha': fecha,
                        'descripcion': descripcion or 'Movimiento',
                        'deposito': deposito,
                        'retiro': retiro,
                        'saldo': saldo,
                        'referencia': ''
                    })
                    
            except Exception:
                continue
    
    return transactions


def parse_santander_pdf(text: str, tables: List, saldo_inicial: float = None) -> List[Dict]:
    """Parse Santander bank statement format"""
    import re
    
    transactions = []
    current_year = datetime.now().year
    
    months_es = {
        'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12',
        'ENERO': '01', 'FEBRERO': '02', 'MARZO': '03', 'ABRIL': '04',
        'MAYO': '05', 'JUNIO': '06', 'JULIO': '07', 'AGOSTO': '08',
        'SEPTIEMBRE': '09', 'OCTUBRE': '10', 'NOVIEMBRE': '11', 'DICIEMBRE': '12'
    }
    
    # Santander typically has format: DD/MM/YYYY DESCRIPTION CARGO ABONO SALDO
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Pattern for date at start: DD/MM/YYYY or DD-MM-YYYY
        date_match = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\s+(.+)', line)
        if date_match:
            day = date_match.group(1).zfill(2)
            month = date_match.group(2).zfill(2)
            year = date_match.group(3)
            if len(year) == 2:
                year = f"20{year}"
            fecha = f"{year}-{month}-{day}"
            rest = date_match.group(4)
            
            # Extract amounts from the rest of the line
            amounts = re.findall(r'([\d,]+\.\d{2})', rest)
            if amounts:
                # Description is everything before the first amount
                desc_match = re.match(r'^(.+?)[\d,]+\.\d{2}', rest)
                descripcion = desc_match.group(1).strip() if desc_match else rest[:50]
                
                # Last amount is usually saldo, second to last could be the movement
                deposito = 0
                retiro = 0
                saldo = float(amounts[-1].replace(',', '')) if amounts else 0
                
                if len(amounts) >= 2:
                    monto = float(amounts[-2].replace(',', ''))
                    # Use shared keyword detection
                    is_dep = is_deposit_transaction(descripcion)
                    if is_dep is True:
                        deposito = monto
                    else:
                        retiro = monto
                elif len(amounts) == 1:
                    monto = float(amounts[0].replace(',', ''))
                    is_dep = is_deposit_transaction(descripcion)
                    if is_dep is True:
                        deposito = monto
                    else:
                        retiro = monto
                
                if deposito > 0 or retiro > 0:
                    transactions.append({
                        'fecha': fecha,
                        'descripcion': descripcion,
                        'deposito': deposito,
                        'retiro': retiro,
                        'saldo': saldo,
                        'referencia': ''
                    })
    
    return transactions


def parse_hsbc_pdf(text: str, tables: List, saldo_inicial: float = None) -> List[Dict]:
    """Parse HSBC bank statement format"""
    import re
    
    transactions = []
    current_year = datetime.now().year
    
    # HSBC format varies but often has: DATE REFERENCE DESCRIPTION WITHDRAWALS DEPOSITS BALANCE
    for table in tables:
        if not table or len(table) < 2:
            continue
        
        for row in table[1:]:
            if not row or len(row) < 4:
                continue
            
            try:
                row_str = [str(cell or '').strip() for cell in row]
                
                # Find date
                fecha = None
                for cell in row_str:
                    date_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', cell)
                    if date_match:
                        day = date_match.group(1).zfill(2)
                        month = date_match.group(2).zfill(2)
                        year = date_match.group(3)
                        if len(year) == 2:
                            year = f"20{year}"
                        fecha = f"{year}-{month}-{day}"
                        break
                
                if not fecha:
                    continue
                
                # Get description (usually longest text field)
                descripcion = ""
                for cell in row_str:
                    if len(cell) > len(descripcion) and not re.match(r'^[\d\$\.,\s/-]+$', cell):
                        descripcion = cell
                
                # Extract amounts
                amounts = []
                for cell in row_str:
                    if re.match(r'^[\d,]+\.?\d*$', cell.replace(',', '').replace(' ', '')):
                        try:
                            amounts.append(float(cell.replace(',', '')))
                        except:
                            pass
                
                if amounts and descripcion:
                    deposito = 0
                    retiro = 0
                    saldo = amounts[-1] if len(amounts) > 1 else 0
                    monto = amounts[0] if amounts else 0
                    
                    # Use shared keyword detection
                    is_dep = is_deposit_transaction(descripcion)
                    if is_dep is True:
                        deposito = monto
                    else:
                        retiro = monto
                    
                    if deposito > 0 or retiro > 0:
                        transactions.append({
                            'fecha': fecha,
                            'descripcion': descripcion,
                            'deposito': deposito,
                            'retiro': retiro,
                            'saldo': saldo,
                            'referencia': ''
                        })
            except:
                continue
    
    return transactions


def parse_banamex_pdf(text: str, tables: List, saldo_inicial: float = None) -> List[Dict]:
    """Parse Citibanamex bank statement format"""
    import re
    
    transactions = []
    current_year = datetime.now().year
    
    months_es = {
        'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'
    }
    
    # Banamex often uses: DD MMM DESCRIPTION CARGOS ABONOS SALDO
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Pattern: DD MMM or DD/MM/YYYY
        date_match = re.match(r'^(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s+(.+)', line, re.IGNORECASE)
        if date_match:
            day = date_match.group(1).zfill(2)
            month = months_es.get(date_match.group(2).upper(), '01')
            fecha = f"{current_year}-{month}-{day}"
            rest = date_match.group(3)
            
            # Extract amounts
            amounts = re.findall(r'([\d,]+\.\d{2})', rest)
            if amounts:
                desc_match = re.match(r'^(.+?)[\d,]+\.\d{2}', rest)
                descripcion = desc_match.group(1).strip() if desc_match else rest[:50]
                
                deposito = 0
                retiro = 0
                saldo = float(amounts[-1].replace(',', '')) if amounts else 0
                
                if len(amounts) >= 2:
                    monto = float(amounts[0].replace(',', ''))
                    # Use shared keyword detection
                    is_dep = is_deposit_transaction(descripcion)
                    if is_dep is True:
                        deposito = monto
                    else:
                        retiro = monto
                
                if deposito > 0 or retiro > 0:
                    transactions.append({
                        'fecha': fecha,
                        'descripcion': descripcion,
                        'deposito': deposito,
                        'retiro': retiro,
                        'saldo': saldo,
                        'referencia': ''
                    })
    
    return transactions


@api_router.post("/bank-transactions/preview-pdf")
async def preview_bank_statement_pdf(
    request: Request, 
    file: UploadFile = File(...), 
    banco: str = Form(default="auto"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Preview transactions from PDF without importing.
    Returns detected bank, transactions found, and summary.
    """
    company_id = await get_active_company_id(request, current_user)
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")
    
    try:
        content = await file.read()
        
        # Detect bank type
        import pdfplumber
        detected_bank = banco
        saldo_inicial_detected = None
        
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += (page.extract_text() or "") + "\n"
            
            if banco == "auto":
                text_lower = full_text.lower()
                if "banbajio" in text_lower or "bajio" in text_lower or "banco del bajio" in text_lower:
                    detected_bank = "Banco del Bajío"
                elif "banorte" in text_lower:
                    detected_bank = "Banorte"
                elif "bbva" in text_lower or "bancomer" in text_lower:
                    detected_bank = "BBVA"
                elif "santander" in text_lower:
                    detected_bank = "Santander"
                elif "hsbc" in text_lower:
                    detected_bank = "HSBC"
                elif "scotiabank" in text_lower:
                    detected_bank = "Scotiabank"
                elif "banamex" in text_lower or "citibanamex" in text_lower:
                    detected_bank = "Citibanamex"
                else:
                    detected_bank = "Genérico"
            
            # Try to extract saldo inicial
            import re
            saldo_patterns = [
                r'SALDO\s+INICIAL[:\s]+\$?\s*([\d,]+\.?\d*)',
                r'SALDO\s+ANTERIOR[:\s]+\$?\s*([\d,]+\.?\d*)',
            ]
            for pattern in saldo_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    saldo_inicial_detected = float(match.group(1).replace(',', ''))
                    break
        
        # Parse transactions
        transactions = parse_bank_statement_pdf(content, banco)
        
        # Calculate summary
        total_depositos = sum(t.get('deposito', 0) for t in transactions)
        total_retiros = sum(t.get('retiro', 0) for t in transactions)
        
        # Format for frontend display
        preview_transactions = []
        for txn in transactions:
            monto = txn['deposito'] if txn['deposito'] > 0 else txn['retiro']
            tipo = 'credito' if txn['deposito'] > 0 else 'debito'
            preview_transactions.append({
                'fecha': txn['fecha'],
                'descripcion': txn['descripcion'][:100],
                'monto': monto,
                'tipo': tipo,
                'tipo_display': 'Depósito' if tipo == 'credito' else 'Retiro',
                'saldo': txn.get('saldo', 0),
                'referencia': txn.get('referencia', '')
            })
        
        return {
            'status': 'success',
            'banco_detectado': detected_bank,
            'saldo_inicial_detectado': saldo_inicial_detected,
            'total_movimientos': len(transactions),
            'total_depositos': total_depositos,
            'total_retiros': total_retiros,
            'flujo_neto': total_depositos - total_retiros,
            'transactions': preview_transactions,
            'message': f'Se detectaron {len(transactions)} movimientos del banco {detected_bank}'
        }
        
    except Exception as e:
        logging.error(f"Error previewing PDF: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error procesando PDF: {str(e)}")


@api_router.post("/bank-transactions/import-pdf")
async def import_bank_statement_pdf(
    request: Request, 
    file: UploadFile = File(...), 
    bank_account_id: str = Form(...),
    banco: str = Form(default="auto"),
    current_user: Dict = Depends(get_current_user)
):
    """
    Import bank statement from PDF file.
    Supports Banorte, BBVA, Santander, HSBC and other Mexican banks.
    """
    import io
    
    company_id = await get_active_company_id(request, current_user)
    
    # Verify bank account
    account = await db.bank_accounts.find_one({'id': bank_account_id, 'company_id': company_id}, {'_id': 0})
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")
    
    try:
        content = await file.read()
        
        # Parse the PDF
        transactions = parse_bank_statement_pdf(content, banco)
        
        if not transactions:
            return {
                'status': 'warning',
                'message': 'No se encontraron movimientos en el PDF. Intenta con otro formato o usa la plantilla Excel.',
                'importados': 0,
                'errores': 0,
                'transactions_preview': []
            }
        
        # Import transactions
        imported = 0
        duplicates = 0
        errors = []
        
        for txn in transactions:
            try:
                # Calculate amount and type
                if txn['deposito'] > 0:
                    monto = txn['deposito']
                    tipo = 'credito'
                else:
                    monto = txn['retiro']
                    tipo = 'debito'
                
                if monto == 0:
                    continue
                
                # Check for duplicates
                existing = await db.bank_transactions.find_one({
                    'company_id': company_id,
                    'bank_account_id': bank_account_id,
                    'descripcion': txn['descripcion'],
                    'monto': monto,
                    'fecha_movimiento': {'$regex': f"^{txn['fecha']}"}
                }, {'_id': 0, 'id': 1})
                
                if existing:
                    duplicates += 1
                    continue
                
                # Create transaction
                new_txn = {
                    'id': str(uuid.uuid4()),
                    'company_id': company_id,
                    'bank_account_id': bank_account_id,
                    'fecha_movimiento': f"{txn['fecha']}T12:00:00",
                    'fecha_valor': f"{txn['fecha']}T12:00:00",
                    'descripcion': txn['descripcion'][:500],
                    'referencia': txn.get('referencia', '')[:100],
                    'monto': monto,
                    'tipo_movimiento': tipo,
                    'saldo': txn.get('saldo', 0),
                    'moneda': account.get('moneda', 'MXN'),
                    'fuente': 'pdf_import',
                    'conciliado': False,
                    'created_at': datetime.now(timezone.utc).isoformat()
                }
                
                await db.bank_transactions.insert_one(new_txn)
                imported += 1
                
            except Exception as e:
                errors.append(f"Error en transacción: {str(e)}")
        
        await audit_log(company_id, 'BankTransaction', 'PDF_IMPORT', 'IMPORT', current_user['id'])
        
        return {
            'status': 'success',
            'message': f'Se importaron {imported} movimientos del PDF',
            'importados': imported,
            'duplicados_omitidos': duplicates,
            'errores': len(errors),
            'detalle_errores': errors[:10],
            'total_encontrados': len(transactions)
        }
        
    except Exception as e:
        logging.error(f"Error importing PDF: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error procesando PDF: {str(e)}")


@api_router.get("/fx-rates")
async def list_fx_rates(request: Request, current_user: Dict = Depends(get_current_user)):
    """List all FX rates, normalizing field names from both old and new formats"""
    company_id = await get_active_company_id(request, current_user)
    rates = await db.fx_rates.find({'company_id': company_id}, {'_id': 0}).sort('fecha_vigencia', -1).to_list(1000)
    
    normalized = []
    for r in rates:
        # Normalize field names (support both old and new formats)
        rate_obj = {
            'id': r.get('id', str(uuid.uuid4())),
            'company_id': r.get('company_id'),
            'moneda_base': r.get('moneda_base') or r.get('moneda_destino') or 'MXN',
            'moneda_cotizada': r.get('moneda_cotizada') or r.get('moneda_origen'),
            'tipo_cambio': r.get('tipo_cambio') or r.get('tasa') or 0,
            'fuente': r.get('fuente', 'manual'),
            'auto_sync': r.get('auto_sync', False),
            'fecha_vigencia': r.get('fecha_vigencia'),
            'created_at': r.get('created_at') or r.get('fecha_vigencia')
        }
        
        # Convert date strings to datetime
        for field in ['fecha_vigencia', 'created_at']:
            if isinstance(rate_obj.get(field), str):
                rate_obj[field] = datetime.fromisoformat(rate_obj[field].replace('Z', '+00:00'))
        
        normalized.append(rate_obj)
    
    return normalized

@api_router.post("/fx-rates", response_model=FXRate)
async def create_fx_rate(rate_data: FXRateCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    rate = FXRate(company_id=company_id, **rate_data.model_dump())
    doc = rate.model_dump()
    for field in ['fecha_vigencia', 'created_at']:
        doc[field] = doc[field].isoformat()
    await db.fx_rates.insert_one(doc)
    await audit_log(rate.company_id, 'FXRate', rate.id, 'CREATE', current_user['id'])
    return rate

@api_router.delete("/fx-rates/{rate_id}")
async def delete_fx_rate(rate_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    rate = await db.fx_rates.find_one({'id': rate_id, 'company_id': company_id}, {'_id': 0})
    if not rate:
        raise HTTPException(status_code=404, detail="Tipo de cambio no encontrado")
    await db.fx_rates.delete_one({'id': rate_id})
    await audit_log(company_id, 'FXRate', rate_id, 'DELETE', current_user['id'])
    return {'status': 'success', 'message': 'Tipo de cambio eliminado'}

@api_router.get("/fx-rates/year/{year}")
async def get_fx_rates_by_year(year: int, request: Request, current_user: Dict = Depends(get_current_user)):
    """Get all FX rates for a specific year, grouped by currency and month"""
    company_id = await get_active_company_id(request, current_user)
    
    # Calculate date range for the year
    start_date = datetime(year, 1, 1, tzinfo=timezone.utc).isoformat()
    end_date = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc).isoformat()
    
    # Get all rates for the year
    rates = await db.fx_rates.find({
        'company_id': company_id,
        'fecha_vigencia': {'$gte': start_date, '$lte': end_date}
    }, {'_id': 0}).sort('fecha_vigencia', 1).to_list(5000)
    
    # Organize by currency and month
    by_currency = {}
    monthly_avg = {}
    
    for r in rates:
        moneda = r.get('moneda_cotizada') or r.get('moneda_origen') or 'USD'
        tasa = r.get('tipo_cambio') or r.get('tasa') or 0
        fecha = r.get('fecha_vigencia', '')
        
        if isinstance(fecha, str):
            try:
                fecha_dt = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
            except:
                continue
        else:
            fecha_dt = fecha
        
        mes = fecha_dt.month
        
        if moneda not in by_currency:
            by_currency[moneda] = []
            monthly_avg[moneda] = {}
        
        by_currency[moneda].append({
            'fecha': fecha,
            'tasa': tasa,
            'fuente': r.get('fuente', 'manual')
        })
        
        # Track for monthly average
        if mes not in monthly_avg[moneda]:
            monthly_avg[moneda][mes] = {'sum': 0, 'count': 0}
        monthly_avg[moneda][mes]['sum'] += tasa
        monthly_avg[moneda][mes]['count'] += 1
    
    # Calculate monthly averages
    averages = {}
    for moneda, meses in monthly_avg.items():
        averages[moneda] = {}
        for mes, data in meses.items():
            averages[moneda][mes] = round(data['sum'] / data['count'], 4) if data['count'] > 0 else 0
    
    return {
        'year': year,
        'currencies': list(by_currency.keys()),
        'total_rates': sum(len(v) for v in by_currency.values()),
        'by_currency': by_currency,
        'monthly_averages': averages
    }

@api_router.get("/fx-rates/latest")
async def get_latest_fx_rates(request: Request, current_user: Dict = Depends(get_current_user)):
    """Get latest exchange rates for common currencies"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get company's base currency
    company = await db.companies.find_one({'id': company_id}, {'_id': 0, 'moneda_base': 1})
    moneda_base = company.get('moneda_base', 'MXN') if company else 'MXN'
    
    # Get latest rate for each currency pair - support both old and new field names
    pipeline = [
        {'$match': {'company_id': company_id}},
        {'$sort': {'fecha_vigencia': -1}},
        {'$group': {
            '_id': {'$ifNull': ['$moneda_cotizada', '$moneda_origen']},
            'tasa': {'$first': {'$ifNull': ['$tipo_cambio', '$tasa']}},
            'fecha_vigencia': {'$first': '$fecha_vigencia'}
        }}
    ]
    
    rates = await db.fx_rates.aggregate(pipeline).to_list(100)
    
    # Default rates if none exist
    default_rates = {
        'USD': 17.50,
        'EUR': 19.00,
        'MXN': 1.0
    }
    
    result = {moneda_base: 1.0}  # Base currency is always 1
    for r in rates:
        if r['_id'] and r.get('tasa'):
            result[r['_id']] = r['tasa']
    
    # Fill in defaults for missing currencies
    for currency, rate in default_rates.items():
        if currency not in result and currency != moneda_base:
            result[currency] = rate
    
    return {
        'moneda_base': moneda_base,
        'rates': result,
        'fecha_actualizacion': datetime.now(timezone.utc).isoformat()
    }


@api_router.get("/fx-rates/by-date")
async def get_fx_rate_by_specific_date(
    request: Request, 
    current_user: Dict = Depends(get_current_user),
    moneda: str = "USD",
    fecha: str = None
):
    """Get the exchange rate for a specific currency and date.
    Used for historical reconciliation calculations.
    
    Args:
        moneda: Currency code (USD, EUR, etc.)
        fecha: Date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
    
    Returns:
        Exchange rate for the specified date, or closest previous rate
    """
    company_id = await get_active_company_id(request, current_user)
    
    if moneda == 'MXN':
        return {"moneda": "MXN", "tasa": 1.0, "fecha": fecha or datetime.now(timezone.utc).isoformat()}
    
    # Parse fecha
    fecha_dt = None
    if fecha:
        try:
            if 'T' in fecha:
                fecha_dt = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
            else:
                fecha_dt = datetime.strptime(fecha, '%Y-%m-%d')
        except:
            fecha_dt = datetime.now(timezone.utc)
    else:
        fecha_dt = datetime.now(timezone.utc)
    
    # Get the historical rate using existing function
    tasa = await get_fx_rate_by_date(company_id, moneda, fecha_dt)
    
    return {
        "moneda": moneda,
        "tasa": tasa,
        "fecha": fecha_dt.isoformat() if fecha_dt else None,
        "fecha_solicitada": fecha
    }


@api_router.get("/fx-rates/first-of-month")
async def get_fx_rate_first_of_month(
    request: Request, 
    current_user: Dict = Depends(get_current_user),
    moneda: str = "USD",
    year: int = None,
    month: int = None
):
    """Get the exchange rate for the first day of a specific month.
    Used for calculating account balances with consistent historical rates.
    
    Args:
        moneda: Currency code (USD, EUR, etc.)
        year: Year (defaults to current year)
        month: Month 1-12 (defaults to current month)
    
    Returns:
        Exchange rate for the first day of the month
    """
    company_id = await get_active_company_id(request, current_user)
    
    if moneda == 'MXN':
        return {"moneda": "MXN", "tasa": 1.0, "fecha": None}
    
    # Use current year/month if not specified
    now = datetime.now(timezone.utc)
    year = year or now.year
    month = month or now.month
    
    # First day of the month
    first_of_month = datetime(year, month, 1, tzinfo=timezone.utc)
    
    # Get the rate for first of month
    tasa = await get_fx_rate_by_date(company_id, moneda, first_of_month)
    
    return {
        "moneda": moneda,
        "tasa": tasa,
        "fecha": first_of_month.isoformat(),
        "year": year,
        "month": month
    }


@api_router.post("/fx-rates/sync")
async def sync_fx_rates_realtime(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    Sync exchange rates from Banxico (official) and Open Exchange Rates (complementary)
    - Banxico: USD, EUR, GBP, JPY, CAD (official Mexican rates)
    - Open Exchange Rates: CHF, CNY (complementary)
    """
    from forex_service import get_forex_service, update_fx_rates_in_db
    
    company_id = await get_active_company_id(request, current_user)
    
    try:
        # Fetch and store rates
        rates = await update_fx_rates_in_db(db, company_id)
        
        # Format response
        rates_summary = []
        for currency, info in rates.items():
            if currency != 'MXN':
                rates_summary.append({
                    'moneda': currency,
                    'tasa_mxn': info['rate'],
                    'fuente': info['source'],
                    'actualizado': info['updated_at']
                })
        
        return {
            'status': 'success',
            'message': f'Se actualizaron {len(rates_summary)} tasas de cambio',
            'rates': sorted(rates_summary, key=lambda x: x['moneda']),
            'fuentes': {
                'banxico': ['USD', 'EUR', 'GBP', 'JPY', 'CAD'],
                'openexchange': ['CHF', 'CNY']
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sincronizando tasas: {str(e)}")


@api_router.get("/fx-rates/scheduler-status")
async def get_fx_scheduler_status(current_user: Dict = Depends(get_current_user)):
    """
    Get the status of the automatic FX rate synchronization scheduler
    Shows next scheduled sync times
    """
    from fx_scheduler import get_scheduler_status
    
    status = get_scheduler_status()
    
    # Get last sync log
    last_sync = await db.system_logs.find_one(
        {'type': 'fx_auto_sync'},
        {'_id': 0},
        sort=[('timestamp', -1)]
    )
    
    return {
        'scheduler': status,
        'last_auto_sync': last_sync,
        'config': {
            'sync_times': ['9:00 AM México (matutino)', '1:00 PM México (FIX oficial)'],
            'timezone': 'America/Mexico_City',
            'sources': {
                'banxico': 'Tasas oficiales del Banco de México',
                'openexchange': 'Open Exchange Rates (complementario)'
            }
        }
    }


@api_router.get("/fx-rates/alerts")
async def get_fx_rate_alerts(request: Request, current_user: Dict = Depends(get_current_user)):
    """
    Get alerts for anomalous exchange rate changes (>2% variation from previous day)
    """
    company_id = await get_active_company_id(request, current_user)
    
    alerts = []
    threshold = 0.02  # 2% change threshold
    
    # Get all currencies with recent rates
    currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'CHF', 'CNY']
    
    for currency in currencies:
        # Get last 2 rates for this currency
        rates = await db.fx_rates.find(
            {'company_id': company_id, 'moneda_origen': currency, 'moneda_destino': 'MXN'},
            {'_id': 0, 'tasa': 1, 'fecha_vigencia': 1, 'fuente': 1}
        ).sort('fecha_vigencia', -1).limit(2).to_list(2)
        
        if len(rates) >= 2:
            current_rate = rates[0]['tasa']
            previous_rate = rates[1]['tasa']
            
            if previous_rate > 0:
                change_pct = (current_rate - previous_rate) / previous_rate
                
                if abs(change_pct) >= threshold:
                    direction = 'subió' if change_pct > 0 else 'bajó'
                    alert_type = 'warning' if abs(change_pct) < 0.05 else 'critical'
                    
                    alerts.append({
                        'currency': currency,
                        'current_rate': current_rate,
                        'previous_rate': previous_rate,
                        'change_percent': round(change_pct * 100, 2),
                        'direction': direction,
                        'type': alert_type,
                        'message': f'{currency} {direction} {abs(round(change_pct * 100, 2))}% (${previous_rate:.4f} → ${current_rate:.4f})',
                        'source': rates[0].get('fuente', 'unknown'),
                        'timestamp': rates[0].get('fecha_vigencia')
                    })
    
    return {
        'alerts': sorted(alerts, key=lambda x: abs(x['change_percent']), reverse=True),
        'threshold_percent': threshold * 100,
        'has_alerts': len(alerts) > 0,
        'critical_count': len([a for a in alerts if a['type'] == 'critical']),
        'warning_count': len([a for a in alerts if a['type'] == 'warning'])
    }


@api_router.get("/cfdi/summary")
async def get_cfdi_summary(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    moneda_vista: str = Query('MXN', description="Moneda para mostrar totales")
):
    """Get CFDI summary with currency conversion"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get all CFDIs
    cfdis = await db.cfdis.find({'company_id': company_id}, {'_id': 0}).to_list(10000)
    
    # Get latest FX rates
    company = await db.companies.find_one({'id': company_id}, {'_id': 0, 'moneda_base': 1})
    moneda_base = company.get('moneda_base', 'MXN') if company else 'MXN'
    
    # Get rates - support both old and new field names
    rates_doc = await db.fx_rates.find({'company_id': company_id}).sort('fecha_vigencia', -1).to_list(100)
    rates = {'MXN': 1.0, 'USD': 17.50, 'EUR': 19.00}  # Defaults
    for r in rates_doc:
        moneda = r.get('moneda_cotizada') or r.get('moneda_origen')
        tasa = r.get('tipo_cambio') or r.get('tasa')
        if moneda and tasa:
            rates[moneda] = tasa
    
    # Calculate totals by currency and converted
    totals_by_currency = {'ingresos': {}, 'egresos': {}}
    totals_converted = {'ingresos': 0, 'egresos': 0}
    
    for cfdi in cfdis:
        moneda = cfdi.get('moneda', 'MXN')
        total = cfdi.get('total', 0)
        tipo = 'ingresos' if cfdi.get('tipo_cfdi') == 'ingreso' else 'egresos'
        
        # Sum by original currency
        if moneda not in totals_by_currency[tipo]:
            totals_by_currency[tipo][moneda] = 0
        totals_by_currency[tipo][moneda] += total
        
        # Convert to view currency
        if moneda == moneda_vista:
            totals_converted[tipo] += total
        elif moneda in rates and moneda_vista in rates:
            # Convert: original -> MXN -> target
            if moneda == 'MXN':
                converted = total / rates.get(moneda_vista, 1)
            elif moneda_vista == 'MXN':
                converted = total * rates.get(moneda, 1)
            else:
                # Cross rate
                to_mxn = total * rates.get(moneda, 1)
                converted = to_mxn / rates.get(moneda_vista, 1)
            totals_converted[tipo] += converted
        else:
            totals_converted[tipo] += total
    
    return {
        'moneda_vista': moneda_vista,
        'moneda_base': moneda_base,
        'totales_por_moneda': totals_by_currency,
        'totales_convertidos': totals_converted,
        'balance_convertido': totals_converted['ingresos'] - totals_converted['egresos'],
        'tipos_cambio_usados': rates
    }

@api_router.get("/audit-logs", response_model=List[AuditLog])
async def list_audit_logs(
    current_user: Dict = Depends(get_current_user),
    limit: int = Query(100, le=1000),
    skip: int = Query(0, ge=0)
):
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    logs = await db.audit_logs.find(
        {'company_id': current_user['company_id']},
        {'_id': 0}
    ).sort('timestamp', -1).skip(skip).limit(limit).to_list(limit)
    
    for log in logs:
        if isinstance(log.get('timestamp'), str):
            log['timestamp'] = datetime.fromisoformat(log['timestamp'])
    return logs

@api_router.get("/reports/dashboard")
async def get_dashboard_report(
    request: Request, 
    current_user: Dict = Depends(get_current_user),
    moneda_vista: str = Query('MXN', description='Moneda para mostrar datos'),
    bank_account_id: str = Query(None, description='Filtrar por cuenta bancaria específica'),
    fecha_desde: str = Query(None, description='Fecha inicio del rango (YYYY-MM-DD)'),
    fecha_hasta: str = Query(None, description='Fecha fin del rango (YYYY-MM-DD)')
):
    company_id = await get_active_company_id(request, current_user)
    
    # Get FX rates for conversion
    fx_rates = await db.fx_rates.find(
        {'company_id': company_id},
        {'_id': 0, 'moneda_origen': 1, 'moneda_destino': 1, 'tasa': 1}
    ).sort('fecha_vigencia', -1).to_list(100)
    
    # Build FX rates map (moneda -> MXN rate)
    fx_map = {'MXN': 1.0}
    for rate in fx_rates:
        if rate.get('moneda_destino') == 'MXN':
            fx_map[rate['moneda_origen']] = rate['tasa']
        elif rate.get('moneda_origen') == 'MXN':
            fx_map[rate['moneda_destino']] = 1 / rate['tasa']
    
    # Also check for rates stored by the forex sync service
    synced_rates = await db.fx_rates.find(
        {'company_id': company_id, 'fuente': {'$in': ['banxico', 'openexchange', 'fallback']}},
        {'_id': 0, 'moneda_origen': 1, 'tasa': 1, 'fuente': 1}
    ).sort('updated_at', -1).to_list(20)
    
    for rate in synced_rates:
        currency = rate.get('moneda_origen')
        if currency and currency not in fx_map:
            fx_map[currency] = rate['tasa']
    
    # Default rates for common currencies if not configured
    default_fx_rates = {
        'USD': 17.50,
        'EUR': 19.00,
        'GBP': 22.00,
        'JPY': 0.12,
        'CHF': 19.50,
        'CAD': 12.80,
        'CNY': 2.45
    }
    for currency, rate in default_fx_rates.items():
        if currency not in fx_map:
            fx_map[currency] = rate
    
    # Conversion factor from MXN to target currency
    target_rate = fx_map.get(moneda_vista, 1.0)
    def convert_to_target(mxn_amount):
        if moneda_vista == 'MXN':
            return mxn_amount
        return mxn_amount / target_rate
    
    # Get bank accounts
    bank_query = {'company_id': company_id}
    if bank_account_id:
        bank_query['id'] = bank_account_id
    
    bank_accounts = await db.bank_accounts.find(bank_query, {'_id': 0}).to_list(100)
    
    # Calculate saldos with conversion
    saldo_inicial_mxn = 0.0
    cash_pool_by_currency = {}
    accounts_detail = []
    
    for acc in bank_accounts:
        saldo = acc.get('saldo_inicial', 0)
        moneda = acc.get('moneda', 'MXN')
        tasa = fx_map.get(moneda, 1.0)
        saldo_mxn = saldo * tasa
        saldo_target = convert_to_target(saldo_mxn)
        
        # Cash pooling by currency
        if moneda not in cash_pool_by_currency:
            cash_pool_by_currency[moneda] = {'total': 0, 'cuentas': 0}
        cash_pool_by_currency[moneda]['total'] += saldo
        cash_pool_by_currency[moneda]['cuentas'] += 1
        
        acc['saldo_mxn'] = saldo_mxn
        acc['saldo_target'] = saldo_target
        acc['tasa_conversion'] = tasa
        
        # Risk indicators
        acc['riesgo_ocioso'] = saldo > 500000  # More than 500k idle
        acc['riesgo_bajo_saldo'] = saldo < 10000  # Less than 10k
        
        accounts_detail.append(acc)
        saldo_inicial_mxn += saldo_mxn
    
    saldo_inicial_target = convert_to_target(saldo_inicial_mxn)
    
    # Build date filter for cashflow weeks
    weeks_query = {'company_id': company_id}
    
    # Parse date filters if provided (convert YYYY-MM-DD to datetime for comparison)
    if fecha_desde:
        try:
            from datetime import datetime
            fecha_desde_dt = datetime.fromisoformat(fecha_desde + 'T00:00:00+00:00')
            weeks_query['fecha_inicio'] = {'$gte': fecha_desde_dt.isoformat()}
        except:
            pass  # Ignore invalid date format
    
    if fecha_hasta:
        try:
            from datetime import datetime
            fecha_hasta_dt = datetime.fromisoformat(fecha_hasta + 'T23:59:59+00:00')
            if 'fecha_fin' not in weeks_query:
                weeks_query['fecha_fin'] = {}
            weeks_query['fecha_fin'] = {'$lte': fecha_hasta_dt.isoformat()}
        except:
            pass  # Ignore invalid date format
    
    # Get cashflow weeks with date filter
    weeks = await db.cashflow_weeks.find(
        weeks_query,
        {'_id': 0}
    ).sort('fecha_inicio', 1).limit(52).to_list(52)  # Up to 1 year of weeks
    
    running_balance_mxn = saldo_inicial_mxn
    previous_flujo_neto = 0
    
    for idx, week in enumerate(weeks):
        txn_query = {'company_id': company_id, 'cashflow_week_id': week['id']}
        if bank_account_id:
            txn_query['bank_account_id'] = bank_account_id
        
        transactions = await db.transactions.find(txn_query, {'_id': 0}).to_list(1000)
        
        total_ingresos_mxn = sum(t['monto'] for t in transactions if t['tipo_transaccion'] == 'ingreso')
        total_egresos_mxn = sum(t['monto'] for t in transactions if t['tipo_transaccion'] == 'egreso')
        flujo_neto_mxn = total_ingresos_mxn - total_egresos_mxn
        
        week['saldo_inicial_mxn'] = running_balance_mxn
        week['saldo_inicial'] = convert_to_target(running_balance_mxn)
        week['total_ingresos_mxn'] = total_ingresos_mxn
        week['total_ingresos'] = convert_to_target(total_ingresos_mxn)
        week['total_egresos_mxn'] = total_egresos_mxn
        week['total_egresos'] = convert_to_target(total_egresos_mxn)
        week['flujo_neto_mxn'] = flujo_neto_mxn
        week['flujo_neto'] = convert_to_target(flujo_neto_mxn)
        week['saldo_final_mxn'] = running_balance_mxn + flujo_neto_mxn
        week['saldo_final'] = convert_to_target(week['saldo_final_mxn'])
        
        # Variance calculation (vs previous week)
        if idx > 0:
            week['varianza_flujo'] = flujo_neto_mxn - previous_flujo_neto
            week['varianza_pct'] = (week['varianza_flujo'] / abs(previous_flujo_neto) * 100) if previous_flujo_neto != 0 else 0
        else:
            week['varianza_flujo'] = 0
            week['varianza_pct'] = 0
        
        previous_flujo_neto = flujo_neto_mxn
        running_balance_mxn = week['saldo_final_mxn']
    
    # Calculate trends and risk indicators
    if len(weeks) >= 4:
        recent_flows = [w['flujo_neto_mxn'] for w in weeks[-4:]]
        trend_direction = 'up' if recent_flows[-1] > recent_flows[0] else 'down' if recent_flows[-1] < recent_flows[0] else 'stable'
        avg_flow = sum(recent_flows) / len(recent_flows)
    else:
        trend_direction = 'stable'
        avg_flow = 0
    
    # Risk indicators
    saldo_final_proyectado = weeks[-1]['saldo_final_mxn'] if weeks else saldo_inicial_mxn
    risk_indicators = {
        'liquidez_critica': saldo_final_proyectado < 50000,
        'tendencia_negativa': trend_direction == 'down' and avg_flow < 0,
        'saldos_ociosos': sum(1 for acc in accounts_detail if acc.get('riesgo_ocioso', False)),
        'cuentas_bajo_saldo': sum(1 for acc in accounts_detail if acc.get('riesgo_bajo_saldo', False)),
        'semanas_con_deficit': sum(1 for w in weeks if w.get('flujo_neto_mxn', 0) < 0)
    }
    
    # KPIs
    total_transactions = await db.transactions.count_documents({'company_id': company_id})
    total_cfdis = await db.cfdis.count_documents({'company_id': company_id})
    total_reconciliations = await db.reconciliations.count_documents({'company_id': company_id})
    total_customers = await db.customers.count_documents({'company_id': company_id})
    total_vendors = await db.vendors.count_documents({'company_id': company_id})
    
    return {
        'moneda_vista': moneda_vista,
        'cashflow_weeks': weeks,
        'saldo_inicial_bancos': saldo_inicial_target,
        'saldo_inicial_bancos_mxn': saldo_inicial_mxn,
        'saldo_final_proyectado': convert_to_target(saldo_final_proyectado),
        'saldo_final_proyectado_mxn': saldo_final_proyectado,
        'bank_accounts': accounts_detail,
        'fx_rates_used': fx_map,
        'cash_pool': cash_pool_by_currency,
        'trend': {
            'direction': trend_direction,
            'avg_flow_4w': convert_to_target(avg_flow),
            'avg_flow_4w_mxn': avg_flow
        },
        'risk_indicators': risk_indicators,
        'kpis': {
            'total_transactions': total_transactions,
            'total_cfdis': total_cfdis,
            'total_reconciliations': total_reconciliations,
            'total_customers': total_customers,
            'total_vendors': total_vendors
        }
    }


@api_router.get("/reports/dashboard-from-payments")
async def get_dashboard_from_payments(
    request: Request, 
    current_user: Dict = Depends(get_current_user),
    moneda_vista: str = Query('MXN', description='Moneda para mostrar datos'),
    bank_account_id: Optional[str] = Query(None, description='Filtrar por cuenta bancaria específica')
):
    """
    Dashboard alternativo que genera datos directamente desde pagos reales.
    Usa la misma lógica que CashflowProjections para consistencia.
    """
    from datetime import datetime, timedelta
    
    company_id = await get_active_company_id(request, current_user)
    
    # Get FX rates
    fx_rates = await db.fx_rates.find({'company_id': company_id}, {'_id': 0}).to_list(100)
    fx_map = {'MXN': 1.0, 'USD': 17.5, 'EUR': 20.0}
    for rate in fx_rates:
        if rate.get('moneda_destino') == 'MXN' and rate.get('tasa'):
            fx_map[rate['moneda_origen']] = rate['tasa']
    
    def convert_to_mxn(amount, currency):
        return amount * fx_map.get(currency, 1)
    
    def convert_from_mxn(amount_mxn, target_currency):
        """Convert MXN to target currency"""
        if target_currency == 'MXN':
            return amount_mxn
        rate = fx_map.get(target_currency, 1)
        return amount_mxn / rate if rate else amount_mxn
    
    def to_display_currency(amount_mxn):
        """Convert MXN amount to display currency"""
        return convert_from_mxn(amount_mxn, moneda_vista)
    
    # Get bank account balances - use saldo_inicial like bank-accounts/summary does
    accounts_query = {'company_id': company_id}
    if bank_account_id:
        accounts_query['id'] = bank_account_id
    
    accounts = await db.bank_accounts.find(accounts_query, {'_id': 0}).to_list(50)
    
    # Calculate initial balance
    saldo_bancos_mxn = 0
    selected_account_moneda = 'MXN'
    selected_account_saldo = 0
    
    for acc in accounts:
        saldo = acc.get('saldo_inicial', 0) or 0
        moneda = acc.get('moneda', 'MXN')
        saldo_bancos_mxn += convert_to_mxn(saldo, moneda)
        if bank_account_id and acc.get('id') == bank_account_id:
            selected_account_moneda = moneda
            selected_account_saldo = saldo
    
    # Get all bank transactions
    bank_txns_query = {'company_id': company_id}
    if bank_account_id:
        bank_txns_query['bank_account_id'] = bank_account_id
    
    bank_txns = await db.bank_transactions.find(bank_txns_query, {'_id': 0}).to_list(5000)
    reconciled_ids = set(t['id'] for t in bank_txns if t.get('conciliado') == True)
    bank_txn_to_account = {t['id']: t.get('bank_account_id') for t in bank_txns}
    
    all_payments = await db.payments.find({'company_id': company_id, 'estatus': 'completado'}, {'_id': 0}).to_list(5000)
    
    # Filter to valid payments (reconciled or without bank_transaction_id)
    payments = [p for p in all_payments if not p.get('bank_transaction_id') or p.get('bank_transaction_id') in reconciled_ids]
    
    # If filtering by bank account, only include payments for that account
    if bank_account_id:
        payments = [p for p in payments if p.get('bank_transaction_id') and bank_txn_to_account.get(p['bank_transaction_id']) == bank_account_id]
    
    # Get categories for USD operations
    categories = await db.categories.find({'company_id': company_id}, {'_id': 0}).to_list(100)
    compra_usd_id = next((c['id'] for c in categories if 'compra' in c.get('nombre', '').lower() and 'usd' in c.get('nombre', '').lower()), None)
    venta_usd_id = next((c['id'] for c in categories if 'venta' in c.get('nombre', '').lower() and 'usd' in c.get('nombre', '').lower()), None)
    
    # Generate 13 weeks (4 past, current, 8 future)
    today = datetime.now()
    # Find Monday of current week
    days_since_monday = today.weekday()
    current_monday = today - timedelta(days=days_since_monday)
    start_monday = current_monday - timedelta(weeks=4)
    
    weeks_data = []
    running_balance = saldo_bancos_mxn
    
    for i in range(13):
        week_start = start_monday + timedelta(weeks=i)
        week_end = week_start + timedelta(days=7)
        is_past = week_end <= today
        is_current = week_start <= today < week_end
        
        # Filter payments for this week
        week_payments = [p for p in payments if p.get('fecha_pago')]
        week_payments = [p for p in week_payments if week_start <= datetime.fromisoformat(p['fecha_pago'].replace('Z', '+00:00').split('+')[0]) < week_end]
        
        # Calculate totals excluding USD operations
        ingresos = 0
        egresos = 0
        venta_usd = 0
        compra_usd = 0
        
        for p in week_payments:
            monto_mxn = convert_to_mxn(p.get('monto', 0), p.get('moneda', 'MXN'))
            cat_id = p.get('category_id')
            
            if cat_id == venta_usd_id:
                venta_usd += monto_mxn
            elif cat_id == compra_usd_id:
                compra_usd += monto_mxn
            elif p.get('tipo') == 'cobro':
                ingresos += monto_mxn
            else:
                egresos += monto_mxn
        
        flujo_neto = ingresos - egresos + venta_usd - compra_usd
        saldo_final = running_balance + flujo_neto if is_past or is_current else running_balance
        
        weeks_data.append({
            'week_num': i + 1,
            'week_label': f"S{i + 1}",
            'date_label': week_start.strftime('%d %b'),
            'fecha_inicio': week_start.isoformat(),
            'fecha_fin': week_end.isoformat(),
            'is_past': is_past,
            'is_current': is_current,
            'ingresos': round(ingresos, 2),
            'egresos': round(egresos, 2),
            'venta_usd': round(venta_usd, 2),
            'compra_usd': round(compra_usd, 2),
            'flujo_neto': round(flujo_neto, 2),
            'saldo_inicial': round(running_balance, 2),
            'saldo_final': round(saldo_final, 2),
            'num_payments': len(week_payments)
        })
        
        if is_past or is_current:
            running_balance = saldo_final
    
    # Calculate varianza (change vs previous week) for each week
    for i, week in enumerate(weeks_data):
        if i == 0:
            week['varianza'] = 0
            week['varianza_pct'] = 0
        else:
            prev_week = weeks_data[i - 1]
            week['varianza'] = round(week['flujo_neto'] - prev_week['flujo_neto'], 2)
            if prev_week['flujo_neto'] != 0:
                week['varianza_pct'] = round((week['varianza'] / abs(prev_week['flujo_neto'])) * 100, 1)
            else:
                week['varianza_pct'] = 0
    
    # Calculate KPIs
    past_weeks = [w for w in weeks_data if w['is_past'] or w['is_current']]
    total_ingresos = sum(w['ingresos'] + w['venta_usd'] for w in past_weeks)
    total_egresos = sum(w['egresos'] + w['compra_usd'] for w in past_weeks)
    
    burn_rate = total_egresos / len(past_weeks) if past_weeks else 0
    runway_weeks = running_balance / burn_rate if burn_rate > 0 else float('inf')
    
    # Find critical week (first week with negative balance)
    critical_week = None
    for w in weeks_data:
        if w['saldo_final'] < 0:
            critical_week = w['week_label']
            break
    
    # Build cash pool by currency
    cash_pool = {}
    for acc in accounts:
        moneda = acc.get('moneda', 'MXN')
        saldo = acc.get('saldo_inicial', 0) or 0
        if moneda not in cash_pool:
            cash_pool[moneda] = {'total': 0, 'cuentas': 0}
        cash_pool[moneda]['total'] += saldo
        cash_pool[moneda]['cuentas'] += 1
    
    # Calculate movements per account for current month
    # Group payments by bank account to calculate saldo_final
    account_movements = {}
    for p in payments:
        bank_txn_id = p.get('bank_transaction_id')
        if bank_txn_id:
            acc_id = bank_txn_to_account.get(bank_txn_id)
            if acc_id:
                if acc_id not in account_movements:
                    account_movements[acc_id] = {'ingresos': 0, 'egresos': 0, 'count': 0}
                if p.get('tipo') == 'cobro':
                    account_movements[acc_id]['ingresos'] += p.get('monto', 0)
                else:
                    account_movements[acc_id]['egresos'] += p.get('monto', 0)
                account_movements[acc_id]['count'] += 1
    
    # Build bank accounts detail with calculated saldo_final
    bank_accounts_detail = []
    for acc in accounts:
        saldo_inicial = acc.get('saldo_inicial', 0) or 0
        moneda = acc.get('moneda', 'MXN')
        acc_id = acc.get('id')
        
        # Get movements for this account
        movements = account_movements.get(acc_id, {'ingresos': 0, 'egresos': 0, 'count': 0})
        
        # Calculate saldo_final = saldo_inicial + ingresos - egresos
        saldo_final = saldo_inicial + movements['ingresos'] - movements['egresos']
        
        saldo_inicial_mxn = convert_to_mxn(saldo_inicial, moneda)
        saldo_final_mxn = convert_to_mxn(saldo_final, moneda)
        
        bank_accounts_detail.append({
            'id': acc_id,
            'nombre': acc.get('nombre'),
            'banco': acc.get('banco'),
            'numero_cuenta': acc.get('numero_cuenta'),
            'moneda': moneda,
            'saldo_inicial': saldo_inicial,
            'saldo_final': round(saldo_final, 2),
            'saldo_inicial_mxn': saldo_inicial_mxn,
            'saldo_final_mxn': saldo_final_mxn,
            'saldo_display': round(to_display_currency(saldo_final_mxn), 2),
            'ingresos': round(movements['ingresos'], 2),
            'egresos': round(movements['egresos'], 2),
            'num_movimientos': movements['count'],
            'riesgo': 'bajo' if saldo_final_mxn > 50000 else 'medio' if saldo_final_mxn > 10000 else 'alto'
        })
    
    # Convert weeks data to display currency
    for week in weeks_data:
        week['ingresos_display'] = round(to_display_currency(week['ingresos']), 2)
        week['egresos_display'] = round(to_display_currency(week['egresos']), 2)
        week['flujo_neto_display'] = round(to_display_currency(week['flujo_neto']), 2)
        week['saldo_inicial_display'] = round(to_display_currency(week['saldo_inicial']), 2)
        week['saldo_final_display'] = round(to_display_currency(week['saldo_final']), 2)
        week['varianza_display'] = round(to_display_currency(week.get('varianza', 0)), 2)
    
    # Get FX rate for display
    fx_rate_display = fx_map.get(moneda_vista, 1) if moneda_vista != 'MXN' else 1
    
    # Build response with account filter info
    response = {
        'moneda_vista': moneda_vista,
        'fx_rate': fx_rate_display,
        'saldo_bancos': round(to_display_currency(saldo_bancos_mxn), 2),
        'saldo_proyectado': round(to_display_currency(running_balance), 2),
        'total_ingresos': round(to_display_currency(total_ingresos), 2),
        'total_egresos': round(to_display_currency(total_egresos), 2),
        'burn_rate': round(to_display_currency(burn_rate), 2),
        'runway_weeks': round(runway_weeks, 1) if runway_weeks != float('inf') else None,
        'critical_week': critical_week,
        'cobranza_vs_pagos': round((total_ingresos / total_egresos * 100), 1) if total_egresos > 0 else 100,
        'weeks': weeks_data,
        'cash_pool': cash_pool,
        'bank_accounts': bank_accounts_detail,
        'kpis': {
            'total_payments': len(payments),
            'total_cfdis': await db.cfdis.count_documents({'company_id': company_id}),
            'total_customers': await db.customers.count_documents({'company_id': company_id}),
            'total_vendors': await db.vendors.count_documents({'company_id': company_id})
        }
    }
    
    # Add filtered account info if filtering by specific account
    if bank_account_id and len(accounts) > 0:
        acc = accounts[0]
        response['filtered_account'] = {
            'id': acc.get('id'),
            'nombre': acc.get('nombre'),
            'banco': acc.get('banco'),
            'moneda': acc.get('moneda'),
            'saldo_inicial': acc.get('saldo_inicial', 0) or 0,
            'saldo_inicial_display': round(to_display_currency(convert_to_mxn(acc.get('saldo_inicial', 0) or 0, acc.get('moneda', 'MXN'))), 2),
            'num_movements': len(payments)
        }
    
    return response


# ================== ENDPOINTS AVANZADOS - FASE 2 ==================

# Importar servicios avanzados
from advanced_services import PredictiveAnalysisService, AutoReconciliationService, AlertService
from integration_services import SATScraperService, BankAPIService, SATCredentialManager

# ===== AN\u00c1LISIS PREDICTIVO CON IA =====

@api_router.get("/ai/predictive-analysis")
async def get_predictive_analysis(current_user: Dict = Depends(get_current_user)):
    """An\u00e1lisis predictivo de cashflow con ML + LLM"""
    
    service = PredictiveAnalysisService(db)
    
    # An\u00e1lisis cuantitativo (ML)
    analysis = await service.analyze_cashflow_trends(
        company_id=current_user['company_id'],
        weeks_history=13
    )
    
    if analysis['status'] == 'insufficient_data':
        return analysis
    
    # Insights cualitativos (LLM)
    ai_insights = await service.generate_ai_insights(
        company_id=current_user['company_id'],
        analysis_data=analysis
    )
    
    return {
        'status': 'success',
        'company_id': current_user['company_id'],
        'analisis_cuantitativo': analysis['analisis'],
        'predicciones_8_semanas': analysis['predictions'],
        'insights_ia': ai_insights
    }

# ===== CONCILIACI\u00d3N AUTOM\u00c1TICA INTELIGENTE =====

@api_router.get("/reconciliation/auto-match/{bank_transaction_id}")
async def find_reconciliation_matches(
    bank_transaction_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Encuentra coincidencias autom\u00e1ticas para un movimiento bancario"""
    
    service = AutoReconciliationService(db)
    matches = await service.find_matches(bank_transaction_id, current_user['company_id'])
    
    return {
        'status': 'success',
        'bank_transaction_id': bank_transaction_id,
        'matches_found': len(matches),
        'matches': matches
    }

@api_router.post("/reconciliation/auto-reconcile-batch")
async def auto_reconcile_batch(
    min_score: float = Query(85, ge=60, le=100),
    current_user: Dict = Depends(get_current_user)
):
    """Concilia autom\u00e1ticamente movimientos con alta confianza"""
    
    service = AutoReconciliationService(db)
    result = await service.auto_reconcile_batch(
        company_id=current_user['company_id'],
        user_id=current_user['id'],
        min_score=min_score
    )
    
    return result

# ===== SISTEMA DE ALERTAS =====

@api_router.post("/alerts/check-and-send")
async def check_and_send_alerts(current_user: Dict = Depends(get_current_user)):
    """Verifica condiciones y env\u00eda alertas autom\u00e1ticas"""
    
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    service = AlertService(db)
    alerts = await service.check_and_send_alerts(current_user['company_id'])
    
    return {
        'status': 'success',
        'alerts_sent': len(alerts),
        'alerts': alerts
    }

# ===== SCRAPING SAT AUTOMATIZADO =====

@api_router.post("/sat/download-cfdis")
async def download_cfdis_from_sat(
    fecha_inicio: datetime,
    fecha_fin: datetime,
    tipo: str = Query("recibidos", regex="^(emitidos|recibidos)$"),
    current_user: Dict = Depends(get_current_user)
):
    """Descarga autom\u00e1tica de CFDIs desde portal SAT"""
    
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    service = SATScraperService(db)
    result = await service.download_cfdis_by_date_range(
        company_id=current_user['company_id'],
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        tipo=tipo
    )
    
    return result

@api_router.post("/sat/schedule-automatic")
async def schedule_sat_downloads(
    frequency: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    current_user: Dict = Depends(get_current_user)
):
    """Programa descargas autom\u00e1ticas de CFDIs"""
    
    if current_user['role'] != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    service = SATScraperService(db)
    result = await service.schedule_automatic_download(
        company_id=current_user['company_id'],
        frequency=frequency
    )
    
    return result

@api_router.post("/sat/credentials")
async def store_sat_credentials(
    rfc: str,
    certificado_file: UploadFile = File(...),
    llave_file: UploadFile = File(...),
    password: str = Query(...),
    current_user: Dict = Depends(get_current_user)
):
    """Almacena credenciales CSD/e.firma para el SAT"""
    
    if current_user['role'] != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    certificado_bytes = await certificado_file.read()
    llave_bytes = await llave_file.read()
    
    manager = SATCredentialManager(db)
    result = await manager.store_csd_credentials(
        company_id=current_user['company_id'],
        rfc=rfc,
        certificado_cer=certificado_bytes,
        llave_key=llave_bytes,
        password=password
    )
    
    return result

# ===== INTEGRACI\u00d3N APIS BANCARIAS =====

@api_router.get("/bank-api/available-banks")
async def get_available_banks():
    """Lista de bancos con APIs disponibles"""
    
    service = BankAPIService(db)
    banks = await service.get_available_banks()
    
    return {
        'status': 'success',
        'banks': banks
    }

# ===== AN\u00c1LISIS DE ESCENARIOS "QU\u00c9 PASAR\u00cdA SI" =====

from scenario_service import ScenarioAnalysisService

class ScenarioCreate(BaseModel):
    nombre: str
    descripcion: str
    modificaciones: List[Dict[str, Any]]

@api_router.post("/scenarios/create")
async def create_scenario(
    scenario_data: ScenarioCreate,
    current_user: Dict = Depends(get_current_user)
):
    """Crea un nuevo escenario de simulación 'qué pasaría si'"""
    
    service = ScenarioAnalysisService(db)
    result = await service.create_scenario(
        company_id=current_user['company_id'],
        nombre=scenario_data.nombre,
        descripcion=scenario_data.descripcion,
        modificaciones=scenario_data.modificaciones,
        user_id=current_user['id']
    )
    
    return result

@api_router.get("/scenarios")
async def list_scenarios(current_user: Dict = Depends(get_current_user)):
    """Lista todos los escenarios de la empresa"""
    
    service = ScenarioAnalysisService(db)
    scenarios = await service.list_scenarios(current_user['company_id'])
    
    return {
        'status': 'success',
        'scenarios': scenarios
    }

@api_router.get("/scenarios/{scenario_id}")
async def get_scenario_detail(
    scenario_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Obtiene detalle completo de un escenario"""
    
    service = ScenarioAnalysisService(db)
    scenario = await service.get_scenario_detail(scenario_id, current_user['company_id'])
    
    if not scenario:
        raise HTTPException(status_code=404, detail="Escenario no encontrado")
    
    return scenario

@api_router.post("/scenarios/compare")
async def compare_scenarios(
    scenario_ids: List[str],
    current_user: Dict = Depends(get_current_user)
):
    """Compara múltiples escenarios lado a lado"""
    
    service = ScenarioAnalysisService(db)
    comparison = await service.compare_multiple_scenarios(
        company_id=current_user['company_id'],
        scenario_ids=scenario_ids
    )
    
    return comparison

# ===== EXPORTACI\u00d3N CONTABLE =====

from export_service import AccountingExportService
from fastapi.responses import StreamingResponse

@api_router.get("/export/coi")
async def export_coi(
    fecha_inicio: datetime = Query(...),
    fecha_fin: datetime = Query(...),
    current_user: Dict = Depends(get_current_user)
):
    """Exporta a formato COI (Contabilidad)"""
    
    service = AccountingExportService(db)
    csv_data = await service.export_to_coi(
        company_id=current_user['company_id'],
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )
    
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=coi_export_{fecha_inicio.strftime('%Y%m%d')}.csv"}
    )

@api_router.get("/export/xml-fiscal")
async def export_xml_fiscal(
    fecha_inicio: datetime = Query(...),
    fecha_fin: datetime = Query(...),
    current_user: Dict = Depends(get_current_user)
):
    """Exporta a XML Fiscal (Balanza SAT)"""
    
    service = AccountingExportService(db)
    xml_data = await service.export_to_xml_fiscal(
        company_id=current_user['company_id'],
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )
    
    return StreamingResponse(
        iter([xml_data]),
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename=balanza_sat_{fecha_inicio.strftime('%Y%m%d')}.xml"}
    )

@api_router.get("/export/alegra")
async def export_alegra(
    fecha_inicio: datetime = Query(...),
    fecha_fin: datetime = Query(...),
    current_user: Dict = Depends(get_current_user)
):
    """Exporta a formato Alegra (JSON)"""
    
    service = AccountingExportService(db)
    json_data = await service.export_to_alegra(
        company_id=current_user['company_id'],
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )
    
    return StreamingResponse(
        iter([json_data]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=alegra_export_{fecha_inicio.strftime('%Y%m%d')}.json"}
    )

@api_router.get("/export/cashflow")
async def export_cashflow_report(
    formato: str = Query("excel", regex="^(excel|json)$"),
    current_user: Dict = Depends(get_current_user)
):
    """Exporta reporte de cashflow 13 semanas"""
    
    service = AccountingExportService(db)
    data = await service.export_cashflow_report(
        company_id=current_user['company_id'],
        formato=formato
    )
    
    if formato == 'excel':
        return StreamingResponse(
            iter([data]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=cashflow_report_{datetime.now().strftime('%Y%m%d')}.csv"}
        )
    else:
        return StreamingResponse(
            iter([data]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=cashflow_report_{datetime.now().strftime('%Y%m%d')}.json"}
        )



# ===== OPTIMIZACI\u00d3N GEN\u00c9TICA =====

from genetic_optimizer import GeneticOptimizer

class OptimizationConfig(BaseModel):
    objetivos: Dict[str, Any] = {
        "maximizar_liquidez": True,
        "minimizar_costos": True,
        "evitar_crisis": True
    }
    restricciones: Dict[str, Any] = {
        "max_retraso_dias": 30,
        "max_adelanto_dias": 15,
        "min_saldo": 50000
    }
    parametros: Optional[Dict[str, Any]] = {
        "generaciones": 50,
        "poblacion": 100,
        "prob_mutacion": 0.2
    }

@api_router.post("/optimize/genetic")
async def run_genetic_optimization(
    config: OptimizationConfig,
    current_user: Dict = Depends(get_current_user)
):
    """
    Ejecuta optimización genética del cashflow
    Encuentra automáticamente la mejor combinación de modificaciones
    """
    
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    optimizer = GeneticOptimizer(db)
    
    result = await optimizer.optimize_cashflow(
        company_id=current_user['company_id'],
        objetivos=config.objetivos,
        restricciones=config.restricciones,
        parametros=config.parametros
    )
    
    return result

@api_router.get("/optimize/history")
async def get_optimization_history(current_user: Dict = Depends(get_current_user)):
    """Obtiene histórico de optimizaciones genéticas"""
    
    optimizer = GeneticOptimizer(db)
    history = await optimizer.get_optimization_history(current_user['company_id'])
    
    return {
        'status': 'success',
        'optimizations': history
    }

@api_router.post("/optimize/apply/{optimization_id}")
async def apply_optimization(
    optimization_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Aplica la mejor solución de una optimización genética"""
    
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    # Obtener optimización
    optimization = await db.optimizations.find_one(
        {'id': optimization_id, 'company_id': current_user['company_id']},
        {'_id': 0}
    )
    
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimización no encontrada")
    
    # Obtener mejor soluci\u00f3n
    mejor_solucion = optimization['mejor_solucion']
    modificaciones = mejor_solucion['modificaciones']
    
    # Aplicar modificaciones a las transacciones reales
    aplicadas = 0
    for mod in modificaciones:
        txn_id = mod.get('transaction_id')
        if not txn_id:
            continue
        
        update_data = {}
        if 'nueva_fecha' in mod:
            update_data['fecha_transaccion'] = mod['nueva_fecha']
        if 'nuevo_monto' in mod:
            update_data['monto'] = mod['nuevo_monto']
        
        if update_data:
            result = await db.transactions.update_one(
                {'id': txn_id, 'company_id': current_user['company_id']},
                {'$set': update_data}
            )
            if result.modified_count > 0:
                aplicadas += 1
    
    # Registrar en auditor\u00eda
    await audit_log(
        current_user['company_id'],
        'Optimization',
        optimization_id,
        'APPLY',
        current_user['id'],
        datos_nuevos={'modificaciones_aplicadas': aplicadas}
    )
    
    return {
        'status': 'success',
        'optimization_id': optimization_id,
        'modificaciones_aplicadas': aplicadas,
        'mejora_esperada': mejor_solucion['mejora_flujo_neto']
    }

class BankAPIConnection(BaseModel):
    bank_account_id: str
    bank_name: str
    credentials: Dict[str, str]

@api_router.post("/bank-api/connect")
async def connect_bank_api(
    connection_data: BankAPIConnection,
    current_user: Dict = Depends(get_current_user)
):
    """Conecta cuenta bancaria con su API"""
    
    if current_user['role'] not in [UserRole.ADMIN, UserRole.CFO]:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    service = BankAPIService(db)
    result = await service.connect_bank_account(
        company_id=current_user['company_id'],
        bank_account_id=connection_data.bank_account_id,
        bank_name=connection_data.bank_name,
        credentials=connection_data.credentials
    )
    
    return result

@api_router.post("/bank-api/sync/{bank_account_id}")
async def sync_bank_transactions(
    bank_account_id: str,
    days_back: int = Query(30, ge=1, le=90),
    current_user: Dict = Depends(get_current_user)
):
    """Sincroniza transacciones desde API del banco"""
    
    service = BankAPIService(db)
    result = await service.sync_transactions(
        bank_account_id=bank_account_id,
        days_back=days_back
    )
    
    return result

# ===== DRILL-DOWN ENDPOINT: Week Transactions Detail =====
@api_router.get("/projections/week-detail")
async def get_week_transactions_detail(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    week_start: str = Query(..., description="Start date of the week (YYYY-MM-DD)"),
    week_end: str = Query(..., description="End date of the week (YYYY-MM-DD)"),
    tipo: str = Query('ingreso', description="Type: 'ingreso' or 'egreso'")
):
    """
    Get detailed breakdown of all transactions that make up INGRESOS or EGRESOS for a specific week.
    This is used for auditing and reconciling the cash flow projection numbers.
    
    Returns:
    - cfdis: CFDIs within the week's date range
    - payments: Completed payments within the week
    - total_cfdi: Sum of CFDI amounts
    - total_payments: Sum of payment amounts
    - difference: The gap between payments and CFDIs (unmatched deposits/disbursements)
    """
    from datetime import datetime
    
    company_id = await get_active_company_id(request, current_user)
    
    # Get FX rates for conversion
    rates_docs = await db.fx_rates.find({'company_id': company_id}).sort('fecha_vigencia', -1).to_list(100)
    rates = {'MXN': 1.0, 'USD': 17.50, 'EUR': 19.00}
    for r in rates_docs:
        moneda = r.get('moneda_cotizada') or r.get('moneda_origen')
        tasa = r.get('tipo_cambio') or r.get('tasa')
        if moneda and tasa:
            rates[moneda] = tasa
    
    def convert_to_mxn(amount, currency):
        if not amount:
            return 0
        if currency == 'MXN' or not currency:
            return amount
        return amount * rates.get(currency, 1)
    
    # Get CFDIs for this week
    cfdi_tipo = 'ingreso' if tipo == 'ingreso' else 'egreso'
    cfdi_query = {
        'company_id': company_id,
        'tipo_cfdi': cfdi_tipo,
        'fecha_emision': {'$gte': week_start, '$lt': week_end + 'T23:59:59'}
    }
    cfdis = await db.cfdis.find(cfdi_query, {'_id': 0, 'xml_original': 0}).to_list(1000)
    
    # Get categories for names
    categories = await db.categories.find({'company_id': company_id}, {'_id': 0}).to_list(500)
    categories_map = {c['id']: c for c in categories}
    
    # Get subcategories
    subcategories = await db.subcategories.find({'company_id': company_id}, {'_id': 0}).to_list(500)
    subcategories_map = {s['id']: s for s in subcategories}
    
    # Process CFDIs
    cfdi_records = []
    total_cfdi_mxn = 0
    for cfdi in cfdis:
        monto_mxn = convert_to_mxn(cfdi.get('total', 0), cfdi.get('moneda', 'MXN'))
        total_cfdi_mxn += monto_mxn
        
        cat = categories_map.get(cfdi.get('category_id'), {})
        subcat = subcategories_map.get(cfdi.get('subcategory_id'), {})
        
        cfdi_records.append({
            'id': cfdi.get('id'),
            'uuid': cfdi.get('uuid'),
            'fecha': cfdi.get('fecha_emision'),
            'monto': cfdi.get('total'),
            'moneda': cfdi.get('moneda', 'MXN'),
            'monto_mxn': round(monto_mxn, 2),
            'origen': 'CFDI',
            'categoria': cat.get('nombre', 'Sin categoría'),
            'subcategoria': subcat.get('nombre', ''),
            'emisor': cfdi.get('emisor_nombre'),
            'receptor': cfdi.get('receptor_nombre')
        })
    
    # Get payments for this week
    payment_tipo = 'cobro' if tipo == 'ingreso' else 'pago'
    payment_query = {
        'company_id': company_id,
        'tipo': payment_tipo,
        'estatus': 'completado',
        '$or': [
            {'fecha_pago': {'$gte': week_start, '$lt': week_end + 'T23:59:59'}},
            {'fecha_vencimiento': {'$gte': week_start, '$lt': week_end + 'T23:59:59'}, 'fecha_pago': None}
        ]
    }
    payments = await db.payments.find(payment_query, {'_id': 0}).to_list(1000)
    
    # Process payments - track which have CFDI linkage
    payment_records = []
    total_payments_mxn = 0
    for p in payments:
        monto_mxn = convert_to_mxn(p.get('monto', 0), p.get('moneda', 'MXN'))
        total_payments_mxn += monto_mxn
        
        # Determine origin
        origen = 'Banco' if p.get('bank_transaction_id') else ('CFDI' if p.get('cfdi_id') else 'Manual')
        
        cat = categories_map.get(p.get('category_id'), {})
        subcat = subcategories_map.get(p.get('subcategory_id'), {})
        
        payment_records.append({
            'id': p.get('id'),
            'fecha': p.get('fecha_pago') or p.get('fecha_vencimiento'),
            'monto': p.get('monto'),
            'moneda': p.get('moneda', 'MXN'),
            'monto_mxn': round(monto_mxn, 2),
            'origen': origen,
            'categoria': cat.get('nombre', p.get('concepto', 'Sin categoría')),
            'subcategoria': subcat.get('nombre', ''),
            'beneficiario': p.get('beneficiario', ''),
            'referencia': p.get('referencia', ''),
            'cfdi_id': p.get('cfdi_id'),
            'bank_transaction_id': p.get('bank_transaction_id')
        })
    
    # Calculate difference (unmatched transactions)
    difference = total_payments_mxn - total_cfdi_mxn
    
    return {
        'week_start': week_start,
        'week_end': week_end,
        'tipo': tipo,
        'cfdis': cfdi_records,
        'payments': payment_records,
        'totals': {
            'cfdi_count': len(cfdi_records),
            'cfdi_total_mxn': round(total_cfdi_mxn, 2),
            'payment_count': len(payment_records),
            'payment_total_mxn': round(total_payments_mxn, 2),
            'difference_mxn': round(difference, 2),
            'note': 'Diferencia positiva = Cobros sin CFDI; Negativa = CFDIs sin cobro registrado'
        }
    }

# ===== SUBCATEGORIES ENDPOINTS (for frontend compatibility) =====
@api_router.post("/subcategories")
async def create_subcategory_direct(request: Request, current_user: Dict = Depends(get_current_user)):
    """Create a new subcategory"""
    company_id = await get_active_company_id(request, current_user)
    data = await request.json()
    
    # Validate category exists
    category = await db.categories.find_one({'id': data.get('category_id'), 'company_id': company_id}, {'_id': 0})
    if not category:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    subcategory_doc = {
        'id': str(uuid.uuid4()),
        'company_id': company_id,
        'category_id': data.get('category_id'),
        'nombre': data.get('nombre'),
        'descripcion': data.get('descripcion', ''),
        'activo': True,
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    await db.subcategories.insert_one(subcategory_doc)
    
    return {
        'id': subcategory_doc['id'],
        'nombre': subcategory_doc['nombre'],
        'category_id': subcategory_doc['category_id'],
        'activo': True
    }

@api_router.delete("/subcategories/{subcategory_id}")
async def delete_subcategory_direct(subcategory_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    """Delete a subcategory (soft delete)"""
    company_id = await get_active_company_id(request, current_user)
    
    result = await db.subcategories.update_one(
        {'id': subcategory_id, 'company_id': company_id},
        {'$set': {'activo': False}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Subcategoría no encontrada")
    
    return {'status': 'success', 'message': 'Subcategoría eliminada'}

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global exception handler
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Error interno del servidor. Por favor, intente de nuevo.",
            "error_type": type(exc).__name__
        }
    )

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        from fx_scheduler import start_scheduler
        start_scheduler(db)
        logging.info("✅ FX Rate Scheduler iniciado correctamente")
    except Exception as e:
        logging.error(f"⚠️ Error iniciando FX Scheduler: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    try:
        from fx_scheduler import stop_scheduler
        stop_scheduler()
    except:
        pass
    client.close()