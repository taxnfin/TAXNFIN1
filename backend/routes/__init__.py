# Routes module - API endpoints organized by domain
# NOTE: During refactoring, routes are being migrated gradually from server.py
# The main api_router in server.py still handles most routes

from fastapi import APIRouter

# For now, we expose individual routers that can be imported
# In the future, they will be combined into a single api_router

__all__ = []

