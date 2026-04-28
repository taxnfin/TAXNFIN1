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
from routes.pdf_invoices import router as pdf_invoices_router
from routes.alegra import router as alegra_router
from routes.treasury import router as treasury_router
from routes.financial_statements import router as financial_statements_router
from routes.belvo import router as belvo_router
from routes.reports import router as reports_router
from routes.scenarios import router as scenarios_router
from routes.exports import router as exports_router
from routes.advanced import router as advanced_router
from routes.projections import router as projections_router
from routes.import_templates import router as import_templates_router
from routes.cashflow import router as cashflow_router
from routes.payment_matching import router as payment_matching_router
from routes.cfdi_operations import router as cfdi_operations_router
from routes.bank_import import router as bank_import_router

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
api_router.include_router(pdf_invoices_router)
api_router.include_router(alegra_router)
api_router.include_router(treasury_router)
api_router.include_router(financial_statements_router)
api_router.include_router(belvo_router)
api_router.include_router(reports_router)
api_router.include_router(scenarios_router)
api_router.include_router(exports_router)
api_router.include_router(advanced_router)
api_router.include_router(projections_router)
api_router.include_router(import_templates_router)
api_router.include_router(cashflow_router)
api_router.include_router(payment_matching_router)
api_router.include_router(cfdi_operations_router)
api_router.include_router(bank_import_router)

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


# ==================== BELVO INTEGRATION MOVED TO routes/belvo.py ====================

# ==================== VENDORS/CUSTOMERS ENDPOINTS MOVED TO routes/vendors.py & routes/customers.py ====================
# Basic CRUD endpoints are now handled by the modular routers:
# Vendors: POST, GET, PUT /{id}, DELETE /{id}
# Customers: POST, GET, PUT /{id}, DELETE /{id}
# 
# The import/template endpoints below remain here for now:

# ===== PLANTILLAS E IMPORTACIÓN MASIVA =====

# ==================== VENDOR/CUSTOMER TEMPLATES & IMPORT MOVED TO routes/import_templates.py ====================

# ==================== CASHFLOW & TRANSACTIONS MOVED TO routes/cashflow.py ====================

# ==================== BANK-TRANSACTIONS & MANUAL PROJECTIONS MOVED TO routes/cashflow.py ====================

# ==================== PAYMENT MATCHING MOVED TO routes/payment_matching.py ====================

# ==================== AI CATEGORIZATION MOVED TO routes/cfdi_operations.py ====================

# ==================== BANK-TRANSACTIONS IMPORT MOVED TO routes/bank_import.py ====================

# ==================== FX RATES MOVED TO routes/fx_rates.py (DUPLICATES REMOVED) ====================

# ==================== REPORTS & DASHBOARD MOVED TO routes/reports.py ====================

# ==================== AI PREDICTIVE, ALERTS, RECON BATCH, SAT EXTRAS MOVED TO routes/advanced.py ====================

# ==================== SCENARIOS & OPTIMIZATION MOVED TO routes/scenarios.py ====================

# ==================== EXPORTS COI/XML/ALEGRA/CASHFLOW MOVED TO routes/exports.py ====================

# ==================== BANK API CONNECT/SYNC MOVED TO routes/advanced.py ====================

# ==================== PROJECTIONS & SUBCATEGORIES MOVED TO routes/projections.py ====================

# ===== APP SETUP =====
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


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