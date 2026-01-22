"""Base model configuration"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
import uuid


def generate_uuid() -> str:
    return str(uuid.uuid4())


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BaseModelWithConfig(BaseModel):
    """Base model with common configuration"""
    model_config = ConfigDict(extra="ignore")
