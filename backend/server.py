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
            'n': 'nota_credito',
            't': 'ingreso'  # Traslado -> treat as ingreso
        }
        tipo_raw = root.get('TipoDeComprobante', 'I').lower()
        tipo_cfdi = tipo_comprobante_map.get(tipo_raw, 'ingreso')
        
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
        is_nomina = nomina_element is not None
        
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
            'is_nomina': is_nomina or has_payroll_keywords
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parseando XML CFDI: {str(e)}")

@api_router.post("/auth/register", response_model=User)
async def register(user_data: UserCreate):
    existing = await db.users.find_one({'email': user_data.email}, {'_id': 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email ya registrado")
    
    company_exists = await db.companies.find_one({'id': user_data.company_id}, {'_id': 0})
    if not company_exists:
        raise HTTPException(status_code=400, detail="Empresa no encontrada")
    
    password_hash = hash_password(user_data.password)
    user = User(
        email=user_data.email,
        nombre=user_data.nombre,
        role=user_data.role,
        company_id=user_data.company_id
    )
    
    doc = user.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['password_hash'] = password_hash
    await db.users.insert_one(doc)
    
    await audit_log(user.company_id, 'User', user.id, 'CREATE', user.id)
    return user

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user = await db.users.find_one({'email': credentials.email}, {'_id': 0})
    if not user or not user.get('activo'):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    if not verify_password(credentials.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    token = create_token(user['id'], user['company_id'], user['role'])
    user.pop('password_hash', None)
    
    if isinstance(user.get('created_at'), str):
        user['created_at'] = datetime.fromisoformat(user['created_at'])
    
    return TokenResponse(access_token=token, user=User(**user))

@api_router.get("/auth/me", response_model=User)
async def get_me(current_user: Dict = Depends(get_current_user)):
    if isinstance(current_user.get('created_at'), str):
        current_user['created_at'] = datetime.fromisoformat(current_user['created_at'])
    return User(**current_user)


# ==================== AUTH0 INTEGRATION ====================

@api_router.get("/auth/auth0/config")
async def get_auth0_config():
    """Get Auth0 configuration for frontend"""
    from auth0_service import get_auth0_service
    
    service = get_auth0_service()
    
    if not service.is_configured():
        return {
            'enabled': False,
            'message': 'Auth0 no está configurado'
        }
    
    return {
        'enabled': True,
        'domain': service.domain,
        'client_id': service.client_id,
        'audience': service.audience
    }


@api_router.get("/auth/auth0/login-url")
async def get_auth0_login_url_endpoint(redirect_uri: str = Query(...)):
    """Get Auth0 login URL for redirect"""
    from auth0_service import get_auth0_login_url, get_auth0_service
    
    service = get_auth0_service()
    if not service.is_configured():
        raise HTTPException(status_code=400, detail="Auth0 no está configurado")
    
    import secrets
    state = secrets.token_urlsafe(32)
    login_url = get_auth0_login_url(redirect_uri, state)
    
    return {
        'login_url': login_url,
        'state': state
    }


@api_router.post("/auth/auth0/callback")
async def auth0_callback(code: str = Form(...), redirect_uri: str = Form(...)):
    """Exchange Auth0 authorization code for tokens and create/update local user"""
    from auth0_service import exchange_code_for_tokens, get_auth0_service
    
    service = get_auth0_service()
    if not service.is_configured():
        raise HTTPException(status_code=400, detail="Auth0 no está configurado")
    
    try:
        # Exchange code for tokens
        tokens = await exchange_code_for_tokens(code, redirect_uri)
        access_token = tokens.get('access_token')
        id_token = tokens.get('id_token')
        
        # Get user info
        user_info = await service.get_user_info(access_token)
        auth0_id = user_info.get('sub')
        email = user_info.get('email')
        name = user_info.get('name', email.split('@')[0] if email else 'Usuario')
        
        # Look for existing user
        existing_user = await db.users.find_one(
            {'$or': [{'auth0_id': auth0_id}, {'email': email}]},
            {'_id': 0}
        )
        
        if existing_user:
            # Update existing user with Auth0 info
            await db.users.update_one(
                {'id': existing_user['id']},
                {'$set': {
                    'auth0_id': auth0_id,
                    'auth0_last_login': datetime.now(timezone.utc).isoformat()
                }}
            )
            user = existing_user
        else:
            # Create new user
            user_id = str(uuid.uuid4())
            new_user = {
                'id': user_id,
                'email': email,
                'nombre': name,
                'password_hash': '',  # No password for Auth0 users
                'rol': 'user',
                'activo': True,
                'auth0_id': auth0_id,
                'auth0_last_login': datetime.now(timezone.utc).isoformat(),
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            await db.users.insert_one(new_user)
            user = new_user
        
        # Generate internal JWT token
        internal_token = jwt.encode(
            {
                'user_id': user['id'],
                'email': user['email'],
                'auth_method': 'auth0',
                'exp': datetime.now(timezone.utc) + timedelta(days=7)
            },
            JWT_SECRET,
            algorithm='HS256'
        )
        
        return {
            'access_token': internal_token,
            'auth0_token': access_token,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'nombre': user.get('nombre', name),
                'rol': user.get('rol', 'user')
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en autenticación Auth0: {str(e)}")


@api_router.post("/auth/auth0/verify")
async def verify_auth0_token(token: str = Form(...)):
    """Verify an Auth0 token"""
    from auth0_service import get_auth0_service
    
    service = get_auth0_service()
    if not service.is_configured():
        raise HTTPException(status_code=400, detail="Auth0 no está configurado")
    
    result = await service.verify_token(token)
    
    if not result.get('valid'):
        raise HTTPException(status_code=401, detail=result.get('error', 'Token inválido'))
    
    return result


@api_router.post("/companies", response_model=Company)
async def create_company(company_data: CompanyCreate, current_user: Dict = Depends(get_current_user)):
    company = Company(**company_data.model_dump())
    doc = company.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.companies.insert_one(doc)
    
    # Initialize 13 weeks of cashflow
    await initialize_cashflow_weeks(company.id)
    
    # Create default bank account for the company
    default_account = BankAccount(
        company_id=company.id,
        nombre_banco="Cuenta Principal",
        numero_cuenta="0000000000",
        moneda="MXN",
        saldo_actual=0.0,
        activo=True
    )
    account_doc = default_account.model_dump()
    account_doc['created_at'] = account_doc['created_at'].isoformat()
    await db.bank_accounts.insert_one(account_doc)
    
    return company

@api_router.get("/companies", response_model=List[Company])
async def list_companies(current_user: Dict = Depends(get_current_user)):
    companies = await db.companies.find({'activo': True}, {'_id': 0}).to_list(1000)
    for c in companies:
        if isinstance(c.get('created_at'), str):
            c['created_at'] = datetime.fromisoformat(c['created_at'])
    return companies

@api_router.get("/companies/{company_id}", response_model=Company)
async def get_company(company_id: str, current_user: Dict = Depends(get_current_user)):
    company = await db.companies.find_one({'id': company_id, 'activo': True}, {'_id': 0})
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    if isinstance(company.get('created_at'), str):
        company['created_at'] = datetime.fromisoformat(company['created_at'])
    return Company(**company)

class CompanyUpdate(BaseModel):
    nombre: Optional[str] = None
    rfc: Optional[str] = None
    moneda_base: Optional[str] = None
    pais: Optional[str] = None
    inicio_semana: Optional[int] = None  # 0=Domingo, 1=Lunes, etc.

@api_router.put("/companies/{company_id}")
async def update_company(company_id: str, data: CompanyUpdate, current_user: Dict = Depends(get_current_user)):
    company = await db.companies.find_one({'id': company_id, 'activo': True}, {'_id': 0})
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_data:
        await db.companies.update_one({'id': company_id}, {'$set': update_data})
    
    updated = await db.companies.find_one({'id': company_id}, {'_id': 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return updated

@api_router.post("/bank-accounts", response_model=BankAccount)
async def create_bank_account(account_data: BankAccountCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    account = BankAccount(company_id=company_id, **account_data.model_dump())
    doc = account.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.bank_accounts.insert_one(doc)
    await audit_log(account.company_id, 'BankAccount', account.id, 'CREATE', current_user['id'])
    return account

@api_router.get("/bank-accounts", response_model=List[BankAccount])
async def list_bank_accounts(request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    accounts = await db.bank_accounts.find({'company_id': company_id, 'activo': True}, {'_id': 0}).to_list(1000)
    for a in accounts:
        if isinstance(a.get('created_at'), str):
            a['created_at'] = datetime.fromisoformat(a['created_at'])
    return accounts

@api_router.put("/bank-accounts/{account_id}")
async def update_bank_account(account_id: str, account_data: BankAccountCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    existing = await db.bank_accounts.find_one({'id': account_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    
    update_data = account_data.model_dump()
    await db.bank_accounts.update_one(
        {'id': account_id, 'company_id': company_id},
        {'$set': update_data}
    )
    await audit_log(company_id, 'BankAccount', account_id, 'UPDATE', current_user['id'], existing, update_data)
    
    updated = await db.bank_accounts.find_one({'id': account_id}, {'_id': 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return updated

@api_router.delete("/bank-accounts/{account_id}")
async def delete_bank_account(account_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    existing = await db.bank_accounts.find_one({'id': account_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    
    await db.bank_accounts.update_one(
        {'id': account_id},
        {'$set': {'activo': False}}
    )
    await audit_log(company_id, 'BankAccount', account_id, 'DELETE', current_user['id'])
    return {'status': 'success', 'message': 'Cuenta bancaria eliminada'}

@api_router.get("/bank-accounts/summary")
async def get_bank_accounts_summary(request: Request, current_user: Dict = Depends(get_current_user)):
    """Get summary of all bank accounts with balances by currency.
    Uses historical exchange rates based on fecha_saldo for each account.
    """
    company_id = await get_active_company_id(request, current_user)
    
    accounts = await db.bank_accounts.find({'company_id': company_id, 'activo': True}, {'_id': 0}).to_list(1000)
    
    # Group by currency
    by_currency = {}
    by_bank = {}
    total_mxn = 0
    
    for acc in accounts:
        moneda = acc.get('moneda', 'MXN')
        banco = acc.get('banco', 'Sin banco')
        saldo = acc.get('saldo_inicial', 0)
        fecha_saldo = acc.get('fecha_saldo')
        
        # Get historical exchange rate for the date the balance was recorded
        if fecha_saldo:
            if isinstance(fecha_saldo, str):
                fecha_saldo = datetime.fromisoformat(fecha_saldo.replace('Z', '+00:00'))
            rate = await get_fx_rate_by_date(company_id, moneda, fecha_saldo)
        else:
            # No date specified, use current rate
            rate = await get_fx_rate_by_date(company_id, moneda, None)
        
        # By currency (original amounts)
        if moneda not in by_currency:
            by_currency[moneda] = {'saldo': 0, 'cuentas': 0, 'saldo_mxn': 0}
        by_currency[moneda]['saldo'] += saldo
        by_currency[moneda]['cuentas'] += 1
        
        # Convert to MXN using historical rate
        saldo_mxn = saldo * rate if moneda != 'MXN' else saldo
        by_currency[moneda]['saldo_mxn'] += saldo_mxn
        
        # By bank
        if banco not in by_bank:
            by_bank[banco] = {'saldo_mxn': 0, 'cuentas': [], 'monedas': set()}
        
        by_bank[banco]['saldo_mxn'] += saldo_mxn
        by_bank[banco]['cuentas'].append({
            'id': acc.get('id', ''),
            'nombre': acc.get('nombre', acc.get('nombre_banco', 'Sin nombre')),
            'numero_cuenta': acc.get('numero_cuenta', ''),
            'moneda': moneda,
            'saldo': saldo,
            'saldo_mxn': saldo_mxn,
            'fecha_saldo': acc.get('fecha_saldo'),
            'tipo_cambio_usado': rate
        })
        by_bank[banco]['monedas'].add(moneda)
        
        total_mxn += saldo_mxn
    
    # Convert sets to lists for JSON serialization
    for banco in by_bank:
        by_bank[banco]['monedas'] = list(by_bank[banco]['monedas'])
    
    # Get current fx rates for display
    fx_rates = {'MXN': 1.0}
    rates_docs = await db.fx_rates.find({'company_id': company_id}).sort('fecha_vigencia', -1).to_list(100)
    for r in rates_docs:
        moneda = r.get('moneda_cotizada') or r.get('moneda_origen')
        tasa = r.get('tipo_cambio') or r.get('tasa')
        if moneda and tasa and moneda not in fx_rates:
            fx_rates[moneda] = tasa
    
    return {
        'total_cuentas': len(accounts),
        'total_mxn': total_mxn,
        'por_moneda': by_currency,
        'por_banco': by_bank,
        'tipos_cambio': fx_rates
    }

@api_router.post("/vendors", response_model=Vendor)
async def create_vendor(vendor_data: VendorCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    vendor = Vendor(company_id=company_id, **vendor_data.model_dump())
    doc = vendor.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.vendors.insert_one(doc)
    await audit_log(vendor.company_id, 'Vendor', vendor.id, 'CREATE', current_user['id'])
    return vendor

@api_router.get("/vendors", response_model=List[Vendor])
async def list_vendors(request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    vendors = await db.vendors.find({'company_id': company_id, 'activo': True}, {'_id': 0}).to_list(1000)
    for v in vendors:
        if isinstance(v.get('created_at'), str):
            v['created_at'] = datetime.fromisoformat(v['created_at'])
    return vendors

@api_router.put("/vendors/{vendor_id}")
async def update_vendor(vendor_id: str, vendor_data: VendorCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    existing = await db.vendors.find_one({'id': vendor_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    
    update_data = vendor_data.model_dump()
    await db.vendors.update_one(
        {'id': vendor_id, 'company_id': company_id},
        {'$set': update_data}
    )
    await audit_log(company_id, 'Vendor', vendor_id, 'UPDATE', current_user['id'], existing, update_data)
    
    updated = await db.vendors.find_one({'id': vendor_id}, {'_id': 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return updated

@api_router.delete("/vendors/{vendor_id}")
async def delete_vendor(vendor_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    existing = await db.vendors.find_one({'id': vendor_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    
    await db.vendors.update_one(
        {'id': vendor_id},
        {'$set': {'activo': False}}
    )
    await audit_log(company_id, 'Vendor', vendor_id, 'DELETE', current_user['id'])
    return {'status': 'success', 'message': 'Proveedor eliminado'}

@api_router.post("/customers", response_model=Customer)
async def create_customer(customer_data: CustomerCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    customer = Customer(company_id=company_id, **customer_data.model_dump())
    doc = customer.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.customers.insert_one(doc)
    await audit_log(customer.company_id, 'Customer', customer.id, 'CREATE', current_user['id'])
    return customer

@api_router.get("/customers", response_model=List[Customer])
async def list_customers(request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    customers = await db.customers.find({'company_id': company_id, 'activo': True}, {'_id': 0}).to_list(1000)
    for c in customers:
        if isinstance(c.get('created_at'), str):
            c['created_at'] = datetime.fromisoformat(c['created_at'])
    return customers

@api_router.put("/customers/{customer_id}")
async def update_customer(customer_id: str, customer_data: CustomerCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    existing = await db.customers.find_one({'id': customer_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    update_data = customer_data.model_dump()
    await db.customers.update_one(
        {'id': customer_id, 'company_id': company_id},
        {'$set': update_data}
    )
    await audit_log(company_id, 'Customer', customer_id, 'UPDATE', current_user['id'], existing, update_data)
    
    updated = await db.customers.find_one({'id': customer_id}, {'_id': 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return updated

@api_router.delete("/customers/{customer_id}")
async def delete_customer(customer_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    existing = await db.customers.find_one({'id': customer_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    await db.customers.update_one(
        {'id': customer_id},
        {'$set': {'activo': False}}
    )
    await audit_log(company_id, 'Customer', customer_id, 'DELETE', current_user['id'])
    return {'status': 'success', 'message': 'Cliente eliminado'}

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
        'new_rfc_detected': new_rfc_detected
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
async def create_bank_transaction(transaction_data: BankTransactionCreate, current_user: Dict = Depends(get_current_user)):
    account = await db.bank_accounts.find_one({'id': transaction_data.bank_account_id, 'company_id': current_user['company_id']}, {'_id': 0})
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    
    bank_transaction = BankTransaction(company_id=current_user['company_id'], **transaction_data.model_dump())
    doc = bank_transaction.model_dump()
    for field in ['fecha_movimiento', 'fecha_valor', 'created_at']:
        doc[field] = doc[field].isoformat()
    await db.bank_transactions.insert_one(doc)
    
    await audit_log(bank_transaction.company_id, 'BankTransaction', bank_transaction.id, 'CREATE', current_user['id'])
    return bank_transaction

@api_router.get("/bank-transactions", response_model=List[BankTransaction])
async def list_bank_transactions(
    current_user: Dict = Depends(get_current_user),
    limit: int = Query(100, le=1000),
    skip: int = Query(0, ge=0)
):
    transactions = await db.bank_transactions.find(
        {'company_id': current_user['company_id']},
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

@api_router.post("/reconciliations", response_model=BankReconciliation)
async def create_reconciliation(reconciliation_data: BankReconciliationCreate, current_user: Dict = Depends(get_current_user)):
    bank_txn = await db.bank_transactions.find_one({'id': reconciliation_data.bank_transaction_id, 'company_id': current_user['company_id']}, {'_id': 0})
    if not bank_txn:
        raise HTTPException(status_code=404, detail="Movimiento bancario no encontrado")
    
    reconciliation = BankReconciliation(
        company_id=current_user['company_id'],
        user_id=current_user['id'],
        **reconciliation_data.model_dump()
    )
    
    doc = reconciliation.model_dump()
    for field in ['fecha_conciliacion', 'created_at']:
        doc[field] = doc[field].isoformat()
    await db.reconciliations.insert_one(doc)
    
    await db.bank_transactions.update_one({'id': reconciliation.bank_transaction_id}, {'$set': {'conciliado': True}})
    
    if reconciliation.transaction_id:
        await db.transactions.update_one({'id': reconciliation.transaction_id}, {'$set': {'es_real': True}})
    
    await audit_log(reconciliation.company_id, 'BankReconciliation', reconciliation.id, 'CREATE', current_user['id'])
    return reconciliation

@api_router.get("/reconciliations", response_model=List[BankReconciliation])
async def list_reconciliations(
    current_user: Dict = Depends(get_current_user),
    limit: int = Query(100, le=1000),
    skip: int = Query(0, ge=0)
):
    reconciliations = await db.reconciliations.find(
        {'company_id': current_user['company_id']},
        {'_id': 0}
    ).sort('fecha_conciliacion', -1).skip(skip).limit(limit).to_list(limit)
    
    for r in reconciliations:
        for field in ['fecha_conciliacion', 'created_at']:
            if isinstance(r.get(field), str):
                r[field] = datetime.fromisoformat(r[field])
    return reconciliations

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

# ===== PAGOS =====
@api_router.post("/payments", response_model=Payment)
async def create_payment(payment_data: PaymentCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    payment = Payment(company_id=company_id, **payment_data.model_dump())
    doc = payment.model_dump()
    
    # If payment is "Real", automatically mark as completed
    if doc.get('es_real') == True:
        doc['estatus'] = 'completado'
        doc['fecha_pago'] = datetime.now(timezone.utc).isoformat()
    
    for field in ['fecha_vencimiento', 'created_at']:
        if doc.get(field):
            doc[field] = doc[field].isoformat()
    if doc.get('fecha_pago') and not isinstance(doc['fecha_pago'], str):
        doc['fecha_pago'] = doc['fecha_pago'].isoformat()
    
    await db.payments.insert_one(doc)
    
    # If payment is real and linked to a CFDI, update the CFDI's collected/paid amount
    if doc.get('es_real') == True and doc.get('cfdi_id'):
        cfdi = await db.cfdis.find_one({'id': doc['cfdi_id']}, {'_id': 0})
        if cfdi:
            if doc['tipo'] == 'cobro':
                current_cobrado = cfdi.get('monto_cobrado', 0) or 0
                new_cobrado = current_cobrado + doc['monto']
                await db.cfdis.update_one(
                    {'id': doc['cfdi_id']},
                    {'$set': {'monto_cobrado': new_cobrado}}
                )
                logger.info(f"Auto-completed payment: Updated CFDI {doc['cfdi_id']} monto_cobrado: {current_cobrado} -> {new_cobrado}")
            else:
                current_pagado = cfdi.get('monto_pagado', 0) or 0
                new_pagado = current_pagado + doc['monto']
                await db.cfdis.update_one(
                    {'id': doc['cfdi_id']},
                    {'$set': {'monto_pagado': new_pagado}}
                )
                logger.info(f"Auto-completed payment: Updated CFDI {doc['cfdi_id']} monto_pagado: {current_pagado} -> {new_pagado}")
    
    await audit_log(company_id, 'Payment', payment.id, 'CREATE', current_user['id'])
    return payment


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

@api_router.get("/payments")
async def list_payments(
    request: Request,
    current_user: Dict = Depends(get_current_user),
    tipo: Optional[str] = Query(None, description="cobro o pago"),
    estatus: Optional[str] = Query(None),
    es_real: Optional[str] = Query(None, description="real o proyeccion"),
    fecha_desde: Optional[str] = Query(None),
    fecha_hasta: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    skip: int = Query(0, ge=0)
):
    company_id = await get_active_company_id(request, current_user)
    
    query = {'company_id': company_id}
    if tipo:
        query['tipo'] = tipo
    if estatus:
        query['estatus'] = estatus
    if es_real == 'real':
        query['es_real'] = True
    elif es_real == 'proyeccion':
        query['es_real'] = False
    if fecha_desde:
        query['fecha_vencimiento'] = {'$gte': fecha_desde}
    if fecha_hasta:
        if 'fecha_vencimiento' in query:
            query['fecha_vencimiento']['$lte'] = fecha_hasta
        else:
            query['fecha_vencimiento'] = {'$lte': fecha_hasta}
    
    payments = await db.payments.find(query, {'_id': 0}).sort('fecha_vencimiento', -1).skip(skip).limit(limit).to_list(limit)
    
    for p in payments:
        for field in ['fecha_vencimiento', 'fecha_pago', 'created_at']:
            if isinstance(p.get(field), str):
                p[field] = datetime.fromisoformat(p[field])
    return payments

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
    
    # Calculate pending amounts from CFDIs
    total_por_cobrar_cfdis = 0  # Income CFDIs pending collection
    total_por_pagar_cfdis = 0   # Expense CFDIs pending payment
    cobros_pendientes_count = 0
    pagos_pendientes_count = 0
    
    for cfdi in all_cfdis:
        total = cfdi.get('total', 0) or 0
        moneda = cfdi.get('moneda', 'MXN')
        tipo = cfdi.get('tipo', '')
        
        if tipo == 'ingreso':
            # Income CFDI - pending to collect
            monto_cobrado = cfdi.get('monto_cobrado', 0) or 0
            pendiente = total - monto_cobrado
            if pendiente > 0.01:
                total_por_cobrar_cfdis += convert_to_mxn(pendiente, moneda)
                cobros_pendientes_count += 1
        elif tipo == 'egreso':
            # Expense CFDI - pending to pay
            monto_pagado = cfdi.get('monto_pagado', 0) or 0
            pendiente = total - monto_pagado
            if pendiente > 0.01:
                total_por_pagar_cfdis += convert_to_mxn(pendiente, moneda)
                pagos_pendientes_count += 1
    
    # Get completed payments this month
    start_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    completed_payments = await db.payments.find({
        'company_id': company_id,
        'estatus': 'completado',
        'fecha_pago': {'$gte': start_of_month.isoformat()}
    }, {'_id': 0}).to_list(1000)
    
    # Calculate paid/collected this month
    total_pagado_mes = sum(
        convert_to_mxn(p['monto'], p.get('moneda', 'MXN')) 
        for p in completed_payments if p['tipo'] == 'pago'
    )
    total_cobrado_mes = sum(
        convert_to_mxn(p['monto'], p.get('moneda', 'MXN')) 
        for p in completed_payments if p['tipo'] == 'cobro'
    )
    
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
    
    return {
        'fecha_corte': fecha_corte,
        'total_por_pagar': round(total_por_pagar_cfdis, 2),
        'total_por_cobrar': round(total_por_cobrar_cfdis, 2),
        'pagos_pendientes': pagos_pendientes_count,
        'cobros_pendientes': cobros_pendientes_count,
        'total_pagado_mes': round(total_pagado_mes, 2),
        'total_cobrado_mes': round(total_cobrado_mes, 2),
        'domiciliaciones_activas': len(domiciliados),
        'monto_domiciliado': round(monto_domiciliado, 2),
        'tc_usd': usd_to_mxn,
        'tc_eur': eur_to_mxn
    }

@api_router.put("/payments/{payment_id}")
async def update_payment(payment_id: str, payment_data: PaymentCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    existing = await db.payments.find_one({'id': payment_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    
    old_monto = existing.get('monto', 0)
    old_cfdi_id = existing.get('cfdi_id')
    old_estatus = existing.get('estatus')
    
    update_data = payment_data.model_dump()
    for field in ['fecha_vencimiento', 'fecha_pago']:
        if update_data.get(field):
            update_data[field] = update_data[field].isoformat()
    
    await db.payments.update_one(
        {'id': payment_id, 'company_id': company_id},
        {'$set': update_data}
    )
    
    # If payment was completed and linked to a CFDI, update the CFDI's collected/paid amount
    if old_estatus == 'completado' and old_cfdi_id:
        cfdi = await db.cfdis.find_one({'id': old_cfdi_id}, {'_id': 0})
        if cfdi:
            # Calculate the difference between old and new amount
            new_monto = update_data.get('monto', old_monto)
            diff = new_monto - old_monto
            
            if existing['tipo'] == 'cobro':
                current_cobrado = cfdi.get('monto_cobrado', 0) or 0
                new_cobrado = max(0, current_cobrado + diff)
                await db.cfdis.update_one(
                    {'id': old_cfdi_id},
                    {'$set': {'monto_cobrado': new_cobrado}}
                )
                logger.info(f"Updated CFDI {old_cfdi_id} monto_cobrado after payment edit: {current_cobrado} -> {new_cobrado}")
            else:
                current_pagado = cfdi.get('monto_pagado', 0) or 0
                new_pagado = max(0, current_pagado + diff)
                await db.cfdis.update_one(
                    {'id': old_cfdi_id},
                    {'$set': {'monto_pagado': new_pagado}}
                )
                logger.info(f"Updated CFDI {old_cfdi_id} monto_pagado after payment edit: {current_pagado} -> {new_pagado}")
    
    await audit_log(company_id, 'Payment', payment_id, 'UPDATE', current_user['id'])
    return {'status': 'success', 'message': 'Pago actualizado'}

@api_router.post("/payments/{payment_id}/complete")
async def complete_payment(payment_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    existing = await db.payments.find_one({'id': payment_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    
    # Update payment status
    await db.payments.update_one(
        {'id': payment_id},
        {'$set': {
            'estatus': 'completado',
            'fecha_pago': datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # If payment is linked to a CFDI, update the paid/collected amount
    if existing.get('cfdi_id'):
        cfdi = await db.cfdis.find_one({'id': existing['cfdi_id']}, {'_id': 0})
        if cfdi:
            if existing['tipo'] == 'cobro':
                # Update monto_cobrado for income CFDI
                current_cobrado = cfdi.get('monto_cobrado', 0) or 0
                new_cobrado = current_cobrado + existing['monto']
                await db.cfdis.update_one(
                    {'id': existing['cfdi_id']},
                    {'$set': {'monto_cobrado': new_cobrado}}
                )
                logger.info(f"Updated CFDI {existing['cfdi_id']} monto_cobrado: {current_cobrado} -> {new_cobrado}")
            else:
                # Update monto_pagado for expense CFDI
                current_pagado = cfdi.get('monto_pagado', 0) or 0
                new_pagado = current_pagado + existing['monto']
                await db.cfdis.update_one(
                    {'id': existing['cfdi_id']},
                    {'$set': {'monto_pagado': new_pagado}}
                )
                logger.info(f"Updated CFDI {existing['cfdi_id']} monto_pagado: {current_pagado} -> {new_pagado}")
    
    await audit_log(company_id, 'Payment', payment_id, 'COMPLETE', current_user['id'])
    return {'status': 'success', 'message': 'Pago completado'}

@api_router.delete("/payments/{payment_id}")
async def delete_payment(payment_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    existing = await db.payments.find_one({'id': payment_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    
    # If payment was completed and linked to a CFDI, reverse the collected/paid amount
    if existing.get('estatus') == 'completado' and existing.get('cfdi_id'):
        cfdi = await db.cfdis.find_one({'id': existing['cfdi_id']}, {'_id': 0})
        if cfdi:
            if existing['tipo'] == 'cobro':
                current_cobrado = cfdi.get('monto_cobrado', 0) or 0
                new_cobrado = max(0, current_cobrado - existing['monto'])
                await db.cfdis.update_one(
                    {'id': existing['cfdi_id']},
                    {'$set': {'monto_cobrado': new_cobrado}}
                )
                logger.info(f"Reversed CFDI {existing['cfdi_id']} monto_cobrado after payment delete: {current_cobrado} -> {new_cobrado}")
            else:
                current_pagado = cfdi.get('monto_pagado', 0) or 0
                new_pagado = max(0, current_pagado - existing['monto'])
                await db.cfdis.update_one(
                    {'id': existing['cfdi_id']},
                    {'$set': {'monto_pagado': new_pagado}}
                )
                logger.info(f"Reversed CFDI {existing['cfdi_id']} monto_pagado after payment delete: {current_pagado} -> {new_pagado}")
    
    await db.payments.delete_one({'id': payment_id})
    await audit_log(company_id, 'Payment', payment_id, 'DELETE', current_user['id'])
    return {'status': 'success', 'message': 'Pago eliminado'}

# ===== CATEGORÍAS =====
@api_router.get("/categories")
async def list_categories(request: Request, current_user: Dict = Depends(get_current_user), tipo: Optional[str] = None):
    company_id = await get_active_company_id(request, current_user)
    query = {'company_id': company_id, 'activo': True}
    if tipo:
        query['tipo'] = tipo
    
    categories = await db.categories.find(query, {'_id': 0}).sort('nombre', 1).to_list(1000)
    
    # Get subcategories for each category
    for cat in categories:
        subcats = await db.subcategories.find({'category_id': cat['id'], 'activo': True}, {'_id': 0}).to_list(100)
        cat['subcategorias'] = subcats
    
    return categories

@api_router.post("/categories")
async def create_category(category_data: CategoryCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    category = Category(company_id=company_id, **category_data.model_dump())
    doc = category.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.categories.insert_one(doc)
    await audit_log(company_id, 'Category', category.id, 'CREATE', current_user['id'])
    return {'status': 'success', 'category_id': category.id, 'nombre': category.nombre}

@api_router.put("/categories/{category_id}")
async def update_category(category_id: str, category_data: CategoryCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    existing = await db.categories.find_one({'id': category_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    await db.categories.update_one({'id': category_id}, {'$set': category_data.model_dump()})
    await audit_log(company_id, 'Category', category_id, 'UPDATE', current_user['id'])
    return {'status': 'success', 'message': 'Categoría actualizada'}

@api_router.delete("/categories/{category_id}")
async def delete_category(category_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    existing = await db.categories.find_one({'id': category_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    await db.categories.update_one({'id': category_id}, {'$set': {'activo': False}})
    await db.subcategories.update_many({'category_id': category_id}, {'$set': {'activo': False}})
    await audit_log(company_id, 'Category', category_id, 'DELETE', current_user['id'])
    return {'status': 'success', 'message': 'Categoría eliminada'}

@api_router.post("/subcategories")
async def create_subcategory(subcat_data: SubCategoryCreate, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    
    # Verify category exists
    category = await db.categories.find_one({'id': subcat_data.category_id, 'company_id': company_id}, {'_id': 0})
    if not category:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    subcat = SubCategory(company_id=company_id, **subcat_data.model_dump())
    doc = subcat.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.subcategories.insert_one(doc)
    await audit_log(company_id, 'SubCategory', subcat.id, 'CREATE', current_user['id'])
    return {'status': 'success', 'subcategory_id': subcat.id, 'nombre': subcat.nombre}

@api_router.delete("/subcategories/{subcat_id}")
async def delete_subcategory(subcat_id: str, request: Request, current_user: Dict = Depends(get_current_user)):
    company_id = await get_active_company_id(request, current_user)
    existing = await db.subcategories.find_one({'id': subcat_id, 'company_id': company_id}, {'_id': 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Subcategoría no encontrada")
    
    await db.subcategories.update_one({'id': subcat_id}, {'$set': {'activo': False}})
    await audit_log(company_id, 'SubCategory', subcat_id, 'DELETE', current_user['id'])
    return {'status': 'success', 'message': 'Subcategoría eliminada'}

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
    """Get DIOT data preview - only paid EGRESO CFDIs"""
    company_id = await get_active_company_id(request, current_user)
    
    # Get paid payments (only egresos) in date range
    payment_query = {'company_id': company_id}
    if fecha_desde or fecha_hasta:
        payment_query['fecha_pago'] = {}
        if fecha_desde:
            payment_query['fecha_pago']['$gte'] = datetime.fromisoformat(fecha_desde.replace('Z', '+00:00')) if 'T' in fecha_desde else datetime.strptime(fecha_desde, '%Y-%m-%d')
        if fecha_hasta:
            fecha_hasta_dt = datetime.fromisoformat(fecha_hasta.replace('Z', '+00:00')) if 'T' in fecha_hasta else datetime.strptime(fecha_hasta, '%Y-%m-%d')
            fecha_hasta_dt = fecha_hasta_dt.replace(hour=23, minute=59, second=59)
            payment_query['fecha_pago']['$lte'] = fecha_hasta_dt
    
    payments = await db.payments.find(payment_query, {'_id': 0}).to_list(10000)
    paid_cfdi_ids = [p.get('cfdi_id') for p in payments if p.get('cfdi_id')]
    
    # Get EGRESO CFDIs that have been paid
    cfdi_query = {
        'company_id': company_id,
        'tipo_cfdi': 'egreso',
        'id': {'$in': paid_cfdi_ids}
    }
    
    cfdis = await db.cfdis.find(cfdi_query, {'_id': 0}).to_list(10000)
    
    # Create lookup for payments by CFDI ID
    payments_by_cfdi = {}
    for p in payments:
        cfdi_id = p.get('cfdi_id')
        if cfdi_id:
            if cfdi_id not in payments_by_cfdi:
                payments_by_cfdi[cfdi_id] = []
            payments_by_cfdi[cfdi_id].append(p)
    
    # Get categories
    categories = {c['id']: c for c in await db.categories.find({'company_id': company_id}, {'_id': 0}).to_list(1000)}
    subcategories = {s['id']: s for s in await db.subcategories.find({'company_id': company_id}, {'_id': 0}).to_list(1000)}
    
    records = []
    total_iva = 0
    total_monto = 0
    
    for cfdi in cfdis:
        cfdi_payments = payments_by_cfdi.get(cfdi['id'], [])
        if not cfdi_payments:
            continue
            
        # Use the most recent payment date
        latest_payment = max(cfdi_payments, key=lambda p: p.get('fecha_pago', datetime.min))
        fecha_pago = latest_payment.get('fecha_pago')
        if isinstance(fecha_pago, datetime):
            fecha_pago_str = fecha_pago.strftime('%Y-%m-%d')
        else:
            fecha_pago_str = str(fecha_pago)[:10] if fecha_pago else ''
        
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
        
        # Calculate IVA components
        iva_16 = impuestos if impuestos > 0 else round(subtotal * 0.16, 2)
        
        categoria = categories.get(cfdi.get('category_id'), {}).get('nombre', '')
        subcategoria = subcategories.get(cfdi.get('subcategory_id'), {}).get('nombre', '')
        
        records.append({
            'tipo_tercero': tipo_tercero,
            'tipo_tercero_desc': tipo_tercero_desc,
            'tipo_operacion': '85',  # Otros (default)
            'tipo_operacion_desc': 'Otros',
            'rfc': rfc,
            'nombre': cfdi.get('emisor_nombre', ''),
            'pais': 'MX',
            'nacionalidad': 'Nacional',
            'valor_actos_pagados': total,
            'valor_actos_0': 0,
            'valor_actos_exentos': 0,
            'valor_actos_16': subtotal,
            'iva_retenido': 0,
            'iva_acreditable': iva_16,
            'fecha_pago': fecha_pago_str,
            'uuid': cfdi.get('uuid', ''),
            'categoria': categoria,
            'subcategoria': subcategoria
        })
        
        total_iva += iva_16
        total_monto += total
    
    return {
        'records': records,
        'summary': {
            'totalOperaciones': len(records),
            'totalIVA': round(total_iva, 2),
            'totalMonto': round(total_monto, 2)
        }
    }

# ===== EXPORTAR DIOT =====
@api_router.get("/export/diot")
async def export_diot(request: Request, current_user: Dict = Depends(get_current_user), fecha_desde: str = None, fecha_hasta: str = None):
    """Export CFDIs in DIOT format (CSV)"""
    from fastapi.responses import StreamingResponse
    import io
    import csv
    
    company_id = await get_active_company_id(request, current_user)
    
    query = {'company_id': company_id}
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

# ===== PLANTILLA ESTADO DE CUENTA =====
@api_router.get("/bank-transactions/template")
async def download_bank_statement_template():
    """Download Excel template for importing bank statements"""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from fastapi.responses import StreamingResponse
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Estado de Cuenta"
    
    # Headers with style
    headers = [
        'fecha_movimiento', 'fecha_valor', 'descripcion', 'referencia',
        'monto', 'tipo_movimiento', 'saldo', 'categoria', 'notas'
    ]
    
    header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')
    
    # Example rows
    example_data = [
        ['2026-01-15', '2026-01-15', 'TRANSFERENCIA SPEI CLIENTE ABC', 'REF123456', 50000.00, 'credito', 150000.00, 'Ventas', 'Pago factura 001'],
        ['2026-01-16', '2026-01-16', 'PAGO NOMINA ENERO', 'NOM202601', -25000.00, 'debito', 125000.00, 'Nómina', 'Quincena 1'],
        ['2026-01-17', '2026-01-17', 'COMISION BANCARIA', 'COM001', -150.00, 'debito', 124850.00, 'Gastos Bancarios', ''],
        ['2026-01-18', '2026-01-18', 'DEPOSITO EFECTIVO', 'DEP001', 10000.00, 'credito', 134850.00, 'Otros Ingresos', ''],
    ]
    
    for row_idx, row_data in enumerate(example_data, 2):
        for col_idx, value in enumerate(row_data, 1):
            ws.cell(row=row_idx, column=col_idx, value=value)
    
    # Adjust column widths
    column_widths = [15, 15, 40, 15, 12, 15, 12, 20, 30]
    for col, width in enumerate(column_widths, 1):
        ws.column_dimensions[chr(64 + col)].width = width
    
    # Instructions sheet
    ws2 = wb.create_sheet("Instrucciones")
    instructions = [
        ["Campo", "Descripción", "Formato", "Requerido"],
        ["fecha_movimiento", "Fecha del movimiento bancario", "YYYY-MM-DD", "Sí"],
        ["fecha_valor", "Fecha valor del banco", "YYYY-MM-DD", "Sí"],
        ["descripcion", "Descripción del movimiento", "Texto", "Sí"],
        ["referencia", "Referencia bancaria", "Texto", "No"],
        ["monto", "Monto del movimiento (positivo o negativo)", "Número", "Sí"],
        ["tipo_movimiento", "Tipo: credito (abono) o debito (cargo)", "credito/debito", "Sí"],
        ["saldo", "Saldo después del movimiento", "Número", "Sí"],
        ["categoria", "Categoría del movimiento", "Texto", "No"],
        ["notas", "Notas adicionales", "Texto", "No"],
        ["", "", "", ""],
        ["IMPORTANTE:", "", "", ""],
        ["- Los montos de débito pueden ser negativos o positivos con tipo_movimiento='debito'", "", "", ""],
        ["- El saldo debe coincidir con su estado de cuenta", "", "", ""],
        ["- Las fechas deben estar en formato YYYY-MM-DD", "", "", ""],
    ]
    for row_idx, row_data in enumerate(instructions, 1):
        for col_idx, value in enumerate(row_data, 1):
            ws2.cell(row=row_idx, column=col_idx, value=value)
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_estado_cuenta.xlsx"}
    )

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
    
    required_cols = ['fecha_movimiento', 'descripcion', 'monto', 'tipo_movimiento', 'saldo']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Columnas faltantes: {', '.join(missing)}")
    
    imported = 0
    errors = []
    
    for idx, row in df.iterrows():
        try:
            txn = {
                'id': str(uuid.uuid4()),
                'company_id': company_id,
                'bank_account_id': bank_account_id,
                'fecha_movimiento': str(row['fecha_movimiento'])[:19],
                'fecha_valor': str(row.get('fecha_valor', row['fecha_movimiento']))[:19],
                'descripcion': str(row['descripcion']),
                'referencia': str(row.get('referencia', '')),
                'monto': float(row['monto']),
                'tipo_movimiento': str(row['tipo_movimiento']).lower(),
                'saldo': float(row['saldo']),
                'conciliado': False,
                'estado_conciliacion': 'pendiente',
                'categoria': str(row.get('categoria', '')),
                'notas': str(row.get('notas', '')),
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
            
            # Parse based on detected bank - use universal parser for all
            # The universal parser identifies columns by header names
            if detected_bank in ["banbajio", "banorte", "bbva", "santander", "hsbc", "banamex", "scotiabank"]:
                transactions = parse_mexican_bank_pdf(full_text, all_tables, pdf, saldo_inicial)
            else:
                transactions = parse_mexican_bank_pdf(full_text, all_tables, pdf, saldo_inicial)
            
    except Exception as e:
        logging.error(f"Error parsing PDF: {str(e)}")
        raise
    
    return transactions


def parse_mexican_bank_pdf(text: str, tables: List, pdf, saldo_inicial: float = None) -> List[Dict]:
    """
    Universal parser for Mexican bank PDFs.
    Only captures transactions with valid dates (DD MMM format like "1 DIC", "15 ENE").
    Ignores summary rows, totals, and invalid data.
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
    
    def is_valid_date(day: int, month: str) -> bool:
        """Check if day and month are valid"""
        if month not in months_es:
            return False
        if day < 1 or day > 31:
            return False
        return True
    
    def extract_valid_date(text: str) -> tuple:
        """Extract and validate date from text. Returns (fecha_str, match_end) or (None, 0)"""
        # Only match DD MMM at the START of text or after whitespace
        match = re.search(r'(?:^|\s)(\d{1,2})\s*(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\b', text.upper())
        if match:
            day = int(match.group(1))
            month = match.group(2)
            if is_valid_date(day, month):
                month_num = months_es[month]
                fecha = f"{current_year}-{month_num}-{str(day).zfill(2)}"
                return (fecha, match.end())
        return (None, 0)
    
    # Process using plain text - most reliable for Mexican bank PDFs
    lines = text.split('\n')
    
    # Words to skip - these are summary/header lines
    skip_keywords = [
        'SALDO INICIAL', 'SALDO ANTERIOR', 'SALDO FINAL', 
        'TOTAL', 'RESUMEN', 'DEPOSITOS', 'RETIROS', 'CARGOS',
        'FECHA', 'NO. REF', 'DESCRIPCION', 'OPERACION',
        '(+)', '(-)', 'PROMEDIO', 'MENSUAL', 'MINIMO'
    ]
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        line_upper = line.upper()
        
        # Skip summary and header lines
        if any(skip in line_upper for skip in skip_keywords):
            continue
        
        # Try to extract a valid date from the beginning of the line
        fecha, date_end = extract_valid_date(line)
        if not fecha:
            continue
        
        # Get the rest of the line after the date
        rest_of_line = line[date_end:].strip() if date_end > 0 else line
        
        # Extract all monetary amounts from this line
        amounts = re.findall(r'([\d,]+\.\d{2})', rest_of_line)
        amounts = [float(a.replace(',', '')) for a in amounts]
        
        # We need at least 2 amounts (movement + saldo) or 3 (dep, ret, saldo)
        if len(amounts) < 2:
            continue
        
        # Get description - text between date and first amount
        first_amount_match = re.search(r'[\d,]+\.\d{2}', rest_of_line)
        if first_amount_match:
            descripcion = rest_of_line[:first_amount_match.start()].strip()
        else:
            descripcion = rest_of_line[:50]
        
        # Clean up description - remove reference numbers
        descripcion = re.sub(r'^\d+\s+', '', descripcion)  # Remove leading numbers (reference)
        descripcion = descripcion.strip()
        
        # Parse amounts based on position
        # Format: [maybe other numbers...] DEPOSITO RETIRO SALDO
        # Last 3 values are the key ones
        deposito = 0
        retiro = 0
        saldo = amounts[-1] if amounts else 0  # Last is always SALDO
        
        if len(amounts) >= 3:
            # We have DEP, RET, SALDO
            dep_val = amounts[-3]
            ret_val = amounts[-2]
            
            # In Mexican bank statements, one of DEP/RET is usually 0
            # The non-zero one is the movement
            if dep_val > 0 and (ret_val == 0 or ret_val == dep_val):
                deposito = dep_val
                retiro = 0
            elif ret_val > 0 and (dep_val == 0 or dep_val == ret_val):
                retiro = ret_val
                deposito = 0
            elif dep_val > 0 and ret_val > 0 and dep_val != ret_val:
                # Both have different values - unusual but possible
                deposito = dep_val
                retiro = ret_val
        elif len(amounts) == 2:
            # Only movement and saldo
            monto = amounts[0]
            saldo = amounts[1]
            
            # Use description to determine if deposit or withdrawal
            desc_upper = descripcion.upper()
            if any(kw in desc_upper for kw in ['DEPOSITO', 'ABONO', 'INGRESO', 'RECIBID', 'TRANSFERENCIA']):
                deposito = monto
            else:
                retiro = monto
        
        # Only add valid transactions
        if (deposito > 0 or retiro > 0) and deposito != retiro:
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