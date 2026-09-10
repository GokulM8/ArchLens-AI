"""Authentication utilities."""

import hashlib
import secrets


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password


def hash_password(password: str) -> str:
    """Hash a password."""
    return hashlib.sha256(password.encode()).hexdigest()


def create_token(user_id: int, secret: str) -> str:
    """Create an authentication token."""
    data = f"{user_id}:{secret}"
    return hashlib.sha256(data.encode()).hexdigest()