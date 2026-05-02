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
    """Register a new user.
    
    If company_id is not provided, automatically creates a new company
    using company_name (required) and assigns the new user as admin.
    If company_id IS provided, joins the existing company with the given role.
    """
    import uuid as _uuid
    from models.enums import UserRole
    
    existing = await db.users.find_one({'email': user_data.email}, {'_id': 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email ya registrado")
    
    company_id = user_data.company_id
    role = user_data.role
    
    if company_id:
        # Joining an existing company
        company_exists = await db.companies.find_one({'id': company_id}, {'_id': 0})
        if not company_exists:
            raise HTTPException(status_code=400, detail="Empresa no encontrada")
    else:
        # Auto-create a new company for this user
        if not user_data.company_name or not user_data.company_name.strip():
            raise HTTPException(
                status_code=400,
                detail="Debes proporcionar el nombre de tu empresa"
            )
        
        company_id = str(_uuid.uuid4())
        company_doc = {
            'id': company_id,
            'nombre': user_data.company_name.strip(),
            'rfc': (user_data.company_rfc or '').strip().upper() or 'PENDIENTE',
            'moneda_base': 'MXN',
            'pais': 'México',
            'activo': True,
            'inicio_semana': 1,
            'logo_url': None,
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        await db.companies.insert_one(company_doc)
        # First user of a brand-new company becomes admin
        role = UserRole.ADMIN
    
    password_hash = hash_password(user_data.password)
    user = User(
        email=user_data.email,
        nombre=user_data.nombre,
        role=role,
        company_id=company_id
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


@router.post("/auth0/callback")
async def auth0_callback(code: str = Form(...), redirect_uri: str = Form(...)):
    """Exchange Auth0 authorization code for tokens and create/update local user"""
    from auth0_service import exchange_code_for_tokens, get_auth0_service
    import uuid
    import jwt
    from datetime import timedelta
    
    # Get JWT config from environment
    import os
    JWT_SECRET = os.environ.get('JWT_SECRET', 'taxnfin-secret-key-change-in-production')
    
    service = get_auth0_service()
    if not service.is_configured():
        raise HTTPException(status_code=400, detail="Auth0 no está configurado")
    
    try:
        # Exchange code for tokens
        tokens = await exchange_code_for_tokens(code, redirect_uri)
        access_token = tokens.get('access_token')
        id_token = tokens.get('id_token')
        
        # Get user info
        user_info = await service.get_user_info(access_token)
        auth0_id = user_info.get('sub')
        email = user_info.get('email')
        name = user_info.get('name', email.split('@')[0] if email else 'Usuario')
        
        # Look for existing user
        existing_user = await db.users.find_one(
            {'$or': [{'auth0_id': auth0_id}, {'email': email}]},
            {'_id': 0}
        )
        
        if existing_user:
            # Update existing user with Auth0 info
            await db.users.update_one(
                {'id': existing_user['id']},
                {'$set': {
                    'auth0_id': auth0_id,
                    'auth0_last_login': datetime.now(timezone.utc).isoformat()
                }}
            )
            user = existing_user
        else:
            # Create new user
            user_id = str(uuid.uuid4())
            new_user = {
                'id': user_id,
                'email': email,
                'nombre': name,
                'password_hash': '',  # No password for Auth0 users
                'rol': 'user',
                'activo': True,
                'auth0_id': auth0_id,
                'auth0_last_login': datetime.now(timezone.utc).isoformat(),
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            await db.users.insert_one(new_user)
            user = new_user
        
        # Generate internal JWT token
        internal_token = jwt.encode(
            {
                'user_id': user['id'],
                'email': user['email'],
                'auth_method': 'auth0',
                'exp': datetime.now(timezone.utc) + timedelta(days=7)
            },
            JWT_SECRET,
            algorithm='HS256'
        )
        
        return {
            'access_token': internal_token,
            'auth0_token': access_token,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'nombre': user.get('nombre', name),
                'rol': user.get('rol', 'user')
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en autenticación Auth0: {str(e)}")


@router.post("/auth0/verify")
async def verify_auth0_token(token: str = Form(...)):
    """Verify an Auth0 token"""
    from auth0_service import get_auth0_service
    
    service = get_auth0_service()
    if not service.is_configured():
        raise HTTPException(status_code=400, detail="Auth0 no está configurado")
    
    result = await service.verify_token(token)
    
    if not result.get('valid'):
        raise HTTPException(status_code=401, detail=result.get('error', 'Token inválido'))
    
    return result
