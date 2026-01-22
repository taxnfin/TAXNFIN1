# Core module - Database, Auth, Config
from .database import db, client
from .auth import (
    get_current_user, 
    get_active_company_id, 
    hash_password, 
    verify_password, 
    create_token,
    security,
    JWT_SECRET,
    JWT_ALGORITHM
)
from .config import settings

__all__ = [
    'db', 'client',
    'get_current_user', 'get_active_company_id', 
    'hash_password', 'verify_password', 'create_token',
    'security', 'JWT_SECRET', 'JWT_ALGORITHM',
    'settings'
]
