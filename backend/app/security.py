"""Password hashing (Argon2id), JWT sessions, TOTP 2FA, and agent API tokens."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .config import settings

_ph = PasswordHasher()  # Argon2id defaults
API_TOKEN_PREFIX = "mnem_"


# ---- passwords ----
def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def needs_rehash(hashed: str) -> bool:
    try:
        return _ph.check_needs_rehash(hashed)
    except Exception:
        return False


# ---- JWT session ----
def create_access_token(subject: str, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "typ": "session",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.PyJWTError:
        return None


# ---- TOTP 2FA ----
def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, account: str, issuer: str = "Mnemosyne") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)


# ---- agent API tokens ----
def generate_api_token() -> tuple[str, str, str]:
    """Return (full_token, prefix, sha256_hash). Full token is shown once."""
    raw = secrets.token_urlsafe(32)
    full = f"{API_TOKEN_PREFIX}{raw}"
    return full, full[: len(API_TOKEN_PREFIX) + 8], hash_api_token(full)


def hash_api_token(full_token: str) -> str:
    return hashlib.sha256(full_token.encode()).hexdigest()
