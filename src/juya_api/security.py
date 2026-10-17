"""Secrets, encrypted personal fields and safe lookup digests."""

import hashlib
import hmac
import json
import secrets

from cryptography.fernet import Fernet

from .config import Settings


def digest(value: str) -> str:
    """Store only one-way digests of high-entropy session tokens."""
    return hashlib.sha256(value.encode()).hexdigest()


def lookup(settings: Settings, purpose: str, value: str) -> str:
    """Separate identity/contact lookup domains without storing raw identifiers."""
    return hmac.new(
        settings.lookup_key.encode(), f"{purpose}:{value}".encode(), hashlib.sha256
    ).hexdigest()


def token(prefix: str) -> str:
    """Generate a role-specific, non-guessable business credential."""
    return prefix + secrets.token_urlsafe(32)


def encrypt(settings: Settings, value: str) -> str:
    """Encrypt a personal field or recoverable credential at rest."""
    return Fernet(settings.field_encryption_key.encode()).encrypt(value.encode()).decode()


def decrypt(settings: Settings, value: str | None) -> str | None:
    """Return only explicitly authorized decrypted field content."""
    return (
        Fernet(settings.field_encryption_key.encode()).decrypt(value.encode()).decode()
        if value
        else None
    )


def fingerprint(value) -> str:
    """Bind an operation key to a canonical request independent of JSON key order."""
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
