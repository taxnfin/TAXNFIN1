"""FX Rate models"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
import uuid


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
