"""Transaction and CashFlow models"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
from typing import Optional
import uuid

from .enums import TransactionType, TransactionOrigin


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
