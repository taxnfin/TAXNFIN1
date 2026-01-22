"""User and authentication models"""
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from datetime import datetime, timezone
from typing import Optional
import uuid

from .enums import UserRole


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
