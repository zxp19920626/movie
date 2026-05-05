from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _make_token(
    sub: str,
    scope: str,
    minutes: int,
    extra: dict[str, Any] | None = None,
    jti: str | None = None,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "scope": scope,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
        "jti": jti or uuid4().hex,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# ===== Admin tokens =====


def make_access_token(admin_user_id: int) -> str:
    return _make_token(str(admin_user_id), scope="admin", minutes=settings.access_token_minutes)


def make_refresh_token(admin_user_id: int) -> str:
    return _make_token(
        str(admin_user_id), scope="admin_refresh", minutes=settings.refresh_token_days * 24 * 60
    )


# ===== User tokens =====


def make_user_access_token(user_id: int, app_id: int | None = None) -> str:
    extra = {"app_id": app_id} if app_id else None
    return _make_token(
        str(user_id), scope="user", minutes=settings.user_access_token_minutes, extra=extra
    )


def make_user_refresh_token(user_id: int, jti: str) -> str:
    return _make_token(
        str(user_id),
        scope="user_refresh",
        minutes=settings.user_refresh_token_days * 24 * 60,
        jti=jti,
    )


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def new_jti() -> str:
    return uuid4().hex
