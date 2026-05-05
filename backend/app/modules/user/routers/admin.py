"""user 资源 — 后台管理路由 /api/v1/admin/users/...

放 user 模块下的考虑：管理 user 资源的逻辑跟 user model 相关；admin 模块只管 admin 自己的资源。
路径 /admin/users/... 只是 URL 约定，代码归属仍是 user 模块。
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.modules.admin.models import AdminUser
from app.modules.user.models import User, UserDevice

router = APIRouter()


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    uuid: str
    email: str | None
    phone: str | None
    country_code: str | None
    display_name: str
    avatar_url: str | None
    status: str
    country: str | None
    preferred_language: str
    app_id: int | None
    registered_at: datetime | None
    last_active_at: datetime | None


class AdminUserListOut(BaseModel):
    items: list[AdminUserOut]
    total: int


class AdminUserDeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    device_id: str
    app_id: int | None
    platform: str
    app_version: str | None
    channel: str | None
    country: str | None
    last_seen_at: datetime


class AdminUserDetailOut(AdminUserOut):
    devices: list[AdminUserDeviceOut]


class AdminUserUpdateRequest(BaseModel):
    display_name: str | None = None
    status: str | None = None  # active / suspended / deleted
    preferred_language: str | None = None
    country: str | None = None


@router.get("/users", response_model=AdminUserListOut)
def list_users(
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
    search: str | None = Query(None, description="match email/phone/display_name"),
    status_filter: str | None = Query(None, alias="status"),
    app_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> AdminUserListOut:
    stmt = select(User)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(User.email.ilike(like), User.phone.ilike(like), User.display_name.ilike(like))
        )
    if status_filter:
        stmt = stmt.where(User.status == status_filter)
    if app_id is not None:
        stmt = stmt.where(User.app_id == app_id)
    total = len(list(db.scalars(stmt).all()))
    rows = list(db.scalars(stmt.order_by(User.id.desc()).limit(limit).offset(offset)).all())
    return AdminUserListOut(items=[AdminUserOut.model_validate(u) for u in rows], total=total)


@router.get("/users/{user_id}", response_model=AdminUserDetailOut)
def get_user(
    user_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
) -> AdminUserDetailOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    devices = list(
        db.scalars(
            select(UserDevice)
            .where(UserDevice.user_id == user_id)
            .order_by(UserDevice.last_seen_at.desc())
        ).all()
    )
    user_dict = {c.name: getattr(user, c.name) for c in user.__table__.columns}
    return AdminUserDetailOut(
        **user_dict,
        devices=[AdminUserDeviceOut.model_validate(d) for d in devices],
    )


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    payload: AdminUserUpdateRequest,
    user_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
) -> AdminUserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    if payload.status is not None:
        if payload.status not in ("active", "suspended", "deleted"):
            raise HTTPException(400, "invalid status")
        user.status = payload.status
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.preferred_language is not None:
        user.preferred_language = payload.preferred_language
    if payload.country is not None:
        user.country = payload.country
    db.commit()
    db.refresh(user)
    return AdminUserOut.model_validate(user)
