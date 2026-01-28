"""
Simple encryption utilities for storing sensitive data like API keys.
Uses Fernet symmetric encryption from the cryptography library.
"""
import os
import base64
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import settings


def _get_encryption_key() -> bytes:
    """
    Derive an encryption key from the JWT secret.

    Uses PBKDF2 to derive a Fernet-compatible key from the JWT secret.
    This ensures we don't need a separate encryption key in the environment.
    """
    # Use JWT secret as the base for key derivation
    secret = settings.jwt_secret.get_secret_value().encode()

    # Use a fixed salt (in production, you might want a per-user salt)
    salt = b"armoriq_agent_salt_v1"

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret))
    return key


def encrypt_api_key(api_key: str) -> bytes:
    """
    Encrypt an API key for storage in the database.

    Args:
        api_key: The plaintext API key to encrypt

    Returns:
        Encrypted bytes suitable for storage in LargeBinary column
    """
    key = _get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(api_key.encode())
    return encrypted


def decrypt_api_key(encrypted_data: bytes) -> str:
    """
    Decrypt an API key from the database.

    Args:
        encrypted_data: The encrypted bytes from the database

    Returns:
        The decrypted API key string
    """
    key = _get_encryption_key()
    f = Fernet(key)
    decrypted = f.decrypt(encrypted_data)
    return decrypted.decode()


def hash_password(password: str) -> str:
    """
    Hash a password for storage using bcrypt.

    Args:
        password: The plaintext password

    Returns:
        The hashed password string
    """
    import bcrypt
    # Encode password and generate salt
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against a stored hash.

    Args:
        password: The plaintext password to verify
        hashed: The stored password hash

    Returns:
        True if the password matches, False otherwise
    """
    import bcrypt
    password_bytes = password.encode('utf-8')
    hashed_bytes = hashed.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)
