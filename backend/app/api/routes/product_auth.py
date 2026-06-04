"""
Product-level auth routes at bare /auth/* paths.

The tools-frontend calls /auth/login, /auth/me, /auth/refresh, /auth/google/start
without any /api/v1 prefix. This router mounts at root so those paths work.

Delegates to the same AuthService used by the existing /api/v1/auth/* routes.
"""
import base64
from urllib.parse import urlencode, urljoin

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.config import settings
from app.api.deps import AuthServiceDep, CurrentUserId, DbSession
from app.models import UserLogin, TokenRefresh, UserCreate

router = APIRouter(prefix="/auth", tags=["Product Auth"])

# Clean callback URL registered in Google Cloud Console — no query params.
_GOOGLE_CALLBACK = f"{settings.backend_url}/auth/google/callback"


@router.post("/login")
async def login(data: UserLogin, auth_service: AuthServiceDep):
    try:
        tokens = await auth_service.login(email=data.email, password=data.password)
        return {
            "success": True,
            "data": {
                "accessToken": tokens.access_token,
                "refreshToken": tokens.refresh_token,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/register")
async def register(data: UserCreate, auth_service: AuthServiceDep):
    try:
        tokens = await auth_service.register(email=data.email, password=data.password, name=data.name)
        return {
            "success": True,
            "data": {
                "accessToken": tokens.access_token,
                "refreshToken": tokens.refresh_token,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/refresh")
async def refresh(data: TokenRefresh, auth_service: AuthServiceDep):
    try:
        tokens = await auth_service.refresh_tokens(data.refresh_token)
        return {
            "success": True,
            "data": {
                "accessToken": tokens.access_token,
                "refreshToken": tokens.refresh_token,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get("/me")
async def me(user_id: CurrentUserId, auth_service: AuthServiceDep):
    user = await auth_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {
        "success": True,
        "data": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "avatar_url": user.avatar_url,
            "organizations": [],  # armoriq-agent has no org model yet
        },
    }


@router.get("/google/start")
async def google_start(
    auth_service: AuthServiceDep,
    redirect: str = Query(..., description="Frontend callback URL (URL-encoded)"),
):
    """
    Kick off Google OAuth. Passes frontend redirect URL as base64 state so the
    registered redirect_uri stays clean (no query params) — required by Google.
    """
    state = base64.urlsafe_b64encode(redirect.encode()).decode()
    try:
        auth_url = auth_service.get_google_auth_url(_GOOGLE_CALLBACK, state=state)
        return RedirectResponse(url=auth_url, status_code=302)
    except (ValueError, TypeError):
        error_url = f"{redirect}?error=oauth_not_configured"
        return RedirectResponse(url=error_url, status_code=302)


@router.get("/google/callback")
async def google_callback(
    code: str,
    auth_service: AuthServiceDep,
    state: str = Query(""),
):
    """
    Google OAuth callback. Exchange code → tokens, then redirect to frontend.
    Recovers frontend_redirect from base64 state parameter.
    """
    try:
        frontend_redirect = base64.urlsafe_b64decode(state.encode()).decode()
    except Exception:
        frontend_redirect = "http://localhost:5174"

    try:
        tokens = await auth_service.handle_google_callback(code, _GOOGLE_CALLBACK)
        sep = "&" if "?" in frontend_redirect else "?"
        dest = f"{frontend_redirect}{sep}token={tokens.access_token}&refreshToken={tokens.refresh_token}"
        return RedirectResponse(url=dest, status_code=302)
    except Exception:
        error_url = f"{frontend_redirect}?error=oauth_failed"
        return RedirectResponse(url=error_url, status_code=302)


@router.get("/github/start")
async def github_start(redirect: str = Query(...)):
    """GitHub OAuth stub — not yet implemented. Returns error to frontend."""
    sep = "&" if "?" in redirect else "?"
    return RedirectResponse(url=f"{redirect}{sep}error=github_not_configured", status_code=302)
