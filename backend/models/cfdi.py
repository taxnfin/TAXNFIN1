"""CFDI (Electronic Invoice) models"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
from typing import Optional
import uuid

from .enums import CFDIType, CFDIStatus


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
    tipo_cambio: float = 1.0  # Exchange rate used in invoice
    subtotal: float
    descuento: float = 0.0
    impuestos: float
    total: float  # Total in MXN (converted if foreign currency)
    total_moneda_original: Optional[float] = None  # Total in original currency (USD, EUR, etc.)
    metodo_pago: Optional[str] = None  # PUE or PPD
    forma_pago: Optional[str] = None   # 01, 02, 03, etc.
    uso_cfdi: Optional[str] = None     # G01, G02, G03, etc.
    iva_trasladado: float = 0.0
    isr_retenido: float = 0.0
    iva_retenido: float = 0.0
    ieps: float = 0.0
    impuestos_locales: float = 0.0
    estatus: CFDIStatus = CFDIStatus.VIGENTE
    estado_cancelacion: Optional[str] = None
    xml_original: Optional[str] = None
    monto_cobrado: float = 0.0
    monto_pagado: float = 0.0
    category_id: Optional[str] = None
    subcategory_id: Optional[str] = None
    estado_conciliacion: str = "pendiente"
    customer_id: Optional[str] = None
    vendor_id: Optional[str] = None
    notas: Optional[str] = None
    source: Optional[str] = None  # 'alegra', 'sat', 'manual', etc.
    alegra_id: Optional[str] = None  # ID from Alegra if synced
    referencia: Optional[str] = None  # Reference number from source (folio)
    folio_alegra: Optional[str] = None  # Full folio from Alegra (prefix + number)
    fecha_vencimiento: Optional[str] = None  # Due date
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
