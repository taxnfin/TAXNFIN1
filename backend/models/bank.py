"""Bank-related models"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import uuid

from .enums import BankTransactionType, ReconciliationMethod, BankConnectionStatus


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
    fecha_saldo: Optional[datetime] = None
    activo: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BankAccountCreate(BaseModel):
    nombre: str
    numero_cuenta: str
    banco: str
    moneda: str = "MXN"
    pais_banco: str = "México"
    saldo_inicial: float = 0.0
    fecha_saldo: Optional[datetime] = None


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
    tipo_conciliacion: str = "con_uuid"
    porcentaje_match: float = 100.0
    notas: Optional[str] = None


class BankConnection(BaseModel):
    """Represents a connection to a bank via Belvo"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    bank_account_id: str
    belvo_link_id: str
    institution_name: str
    institution_id: str
    status: BankConnectionStatus = BankConnectionStatus.PENDING
    last_sync: Optional[datetime] = None
    sync_status: str = "never"
    sync_error: Optional[str] = None
    credentials_encrypted: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    activo: bool = True


class BankMovementRaw(BaseModel):
    """Raw bank movement from Belvo - before processing"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    bank_connection_id: str
    bank_account_id: str
    belvo_transaction_id: str
    fecha_movimiento: datetime
    fecha_valor: Optional[datetime] = None
    descripcion: str
    referencia: Optional[str] = None
    monto: float
    tipo_movimiento: str
    saldo: Optional[float] = None
    categoria_belvo: Optional[str] = None
    subcategoria_belvo: Optional[str] = None
    merchant_name: Optional[str] = None
    merchant_logo: Optional[str] = None
    moneda: str = "MXN"
    raw_data: Optional[Dict[str, Any]] = None
    procesado: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
