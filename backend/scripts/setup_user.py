"""
Script to create initial user and add OpenAI API key.
Run with: uv run python scripts/setup_user.py
"""
import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Add the app to the path
import sys
sys.path.insert(0, "/media/ssd2/kaam-kaaz/armoriq/armoriq-agent/backend")

from app.config import settings
from app.utils.encryption import encrypt_api_key, hash_password
from app.models.database import Base, User, UserLLMConfig


async def create_user_and_api_key():
    """Create the initial user and add OpenAI API key."""

    # Create async engine
    engine = create_async_engine(settings.database_url, echo=True)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check if user already exists
        result = await session.execute(
            select(User).where(User.email == "aniket@armoriq.io")
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print(f"User aniket@armoriq.io already exists with ID: {existing_user.id}")
            user_id = existing_user.id
        else:
            # Create user
            user = User(
                id=uuid.uuid4(),
                email="aniket@armoriq.io",
                password_hash=hash_password("armoriq@005"),
                name="Aniket",
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(user)
            await session.flush()
            user_id = user.id
            print(f"Created user aniket@armoriq.io with ID: {user_id}")

        # Check if OpenAI config already exists
        result = await session.execute(
            select(UserLLMConfig).where(
                UserLLMConfig.user_id == user_id,
                UserLLMConfig.provider == "openai"
            )
        )
        existing_config = result.scalar_one_or_none()

        if existing_config:
            print(f"OpenAI config already exists for user")
        else:
            # OpenAI API key
            openai_key = "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"

            # Encrypt the API key
            encrypted_key = encrypt_api_key(openai_key)

            # Create LLM config
            llm_config = UserLLMConfig(
                id=uuid.uuid4(),
                user_id=user_id,
                provider="openai",
                api_key_encrypted=encrypted_key,
                is_default=True,
                settings={"temperature": 0.7, "max_tokens": 4096},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(llm_config)
            print(f"Added OpenAI API key for user")

        await session.commit()
        print("Setup completed successfully!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_user_and_api_key())
