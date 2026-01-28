"""
Pydantic Settings for the application.
Loads configuration from environment variables.
"""
from functools import lru_cache
from typing import Optional

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: str = "development"

    # App
    app_name: str = "ArmorIQ Agent"
    app_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    # Database
    database_url: str = "postgresql+asyncpg://armoriq:armoriq@localhost:5432/armoriq_agent"

    # JWT
    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"

    # Google OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[SecretStr] = None

    # ArmorIQ
    armoriq_api_key: Optional[SecretStr] = None
    armoriq_proxy_url: str = "https://customer-proxy.armoriq.ai"
    armoriq_backend_url: str = "https://customer-api.armoriq.ai"

    # OpenRouter (optional)
    openrouter_api_key: Optional[SecretStr] = None

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
