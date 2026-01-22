"""Category and subcategory models"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
import uuid

from .enums import CategoryType


class Category(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    nombre: str
    tipo: CategoryType
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
