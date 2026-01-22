"""Application configuration settings"""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

class Settings:
    """Application settings loaded from environment"""
    
    # Database
    MONGO_URL: str = os.environ.get('MONGO_URL', '')
    DB_NAME: str = os.environ.get('DB_NAME', 'taxnfin')
    
    # JWT
    JWT_SECRET: str = os.environ.get('JWT_SECRET', 'taxnfin-secret-key-change-in-production')
    JWT_ALGORITHM: str = 'HS256'
    JWT_EXPIRATION_HOURS: int = 24 * 7  # 1 week
    
    # Belvo (Open Banking)
    BELVO_SECRET_ID: str = os.environ.get('BELVO_SECRET_ID', '')
    BELVO_SECRET_PASSWORD: str = os.environ.get('BELVO_SECRET_PASSWORD', '')
    BELVO_ENV: str = os.environ.get('BELVO_ENV', 'sandbox')
    
    # Banxico API
    BANXICO_TOKEN: str = os.environ.get('BANXICO_TOKEN', '')
    
    # Open Exchange Rates
    OPEN_EXCHANGE_APP_ID: str = os.environ.get('OPEN_EXCHANGE_APP_ID', '')
    
    # Auth0
    AUTH0_DOMAIN: str = os.environ.get('AUTH0_DOMAIN', '')
    AUTH0_CLIENT_ID: str = os.environ.get('AUTH0_CLIENT_ID', '')
    AUTH0_CLIENT_SECRET: str = os.environ.get('AUTH0_CLIENT_SECRET', '')
    AUTH0_AUDIENCE: str = os.environ.get('AUTH0_AUDIENCE', '')

settings = Settings()
