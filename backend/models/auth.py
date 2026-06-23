"""User and authentication models"""
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from datetime import datetime, timezone
from typing import Optional, List
import uuid

from .enums import UserRole


class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    nombre: str
    role: UserRole = UserRole.VIEWER
    company_id: str                                                  # empresa principal (backwards compat)
    company_ids: List[str] = Field(default_factory=list)             # todas sus empresas
    empresas_asignadas: List[str] = Field(default_factory=list)      # asignadas por el CFO
    invited_by: Optional[str] = None                                 # user_id del CFO que invitó
    must_change_password: bool = False
    activo: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nombre: str
    role: UserRole = UserRole.VIEWER
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    company_rfc: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User
