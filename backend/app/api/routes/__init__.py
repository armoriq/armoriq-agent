"""
API routes module init.
"""
from fastapi import APIRouter

from app.api.routes import auth, llm, mcp, chat, plans


# Main API router
api_router = APIRouter()

# Include route modules
api_router.include_router(auth.router)
api_router.include_router(llm.router)
api_router.include_router(mcp.router)
api_router.include_router(chat.router)
api_router.include_router(plans.router)
