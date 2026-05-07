import secrets
import hashlib
from datetime import datetime, timedelta, timezone

INVITE_TTL = timedelta(days=7)
RESET_TTL = timedelta(hours=1)


def generate_token() -> tuple:
    raw = secrets.token_urlsafe(32)
    hashed = hash_token(raw)
    return raw, hashed


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def invite_expiry() -> datetime:
    return datetime.now(timezone.utc) + INVITE_TTL


def reset_expiry() -> datetime:
    return datetime.now(timezone.utc) + RESET_TTL