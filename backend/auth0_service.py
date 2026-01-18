"""
Auth0 Service - Integration with Auth0 for enterprise identity management
Supports both M2M (machine-to-machine) and user authentication
"""
import os
import httpx
from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError
from typing import Dict, Optional
from datetime import datetime, timezone
import json

# Auth0 Configuration
AUTH0_DOMAIN = os.environ.get('AUTH0_DOMAIN', '')
AUTH0_CLIENT_ID = os.environ.get('AUTH0_CLIENT_ID', '')
AUTH0_CLIENT_SECRET = os.environ.get('AUTH0_CLIENT_SECRET', '')
AUTH0_AUDIENCE = os.environ.get('AUTH0_AUDIENCE', '')
AUTH0_ALGORITHMS = ['RS256']

# Cache for JWKS
_jwks_cache = None
_jwks_cache_time = None
JWKS_CACHE_TTL = 3600  # 1 hour


class Auth0Service:
    """Service for Auth0 authentication and authorization"""
    
    def __init__(self):
        self.domain = AUTH0_DOMAIN
        self.client_id = AUTH0_CLIENT_ID
        self.client_secret = AUTH0_CLIENT_SECRET
        self.audience = AUTH0_AUDIENCE
        self.issuer = f"https://{self.domain}/"
        self.jwks_url = f"https://{self.domain}/.well-known/jwks.json"
    
    async def get_jwks(self) -> dict:
        """
        Fetch JSON Web Key Set from Auth0 (with caching)
        """
        global _jwks_cache, _jwks_cache_time
        
        now = datetime.now(timezone.utc).timestamp()
        
        # Return cached JWKS if valid
        if _jwks_cache and _jwks_cache_time and (now - _jwks_cache_time) < JWKS_CACHE_TTL:
            return _jwks_cache
        
        # Fetch fresh JWKS
        async with httpx.AsyncClient() as client:
            response = await client.get(self.jwks_url)
            if response.status_code == 200:
                _jwks_cache = response.json()
                _jwks_cache_time = now
                return _jwks_cache
            else:
                raise Exception(f"Failed to fetch JWKS: {response.status_code}")
    
    async def get_m2m_token(self) -> str:
        """
        Get Machine-to-Machine access token for API calls
        """
        url = f"https://{self.domain}/oauth/token"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json={
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'audience': self.audience,
                    'grant_type': 'client_credentials'
                },
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('access_token')
            else:
                raise Exception(f"Failed to get M2M token: {response.text}")
    
    async def verify_token(self, token: str) -> Dict:
        """
        Verify an Auth0 JWT token and return the payload
        """
        try:
            # Get JWKS
            jwks = await self.get_jwks()
            
            # Get the unverified header to find the key ID
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get('kid')
            
            # Find the matching key
            rsa_key = None
            for key in jwks.get('keys', []):
                if key.get('kid') == kid:
                    rsa_key = {
                        'kty': key['kty'],
                        'kid': key['kid'],
                        'use': key['use'],
                        'n': key['n'],
                        'e': key['e']
                    }
                    break
            
            if not rsa_key:
                raise JWTError("Unable to find appropriate key")
            
            # Verify and decode the token
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=AUTH0_ALGORITHMS,
                audience=self.audience,
                issuer=self.issuer
            )
            
            return {
                'valid': True,
                'payload': payload,
                'sub': payload.get('sub'),  # User ID
                'email': payload.get('email'),
                'permissions': payload.get('permissions', []),
                'scope': payload.get('scope', '').split()
            }
            
        except ExpiredSignatureError:
            return {
                'valid': False,
                'error': 'Token has expired',
                'error_code': 'token_expired'
            }
        except JWTError as e:
            return {
                'valid': False,
                'error': str(e),
                'error_code': 'invalid_token'
            }
        except Exception as e:
            return {
                'valid': False,
                'error': str(e),
                'error_code': 'verification_error'
            }
    
    async def get_user_info(self, access_token: str) -> Dict:
        """
        Get user profile information from Auth0
        """
        url = f"https://{self.domain}/userinfo"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={'Authorization': f'Bearer {access_token}'}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Failed to get user info: {response.text}")
    
    def is_configured(self) -> bool:
        """Check if Auth0 is properly configured"""
        return all([self.domain, self.client_id, self.client_secret, self.audience])


# Singleton instance
_auth0_service: Optional[Auth0Service] = None


def get_auth0_service() -> Auth0Service:
    """Get or create Auth0 service instance"""
    global _auth0_service
    if _auth0_service is None:
        _auth0_service = Auth0Service()
    return _auth0_service


async def auth0_or_jwt_auth(token: str, db) -> Optional[Dict]:
    """
    Hybrid authentication: Try Auth0 first, fall back to internal JWT
    This allows gradual migration to Auth0 while maintaining compatibility
    """
    auth0_service = get_auth0_service()
    
    # If Auth0 is configured, try Auth0 first
    if auth0_service.is_configured():
        result = await auth0_service.verify_token(token)
        
        if result.get('valid'):
            # Auth0 token is valid
            sub = result.get('sub')  # Auth0 user ID
            email = result.get('email')
            
            # Look up or create user in local database
            user = await db.users.find_one(
                {'$or': [{'auth0_id': sub}, {'email': email}]},
                {'_id': 0}
            )
            
            if user:
                # Update auth0_id if not set
                if not user.get('auth0_id') and sub:
                    await db.users.update_one(
                        {'id': user['id']},
                        {'$set': {'auth0_id': sub}}
                    )
                return user
            else:
                # User not found in local DB - could create auto-provisioned user here
                return None
    
    # Fall back to internal JWT verification
    return None


def get_auth0_login_url(redirect_uri: str, state: str = None) -> str:
    """
    Generate Auth0 login URL for frontend redirect
    """
    auth0_service = get_auth0_service()
    
    params = {
        'response_type': 'code',
        'client_id': auth0_service.client_id,
        'redirect_uri': redirect_uri,
        'scope': 'openid profile email',
        'audience': auth0_service.audience
    }
    
    if state:
        params['state'] = state
    
    query_string = '&'.join(f"{k}={v}" for k, v in params.items())
    return f"https://{auth0_service.domain}/authorize?{query_string}"


async def exchange_code_for_tokens(code: str, redirect_uri: str) -> Dict:
    """
    Exchange authorization code for tokens
    """
    auth0_service = get_auth0_service()
    url = f"https://{auth0_service.domain}/oauth/token"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json={
                'grant_type': 'authorization_code',
                'client_id': auth0_service.client_id,
                'client_secret': auth0_service.client_secret,
                'code': code,
                'redirect_uri': redirect_uri
            },
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Token exchange failed: {response.text}")
