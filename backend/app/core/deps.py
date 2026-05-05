from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token

bearer = HTTPBearer(auto_error=False)


def _decode_or_401(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing token")
    try:
        return decode_token(credentials.credentials)
    except PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"invalid token: {e}"
        ) from e


def get_current_admin_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> int:
    payload = _decode_or_401(credentials)
    if payload.get("scope") != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="wrong scope")
    try:
        return int(payload["sub"])
    except (KeyError, ValueError, TypeError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid sub") from e


def get_current_admin(
    admin_id: int = Depends(get_current_admin_id),
    db: Session = Depends(get_db),
):
    from app.modules.admin.models import AdminUser

    admin = db.get(AdminUser, admin_id)
    if admin is None or admin.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="admin not found")
    return admin


# ===== C 端 user =====


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> int:
    payload = _decode_or_401(credentials)
    if payload.get("scope") != "user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="wrong scope")
    try:
        return int(payload["sub"])
    except (KeyError, ValueError, TypeError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid sub") from e


def get_current_user(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.modules.user.models import User

    user = db.get(User, user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


def get_current_user_refresh_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    """专门给 /auth/refresh 用，需要 user_refresh scope 的 token"""
    payload = _decode_or_401(credentials)
    if payload.get("scope") != "user_refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="wrong scope")
    return payload
