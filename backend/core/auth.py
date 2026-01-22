"""Authentication utilities - JWT, password hashing, user verification"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt
import jwt

from .config import settings
from .database import db

JWT_SECRET = settings.JWT_SECRET
JWT_ALGORITHM = settings.JWT_ALGORITHM
JWT_EXPIRATION_HOURS = settings.JWT_EXPIRATION_HOURS

security = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def create_token(user_id: str, company_id: str, role: str) -> str:
    """Create a JWT token for a user"""
    payload = {
        'user_id': user_id,
        'company_id': company_id,
        'role': role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Get current authenticated user from JWT token"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({'id': payload['user_id']}, {'_id': 0, 'password_hash': 0})
        if not user or not user.get('activo'):
            raise HTTPException(status_code=401, detail="Usuario inválido")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")


async def get_active_company_id(request: Request, current_user: Dict = Depends(get_current_user)) -> str:
    """Get the active company ID from header or fallback to user's company"""
    # Check for X-Company-ID header first
    company_id = request.headers.get('X-Company-ID')
    
    if company_id:
        # Verify user has access to this company (admin can access all, others only their own)
        if current_user['role'] == 'admin':
            # Verify company exists
            company = await db.companies.find_one({'id': company_id}, {'_id': 0})
            if company:
                return company_id
        elif company_id == current_user['company_id']:
            return company_id
    
    # Fallback to user's company
    return current_user['company_id']
