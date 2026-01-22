"""Database connection and client"""
from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings

# MongoDB client and database
client = AsyncIOMotorClient(settings.MONGO_URL)
db = client[settings.DB_NAME]
