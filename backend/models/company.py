"""Company models"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
from typing import Optional
import uuid


class Company(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    nombre: str
    rfc: str
    moneda_base: str = "MXN"
    pais: str = "México"
    activo: bool = True
    inicio_semana: int = 1  # 0=Domingo, 1=Lunes, 2=Martes, etc. Default: Lunes
    logo_url: Optional[str] = None  # URL or base64 of company logo
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CompanyCreate(BaseModel):
    nombre: str
    rfc: str
    moneda_base: str = "MXN"
    pais: str = "México"
    inicio_semana: int = 1
    logo_url: Optional[str] = None


class CompanyUpdate(BaseModel):
    nombre: Optional[str] = None
    rfc: Optional[str] = None
    moneda_base: Optional[str] = None
    pais: Optional[str] = None
    inicio_semana: Optional[int] = None
    logo_url: Optional[str] = None
