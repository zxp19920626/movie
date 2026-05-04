from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.core.security import (
    make_access_token,
    make_refresh_token,
    verify_password,
)
from app.modules.admin.models import AdminUser
from app.modules.admin.schemas import (
    AdminUserOut,
    LoginRequest,
    LoginResponse,
)

router = APIRouter()


@router.post("/auth/login", response_model=LoginResponse)
def admin_login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    stmt = select(AdminUser).where(AdminUser.email == payload.email.lower())
    admin = db.scalars(stmt).one_or_none()
    if admin is None or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误"
        )
    if admin.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="账号已禁用"
        )
    admin.last_login_at = datetime.now(UTC)
    db.commit()

    return LoginResponse(
        access_token=make_access_token(admin.id),
        refresh_token=make_refresh_token(admin.id),
        user=AdminUserOut(**admin.to_public()),
    )


@router.get("/auth/me", response_model=AdminUserOut)
def admin_me(admin: AdminUser = Depends(get_current_admin)) -> AdminUserOut:
    return AdminUserOut(**admin.to_public())
