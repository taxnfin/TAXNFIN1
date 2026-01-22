"""Manual projection concept models"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
from typing import Optional
import uuid


class ManualProjectionConcept(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    nombre: str
    tipo: str  # "ingreso" o "egreso"
    monto: float
    moneda: str = "MXN"
    semana: Optional[int] = None
    mes: Optional[int] = None
    recurrente: bool = False
    categoria: Optional[str] = None
    notas: Optional[str] = None
    activo: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ManualProjectionConceptCreate(BaseModel):
    nombre: str
    tipo: str
    monto: float
    moneda: str = "MXN"
    semana: Optional[int] = None
    mes: Optional[int] = None
    recurrente: bool = False
    categoria: Optional[str] = None
    notas: Optional[str] = None
