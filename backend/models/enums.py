"""Enumeration types for the application"""
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    CFO = "cfo"
    VIEWER = "viewer"


class TransactionType(str, Enum):
    INGRESO = "ingreso"
    EGRESO = "egreso"


class TransactionOrigin(str, Enum):
    BANCO = "banco"
    CSV = "csv"
    MANUAL = "manual"


class CFDIType(str, Enum):
    INGRESO = "ingreso"
    EGRESO = "egreso"
    PAGO = "pago"
    NOTA_CREDITO = "nota_credito"


class CFDIStatus(str, Enum):
    VIGENTE = "vigente"
    CANCELADO = "cancelado"


class BankTransactionType(str, Enum):
    CREDITO = "credito"
    DEBITO = "debito"


class ReconciliationMethod(str, Enum):
    AUTOMATICA = "automatica"
    MANUAL = "manual"


class ReconciliationStatus(str, Enum):
    PENDIENTE = "pendiente"
    CONCILIADO = "conciliado"
    NO_CONCILIABLE = "no_conciliable"


class CategoryType(str, Enum):
    INGRESO = "ingreso"
    EGRESO = "egreso"


class PaymentStatus(str, Enum):
    PENDIENTE = "pendiente"
    COMPLETADO = "completado"
    CANCELADO = "cancelado"
    VENCIDO = "vencido"


class PaymentMethod(str, Enum):
    TRANSFERENCIA = "transferencia"
    CHEQUE = "cheque"
    EFECTIVO = "efectivo"
    TARJETA = "tarjeta"
    DOMICILIACION = "domiciliacion"
    SPEI = "spei"


class BankConnectionStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    INVALID = "invalid"
    DISCONNECTED = "disconnected"
