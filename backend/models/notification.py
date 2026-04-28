"""Notification and KPI alert rule models"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid


class NotificationLevel(str):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class KpiAlertRule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    metric_key: str          # e.g. "gross_margin", "current_ratio"
    metric_section: str      # e.g. "margins", "liquidity"
    metric_label: str        # e.g. "Margen Bruto"
    condition: str           # "above" or "below"
    threshold: float         # threshold value
    level: str = "warning"   # info, warning, critical
    is_active: bool = True
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KpiAlertRuleCreate(BaseModel):
    metric_key: str
    metric_section: str
    metric_label: str
    condition: str           # "above" or "below"
    threshold: float
    level: str = "warning"


class Notification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str
    user_id: Optional[str] = None
    title: str
    message: str
    level: str = "info"      # info, warning, critical
    category: str = "kpi"    # kpi, system, etc.
    metric_key: Optional[str] = None
    metric_value: Optional[float] = None
    rule_id: Optional[str] = None
    read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
