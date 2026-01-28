"""
API module init.
"""
from app.api.routes import api_router
from app.api.deps import (
    get_current_user_id,
    get_current_user_id_optional,
    get_auth_service,
    CurrentUserId,
    CurrentUserIdOptional,
    DbSession,
    AuthServiceDep,
)

__all__ = [
    "api_router",
    "get_current_user_id",
    "get_current_user_id_optional",
    "get_auth_service",
    "CurrentUserId",
    "CurrentUserIdOptional",
    "DbSession",
    "AuthServiceDep",
]
