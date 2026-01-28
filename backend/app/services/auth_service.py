"""
Authentication service.
Handles JWT tokens and Google OAuth.
"""
import bcrypt
from datetime import datetime, timedelta
from typing import Optional

from httpx import AsyncClient
from jose import jwt, JWTError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings, ExternalURLs, Timeouts, ErrorMessages
from app.models import User, TokenPair


class GoogleUserInfo(BaseModel):
    """Google OAuth user info."""

    id: str
    email: str
    name: str
    picture: Optional[str] = None


class AuthService:
    """
    Handles authentication:
    - Password hashing/verification
    - JWT token creation/verification
    - Google OAuth flow
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # -------------------------------------------------------------------------
    # PASSWORD HASHING
    # -------------------------------------------------------------------------
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        """Verify a password against its hash."""
        try:
            plain_bytes = plain.encode('utf-8')
            hashed_bytes = hashed.encode('utf-8')
            return bcrypt.checkpw(plain_bytes, hashed_bytes)
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # JWT TOKEN MANAGEMENT
    # -------------------------------------------------------------------------
    @staticmethod
    def create_access_token(user_id: str) -> str:
        """Create a JWT access token."""
        expire = datetime.utcnow() + timedelta(
            minutes=Timeouts.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
        payload = {
            "sub": user_id,
            "exp": expire,
            "type": "access",
            "iat": datetime.utcnow(),
        }
        return jwt.encode(
            payload,
            settings.jwt_secret.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )

    @staticmethod
    def create_refresh_token(user_id: str) -> str:
        """Create a JWT refresh token."""
        expire = datetime.utcnow() + timedelta(
            days=Timeouts.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        payload = {
            "sub": user_id,
            "exp": expire,
            "type": "refresh",
            "iat": datetime.utcnow(),
        }
        return jwt.encode(
            payload,
            settings.jwt_secret.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )

    @staticmethod
    def create_token_pair(user_id: str) -> TokenPair:
        """Create access and refresh token pair."""
        return TokenPair(
            access_token=AuthService.create_access_token(user_id),
            refresh_token=AuthService.create_refresh_token(user_id),
        )

    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[str]:
        """
        Verify a JWT token and return user_id if valid.

        Args:
            token: The JWT token to verify
            token_type: Expected token type ("access" or "refresh")

        Returns:
            User ID if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret.get_secret_value(),
                algorithms=[settings.jwt_algorithm],
            )
            if payload.get("type") != token_type:
                return None
            return payload.get("sub")
        except JWTError:
            return None

    # -------------------------------------------------------------------------
    # USER OPERATIONS
    # -------------------------------------------------------------------------
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        """Get user by Google ID."""
        result = await self.db.execute(
            select(User).where(User.google_id == google_id)
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        email: str,
        name: str,
        password_hash: Optional[str] = None,
        google_id: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> User:
        """Create a new user."""
        user = User(
            email=email,
            name=name,
            password_hash=password_hash,
            google_id=google_id,
            avatar_url=avatar_url,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update_user_google_id(self, user_id: str, google_id: str) -> None:
        """Link Google account to existing user."""
        user = await self.get_user_by_id(user_id)
        if user:
            user.google_id = google_id
            await self.db.flush()

    # -------------------------------------------------------------------------
    # EMAIL/PASSWORD AUTH
    # -------------------------------------------------------------------------
    async def register(
        self,
        email: str,
        password: str,
        name: str,
    ) -> TokenPair:
        """Register a new user with email/password."""
        # Check if user exists
        existing = await self.get_user_by_email(email)
        if existing:
            raise ValueError(ErrorMessages.EMAIL_ALREADY_EXISTS)

        # Create user
        user = await self.create_user(
            email=email,
            name=name,
            password_hash=self.hash_password(password),
        )

        return self.create_token_pair(str(user.id))

    async def login(self, email: str, password: str) -> TokenPair:
        """Login with email/password."""
        user = await self.get_user_by_email(email)

        if not user:
            raise ValueError(ErrorMessages.INVALID_CREDENTIALS)

        if not user.password_hash:
            # User registered with OAuth only
            raise ValueError(ErrorMessages.INVALID_CREDENTIALS)

        if not self.verify_password(password, user.password_hash):
            raise ValueError(ErrorMessages.INVALID_CREDENTIALS)

        return self.create_token_pair(str(user.id))

    async def refresh_tokens(self, refresh_token: str) -> TokenPair:
        """Refresh access token using refresh token."""
        user_id = self.verify_token(refresh_token, token_type="refresh")

        if not user_id:
            raise ValueError(ErrorMessages.TOKEN_INVALID)

        # Verify user still exists
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError(ErrorMessages.USER_NOT_FOUND)

        return self.create_token_pair(user_id)

    # -------------------------------------------------------------------------
    # GOOGLE OAUTH
    # -------------------------------------------------------------------------
    def get_google_auth_url(self, redirect_uri: str) -> str:
        """Generate Google OAuth authorization URL."""
        if not settings.google_client_id:
            raise ValueError("Google OAuth not configured")

        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{ExternalURLs.GOOGLE_AUTH_URL}?{query}"

    async def handle_google_callback(
        self,
        code: str,
        redirect_uri: str,
    ) -> TokenPair:
        """
        Exchange Google auth code for tokens and get/create user.

        Args:
            code: Authorization code from Google
            redirect_uri: The redirect URI used in the auth request

        Returns:
            JWT token pair for the user
        """
        if not settings.google_client_id or not settings.google_client_secret:
            raise ValueError("Google OAuth not configured")

        async with AsyncClient() as client:
            # Exchange code for tokens
            token_response = await client.post(
                ExternalURLs.GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret.get_secret_value(),
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )

            if token_response.status_code != 200:
                raise ValueError("Failed to exchange code for tokens")

            token_data = token_response.json()

            # Get user info from Google
            userinfo_response = await client.get(
                ExternalURLs.GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
            )

            if userinfo_response.status_code != 200:
                raise ValueError("Failed to get user info from Google")

            userinfo = GoogleUserInfo(**userinfo_response.json())

        # Find or create user
        user = await self.get_user_by_google_id(userinfo.id)

        if not user:
            # Check if user exists with same email
            user = await self.get_user_by_email(userinfo.email)

            if user:
                # Link Google account to existing user
                await self.update_user_google_id(str(user.id), userinfo.id)
            else:
                # Create new user
                user = await self.create_user(
                    email=userinfo.email,
                    name=userinfo.name,
                    google_id=userinfo.id,
                    avatar_url=userinfo.picture,
                )

        return self.create_token_pair(str(user.id))
