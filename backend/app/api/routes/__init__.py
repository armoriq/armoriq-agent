"""
API routes module init.
"""
from fastapi import APIRouter

from app.api.routes import auth, llm, mcp, chat, plans
from app.api.routes import iap, dashboard, api_keys, agents, policies, product_auth


# Main chatbot API router (mounted at /api/v1)
api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(llm.router)
api_router.include_router(mcp.router)
api_router.include_router(chat.router)
api_router.include_router(plans.router)

__all__ = [
    "api_router",
    "iap", "dashboard", "api_keys", "agents", "policies", "product_auth",
]
