"""
LLM configuration routes.
Manages user's LLM provider API keys and settings.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from cryptography.fernet import Fernet

from app.config import APIRoutes, settings, PROVIDER_MODELS, ErrorMessages
from app.api.deps import CurrentUserId, DbSession
from app.models import (
    UserLLMConfig,
    LLMConfigCreate,
    LLMConfigUpdate,
    LLMConfigResponse,
    LLMProviderInfo,
    LLMProvidersResponse,
)
from app.services.llm_router import LLMRouter
from app.services.openrouter_client import OpenRouterClient


router = APIRouter(prefix=APIRoutes.LLM_PREFIX, tags=["LLM Configuration"])


# Simple encryption for API keys (use proper key management in production)
# In production, use AWS KMS, Google Cloud KMS, or HashiCorp Vault
def get_encryption_key() -> bytes:
    """Get or derive encryption key from JWT secret."""
    # Derive a Fernet-compatible key from JWT secret
    import hashlib
    import base64
    key = hashlib.sha256(settings.jwt_secret.get_secret_value().encode()).digest()
    return base64.urlsafe_b64encode(key)


def encrypt_api_key(api_key: str) -> bytes:
    """Encrypt an API key."""
    f = Fernet(get_encryption_key())
    return f.encrypt(api_key.encode())


def decrypt_api_key(encrypted: bytes) -> str:
    """Decrypt an API key."""
    f = Fernet(get_encryption_key())
    return f.decrypt(encrypted).decode()


@router.get(APIRoutes.LLM_PROVIDERS, response_model=LLMProvidersResponse)
async def get_providers(
    user_id: CurrentUserId,
    db: DbSession,
):
    """
    Get all available LLM providers and their models.

    Also indicates which providers the user has configured.
    """
    # Get user's configured providers
    result = await db.execute(
        select(UserLLMConfig.provider).where(UserLLMConfig.user_id == user_id)
    )
    configured_providers = {row[0] for row in result.fetchall()}

    # Build provider list
    providers = []

    # Add direct providers
    provider_names = {
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "google": "Google AI",
        "mistral": "Mistral AI",
        "ollama": "Ollama (Local)",
        "openrouter": "OpenRouter",
    }

    for provider_id, models in PROVIDER_MODELS.items():
        providers.append(
            LLMProviderInfo(
                id=provider_id,
                name=provider_names.get(provider_id, provider_id.title()),
                models=models,
                configured=provider_id in configured_providers,
            )
        )

    return LLMProvidersResponse(providers=providers)


@router.get(APIRoutes.LLM_CONFIG_LIST, response_model=list[LLMConfigResponse])
async def list_llm_configs(
    user_id: CurrentUserId,
    db: DbSession,
):
    """Get all LLM configurations for current user."""
    result = await db.execute(
        select(UserLLMConfig)
        .where(UserLLMConfig.user_id == user_id)
        .order_by(UserLLMConfig.created_at.desc())
    )
    configs = result.scalars().all()
    return configs


@router.post(APIRoutes.LLM_CONFIG, response_model=LLMConfigResponse)
async def add_llm_config(
    data: LLMConfigCreate,
    user_id: CurrentUserId,
    db: DbSession,
):
    """
    Add or update LLM provider configuration.

    Validates the API key by making a test call before saving.
    """
    # Validate provider
    if data.provider not in PROVIDER_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorMessages.LLM_PROVIDER_INVALID,
        )

    # Skip validation for Ollama (no API key needed)
    if data.provider != "ollama":
        # Validate API key by making a test call
        try:
            model = PROVIDER_MODELS[data.provider][0]  # Use first model
            llm = LLMRouter.get_llm(
                provider=data.provider,
                model=model,
                api_key=data.api_key,
                streaming=False,
            )
            # Quick test call
            await llm.ainvoke([{"role": "user", "content": "test"}])
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{ErrorMessages.LLM_API_KEY_INVALID}: {str(e)}",
            )

    # Check if config already exists for this provider
    result = await db.execute(
        select(UserLLMConfig)
        .where(
            UserLLMConfig.user_id == user_id,
            UserLLMConfig.provider == data.provider,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing
        existing.api_key_encrypted = encrypt_api_key(data.api_key)
        existing.settings = data.settings
        if data.is_default:
            # Clear other defaults
            await db.execute(
                update(UserLLMConfig)
                .where(UserLLMConfig.user_id == user_id)
                .values(is_default=False)
            )
            existing.is_default = True
        await db.flush()
        await db.refresh(existing)
        return existing

    # Create new config
    if data.is_default:
        # Clear other defaults
        await db.execute(
            update(UserLLMConfig)
            .where(UserLLMConfig.user_id == user_id)
            .values(is_default=False)
        )

    config = UserLLMConfig(
        user_id=user_id,
        provider=data.provider,
        api_key_encrypted=encrypt_api_key(data.api_key),
        is_default=data.is_default,
        settings=data.settings,
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)
    return config


@router.delete(APIRoutes.LLM_CONFIG_DELETE)
async def delete_llm_config(
    config_id: UUID,
    user_id: CurrentUserId,
    db: DbSession,
):
    """Delete an LLM provider configuration."""
    result = await db.execute(
        delete(UserLLMConfig)
        .where(
            UserLLMConfig.id == config_id,
            UserLLMConfig.user_id == user_id,
        )
        .returning(UserLLMConfig.id)
    )
    deleted = result.scalar_one_or_none()

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorMessages.LLM_CONFIG_NOT_FOUND,
        )

    return {"message": "Configuration deleted"}


# Helper function for other services
async def get_user_api_key(
    db: AsyncSession,
    user_id: str,
    provider: str,
) -> Optional[str]:
    """Get decrypted API key for a provider."""
    result = await db.execute(
        select(UserLLMConfig)
        .where(
            UserLLMConfig.user_id == user_id,
            UserLLMConfig.provider == provider,
        )
    )
    config = result.scalar_one_or_none()

    if not config:
        return None

    return decrypt_api_key(config.api_key_encrypted)
