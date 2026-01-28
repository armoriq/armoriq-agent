"""
Authentication routes.
Handles JWT login/register and Google OAuth.
"""
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.config import APIRoutes, settings
from app.api.deps import AuthServiceDep, CurrentUserId, DbSession
from app.models import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenPair,
    TokenRefresh,
)
from app.services.auth_service import AuthService


router = APIRouter(prefix=APIRoutes.AUTH_PREFIX, tags=["Authentication"])


@router.post(APIRoutes.AUTH_REGISTER, response_model=TokenPair)
async def register(
    data: UserCreate,
    auth_service: AuthServiceDep,
):
    """
    Register a new user with email and password.

    Returns JWT token pair (access + refresh tokens).
    """
    try:
        return await auth_service.register(
            email=data.email,
            password=data.password,
            name=data.name,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(APIRoutes.AUTH_LOGIN, response_model=TokenPair)
async def login(
    data: UserLogin,
    auth_service: AuthServiceDep,
):
    """
    Login with email and password.

    Returns JWT token pair (access + refresh tokens).
    """
    try:
        return await auth_service.login(
            email=data.email,
            password=data.password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.post(APIRoutes.AUTH_REFRESH, response_model=TokenPair)
async def refresh_tokens(
    data: TokenRefresh,
    auth_service: AuthServiceDep,
):
    """
    Refresh access token using refresh token.

    Returns new JWT token pair.
    """
    try:
        return await auth_service.refresh_tokens(data.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.get(APIRoutes.AUTH_ME, response_model=UserResponse)
async def get_current_user(
    user_id: CurrentUserId,
    auth_service: AuthServiceDep,
):
    """
    Get current authenticated user's profile.
    """
    user = await auth_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


# =============================================================================
# GOOGLE OAUTH
# =============================================================================
@router.get(APIRoutes.AUTH_GOOGLE)
async def google_auth(
    auth_service: AuthServiceDep,
    redirect_uri: str = Query(
        default=None,
        description="Redirect URI after authentication",
    ),
):
    """
    Initiate Google OAuth flow.

    Redirects to Google's consent page.
    """
    # Default redirect URI
    if not redirect_uri:
        redirect_uri = f"{settings.backend_url}{APIRoutes.PREFIX}{APIRoutes.AUTH_PREFIX}{APIRoutes.AUTH_GOOGLE_CALLBACK}"

    try:
        auth_url = auth_service.get_google_auth_url(redirect_uri)
        return {"auth_url": auth_url}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(APIRoutes.AUTH_GOOGLE_CALLBACK)
async def google_callback(
    code: str,
    auth_service: AuthServiceDep,
    redirect_uri: str = Query(
        default=None,
        description="The redirect URI used in the auth request",
    ),
):
    """
    Handle Google OAuth callback.

    Exchanges auth code for tokens and creates/updates user.
    Returns JWT token pair.
    """
    # Default redirect URI
    if not redirect_uri:
        redirect_uri = f"{settings.backend_url}{APIRoutes.PREFIX}{APIRoutes.AUTH_PREFIX}{APIRoutes.AUTH_GOOGLE_CALLBACK}"

    try:
        tokens = await auth_service.handle_google_callback(code, redirect_uri)

        # For API usage, return tokens directly
        # For web app, you might want to redirect with tokens
        return tokens

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(APIRoutes.AUTH_LOGOUT)
async def logout(user_id: CurrentUserId):
    """
    Logout user.

    Note: With JWT, logout is client-side (delete tokens).
    This endpoint is for logging/analytics purposes.
    """
    # In a more sophisticated setup, you might:
    # - Add token to blacklist
    # - Clear server-side sessions
    # For now, just acknowledge the logout
    return {"message": "Logged out successfully"}
