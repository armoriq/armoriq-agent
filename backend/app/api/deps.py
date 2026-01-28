"""
FastAPI dependencies for dependency injection.
"""
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ErrorMessages
from app.db import get_db
from app.services.auth_service import AuthService


# Security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials],
        Depends(security)
    ],
) -> str:
    """
    Dependency to get current user ID from JWT token.

    Usage:
        @router.get("/")
        async def endpoint(user_id: str = Depends(get_current_user_id)):
            ...
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = AuthService.verify_token(credentials.credentials, token_type="access")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorMessages.TOKEN_INVALID,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id


async def get_current_user_id_optional(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials],
        Depends(security)
    ],
) -> Optional[str]:
    """
    Dependency to get current user ID if token provided, None otherwise.
    Useful for endpoints that work both authenticated and unauthenticated.
    """
    if not credentials:
        return None

    return AuthService.verify_token(credentials.credentials, token_type="access")


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """Get AuthService instance with database session."""
    return AuthService(db)


# Type aliases for cleaner dependency injection
CurrentUserId = Annotated[str, Depends(get_current_user_id)]
CurrentUserIdOptional = Annotated[Optional[str], Depends(get_current_user_id_optional)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
