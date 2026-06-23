"""Authentication routes"""
from fastapi import APIRouter, Depends, HTTPException, Query, Form
from pydantic import BaseModel, EmailStr
from typing import Dict, Optional
from datetime import datetime, timezone, timedelta
import secrets
import os
import logging
import asyncio
import resend

from core.database import db
from core.auth import (
    get_current_user, hash_password, verify_password, create_token
)
from models.auth import User, UserCreate, UserLogin, TokenResponse

router = APIRouter(prefix="/auth")
logger = logging.getLogger(__name__)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


async def _send_reset_email(email: str, reset_link: str, token: str) -> None:
    """Send reset email via Resend. Logs the link to console if RESEND_API_KEY not set."""
    api_key = os.environ.get('RESEND_API_KEY', '')
    logger.info("[RESEND] api_key present=%s key_prefix=%s", bool(api_key), api_key[:8] if api_key else 'NONE')

    if not api_key:
        logger.warning(
            "\n" + "=" * 60 + "\n"
            "DEV MODE — Password Reset Link for %s:\n%s\n"
            "Token: %s\n" + "=" * 60,
            email, reset_link, token
        )
        return

    resend.api_key = api_key
    from_address = os.environ.get('RESEND_FROM', 'TaxnFin <noreply@taxnfin.com>')
    logger.info("[RESEND] from=%s to=%s", from_address, email)

    text_body = (
        f"Recibimos una solicitud para restablecer tu contraseña.\n\n"
        f"Haz clic en el siguiente enlace (válido por 1 hora):\n{reset_link}\n\n"
        f"Si no solicitaste esto, ignora este mensaje."
    )
    html_body = f"""
    <html><body style="font-family:sans-serif;color:#0F172A;max-width:480px;margin:auto">
      <h2>Restablece tu contraseña</h2>
      <p>Recibimos una solicitud para restablecer la contraseña de tu cuenta TaxnFin.</p>
      <p style="margin:24px 0">
        <a href="{reset_link}"
           style="background:#0F172A;color:white;padding:12px 28px;text-decoration:none;
                  border-radius:6px;display:inline-block;font-weight:600">
          Restablecer contraseña
        </a>
      </p>
      <p style="color:#64748B;font-size:13px">
        Este enlace expira en <strong>1 hora</strong>.<br>
        Si no solicitaste esto, puedes ignorar este mensaje.
      </p>
    </body></html>
    """

    params = {
        "from": from_address,
        "to": [email],
        "subject": "Restablece tu contraseña — TaxnFin Cashflow",
        "html": html_body,
        "text": text_body,
    }

    async def _call_resend() -> object:
        return await asyncio.wait_for(
            asyncio.to_thread(resend.Emails.send, params),
            timeout=60.0,
        )

    try:
        logger.info("[RESEND] calling resend.Emails.send (attempt 1) ...")
        result = await _call_resend()
        logger.info("[RESEND] send OK — response: %s", result)
    except Exception as exc:
        logger.warning("[RESEND] attempt 1 failed (%s: %s), retrying ...", type(exc).__name__, exc)
        try:
            result = await _call_resend()
            logger.info("[RESEND] retry OK — response: %s", result)
        except Exception as exc2:
            logger.error("[RESEND] send FAILED after retry — %s: %s", type(exc2).__name__, exc2)
            raise


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
        # SECURITY: Self-registration into an existing company always grants
        # the lowest privilege (viewer). Promotion must be done by an admin
        # via the admin panel. This prevents privilege escalation via the
        # public /register endpoint.
        role = UserRole.VIEWER
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
        # First user of a brand-new company becomes CFO (not admin)
        # Only platform admin (kvillafuerte@taxnfin.com) should have admin role
        role = UserRole.CFO
    
    password_hash = hash_password(user_data.password)
    user = User(
        email=user_data.email,
        nombre=user_data.nombre,
        role=role,
        company_id=company_id,
        company_ids=[company_id],
        empresas_asignadas=[company_id],
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


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    """Generate a password-reset token and email the link.

    Always returns a generic success message to avoid user enumeration.
    """
    logger.info("[FORGOT-PW] request received for email=%s", payload.email)

    frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
    logger.info("[FORGOT-PW] FRONTEND_URL=%s", frontend_url)

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    reset_link = f"{frontend_url}/reset-password?token={token}"

    user = await db.users.find_one({'email': payload.email}, {'_id': 0, 'id': 1})
    logger.info("[FORGOT-PW] user found=%s", bool(user))

    if user:
        await db.password_resets.insert_one({
            'token': token,
            'user_id': user['id'],
            'email': payload.email,
            'expires_at': expires_at.isoformat(),
            'used': False,
            'created_at': datetime.now(timezone.utc).isoformat(),
        })
        logger.info("[FORGOT-PW] reset token saved to DB, calling _send_reset_email ...")
        try:
            await _send_reset_email(payload.email, reset_link, token)
            logger.info("[FORGOT-PW] _send_reset_email completed without exception")
        except Exception as exc:
            logger.error("[FORGOT-PW] _send_reset_email raised %s: %s", type(exc).__name__, exc)

    return {"message": "Si el email existe, recibirás instrucciones para restablecer tu contraseña."}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest):
    """Consume a reset token and update the user's password."""
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")

    record = await db.password_resets.find_one(
        {'token': payload.token, 'used': False}, {'_id': 0}
    )
    if not record:
        raise HTTPException(status_code=400, detail="Token inválido o ya utilizado")

    expires_at = datetime.fromisoformat(record['expires_at'])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="El token ha expirado. Solicita uno nuevo.")

    new_hash = hash_password(payload.new_password)
    await db.users.update_one(
        {'id': record['user_id']},
        {'$set': {'password_hash': new_hash}}
    )
    await db.password_resets.update_one(
        {'token': payload.token},
        {'$set': {'used': True, 'used_at': datetime.now(timezone.utc).isoformat()}}
    )

    return {"message": "Contraseña actualizada correctamente. Ya puedes iniciar sesión."}


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
