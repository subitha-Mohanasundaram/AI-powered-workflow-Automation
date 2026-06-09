"""
Encryption Service — AES-128 Fernet encryption for confidential user data.

All sensitive fields (API keys, SMTP passwords, personal details, custom headers)
are encrypted before storing in the database and decrypted only when needed.

The encryption key is derived from the SECRET_KEY environment variable.
If not set, a per-process key is generated (data is lost on restart — set SECRET_KEY in .env for persistence).
"""
import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from ..logging_config import get_logger

logger = get_logger(__name__)

_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        secret = os.environ.get("SECRET_KEY", "")
        if secret:
            # Derive a 32-byte key from the secret using SHA-256
            key_bytes = hashlib.sha256(secret.encode()).digest()
            key = base64.urlsafe_b64encode(key_bytes)
        else:
            # Generate a random key (non-persistent — only for development)
            key = Fernet.generate_key()
            logger.warning(
                "SECRET_KEY not set — using random encryption key. "
                "Encrypted data will be lost on restart. Set SECRET_KEY in .env for production."
            )
        _fernet = Fernet(key)
    return _fernet


def encrypt(plaintext: str) -> str:
    """Encrypt a string. Returns a base64-encoded ciphertext string."""
    if not plaintext:
        return ""
    try:
        return _get_fernet().encrypt(plaintext.encode()).decode()
    except Exception as exc:
        logger.error("Encryption failed | error=%s", exc)
        raise


def decrypt(ciphertext: str) -> str:
    """Decrypt a previously encrypted string. Returns plaintext."""
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.error("Decryption failed — invalid token or wrong key")
        return "[DECRYPTION_FAILED]"
    except Exception as exc:
        logger.error("Decryption error | error=%s", exc)
        return "[DECRYPTION_ERROR]"


def mask(value: str) -> str:
    """Return a masked version for display — shows first 4 and last 2 chars."""
    if not value or len(value) < 8:
        return "****"
    return f"{value[:4]}{'*' * (len(value) - 6)}{value[-2:]}"
