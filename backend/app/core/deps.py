from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_admin_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> int:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing token")
    try:
        payload = decode_token(credentials.credentials)
    except PyJWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"invalid token: {e}")
    if payload.get("scope") != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="wrong scope")
    try:
        return int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid sub")


def get_current_admin(
    admin_id: int = Depends(get_current_admin_id),
    db: Session = Depends(get_db),
):
    # 延迟 import 避免循环依赖
    from app.modules.admin.models import AdminUser

    admin = db.get(AdminUser, admin_id)
    if admin is None or admin.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="admin not found")
    return admin
