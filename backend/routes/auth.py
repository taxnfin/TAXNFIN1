"""Authentication routes"""
from fastapi import APIRouter, Depends, HTTPException, Query, Form
from typing import Dict
from datetime import datetime, timezone

from core.database import db
from core.auth import (
    get_current_user, hash_password, verify_password, create_token
)
from models.auth import User, UserCreate, UserLogin, TokenResponse

router = APIRouter(prefix="/auth")


@router.post("/register", response_model=User)
async def register(user_data: UserCreate):
    """Register a new user"""
    existing = await db.users.find_one({'email': user_data.email}, {'_id': 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email ya registrado")
    
    company_exists = await db.companies.find_one({'id': user_data.company_id}, {'_id': 0})
    if not company_exists:
        raise HTTPException(status_code=400, detail="Empresa no encontrada")
    
    password_hash = hash_password(user_data.password)
    user = User(
        email=user_data.email,
        nombre=user_data.nombre,
        role=user_data.role,
        company_id=user_data.company_id
    )
    
    doc = user.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['password_hash'] = password_hash
    await db.users.insert_one(doc)
    
    return user


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login and get access token"""
    user = await db.users.find_one({'email': credentials.email}, {'_id': 0})
    if not user or not user.get('activo'):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    if not verify_password(credentials.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    token = create_token(user['id'], user['company_id'], user['role'])
    user.pop('password_hash', None)
    
    if isinstance(user.get('created_at'), str):
        user['created_at'] = datetime.fromisoformat(user['created_at'])
    
    return TokenResponse(access_token=token, user=User(**user))


@router.get("/me", response_model=User)
async def get_me(current_user: Dict = Depends(get_current_user)):
    """Get current authenticated user"""
    if isinstance(current_user.get('created_at'), str):
        current_user['created_at'] = datetime.fromisoformat(current_user['created_at'])
    return User(**current_user)


@router.get("/auth0/config")
async def get_auth0_config():
    """Get Auth0 configuration for frontend"""
    from auth0_service import get_auth0_service
    
    service = get_auth0_service()
    
    if not service.is_configured():
        return {
            'enabled': False,
            'message': 'Auth0 no está configurado'
        }
    
    return {
        'enabled': True,
        'domain': service.domain,
        'client_id': service.client_id,
        'audience': service.audience
    }


@router.get("/auth0/login-url")
async def get_auth0_login_url_endpoint(redirect_uri: str = Query(...)):
    """Get Auth0 login URL for redirect"""
    from auth0_service import get_auth0_login_url, get_auth0_service
    
    service = get_auth0_service()
    if not service.is_configured():
        raise HTTPException(status_code=400, detail="Auth0 no está configurado")
    
    import secrets
    state = secrets.token_urlsafe(32)
    login_url = get_auth0_login_url(redirect_uri, state)
    
    return {
        'login_url': login_url,
        'state': state
    }
