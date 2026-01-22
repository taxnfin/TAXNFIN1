"""Payment models"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
from typing import Optional
import uuid

from .enums import PaymentStatus, PaymentMethod


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
    tipo_cambio_historico: Optional[float] = None
    metodo_pago: PaymentMethod
    fecha_vencimiento: datetime
    fecha_pago: Optional[datetime] = None
    estatus: PaymentStatus = PaymentStatus.PENDIENTE
    referencia: Optional[str] = None
    beneficiario: Optional[str] = None
    notas: Optional[str] = None
    domiciliacion_activa: bool = False
    es_real: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PaymentCreate(BaseModel):
    bank_account_id: Optional[str] = None
    cfdi_id: Optional[str] = None
    tipo: str
    concepto: str
    monto: float
    moneda: str = "MXN"
    tipo_cambio_historico: Optional[float] = None
    metodo_pago: PaymentMethod
    fecha_vencimiento: datetime
    fecha_pago: Optional[datetime] = None
    estatus: PaymentStatus = PaymentStatus.PENDIENTE
    referencia: Optional[str] = None
    beneficiario: Optional[str] = None
    notas: Optional[str] = None
    domiciliacion_activa: bool = False
    es_real: bool = True
