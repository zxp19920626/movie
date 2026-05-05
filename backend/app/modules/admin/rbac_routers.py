"""RBAC 后台 — roles + admin-users 管理（P3.14c）。

挂在 /api/v1/admin/rbac/* 下，只允许 super_admin 操作（permission "permissions.edit"）。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.core.security import hash_password
from app.modules.admin.models import AdminRole, AdminUser
from app.modules.admin.permissions import (
    PERMISSION_TREE,
    SEED_ROLES,
    all_permission_codes,
)

router = APIRouter()


def _require_super_admin(admin: AdminUser):
    if not (admin.role and admin.role.is_super_admin):
        # 给非 super_admin 留个口：只要拥有 permissions.edit 也允许
        if "permissions.edit" not in (admin.role.permissions if admin.role else []):
            raise HTTPException(403, "需要 super_admin 或 permissions.edit 权限")


# ===== Schemas =====


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    is_super_admin: bool
    is_builtin: bool
    permissions: list[str]
    created_at: datetime


class RoleCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=128)
    permissions: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = None
    permissions: list[str] | None = None


class RoleListOut(BaseModel):
    items: list[RoleOut]
    total: int


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    display_name: str
    role_id: int
    role_code: str
    role_name: str
    is_super_admin: bool
    app_scope: list[str]
    status: str
    last_login_at: datetime | None
    created_at: datetime


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = ""
    role_id: int
    app_scope: list[str] = Field(default_factory=list)


class AdminUserUpdate(BaseModel):
    display_name: str | None = None
    role_id: int | None = None
    app_scope: list[str] | None = None
    status: str | None = None  # active / suspended
    password: str | None = Field(default=None, min_length=8, max_length=128)


class AdminUserListOut(BaseModel):
    items: list[AdminUserOut]
    total: int


# ===== Permission tree =====


@router.get("/permissions/tree")
def get_permission_tree(
    _admin: AdminUser = Depends(get_current_admin),
) -> dict[str, object]:
    return {
        "tree": PERMISSION_TREE,
        "all_codes": all_permission_codes(),
        "seed_roles": list(SEED_ROLES.keys()),
    }


# ===== Roles =====


@router.get("/roles", response_model=RoleListOut)
def list_roles(
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> RoleListOut:
    total = len(list(db.scalars(select(AdminRole)).all()))
    items = list(
        db.scalars(select(AdminRole).order_by(AdminRole.id).limit(limit).offset(offset)).all()
    )
    return RoleListOut(items=[RoleOut.model_validate(r) for r in items], total=total)


@router.post("/roles", response_model=RoleOut, status_code=201)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> RoleOut:
    _require_super_admin(admin)
    if db.scalar(select(AdminRole).where(AdminRole.code == payload.code)):
        raise HTTPException(409, f"role code '{payload.code}' 已存在")
    valid = set(all_permission_codes())
    bad = [p for p in payload.permissions if p not in valid]
    if bad:
        raise HTTPException(400, f"未知权限点：{bad}")
    role = AdminRole(
        code=payload.code,
        name=payload.name,
        is_super_admin=False,
        is_builtin=False,
        permissions=payload.permissions,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return RoleOut.model_validate(role)


@router.patch("/roles/{role_id}", response_model=RoleOut)
def update_role(
    payload: RoleUpdate,
    role_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> RoleOut:
    _require_super_admin(admin)
    role = db.get(AdminRole, role_id)
    if role is None:
        raise HTTPException(404, "role not found")
    if role.is_super_admin and payload.permissions is not None:
        raise HTTPException(400, "super_admin 角色不可改 permissions（永远短路）")
    if payload.name is not None:
        role.name = payload.name
    if payload.permissions is not None:
        valid = set(all_permission_codes())
        bad = [p for p in payload.permissions if p not in valid]
        if bad:
            raise HTTPException(400, f"未知权限点：{bad}")
        role.permissions = payload.permissions
    db.commit()
    return RoleOut.model_validate(role)


@router.delete("/roles/{role_id}", status_code=204)
def delete_role(
    role_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> None:
    _require_super_admin(admin)
    role = db.get(AdminRole, role_id)
    if role is None:
        raise HTTPException(404, "role not found")
    if role.is_builtin:
        raise HTTPException(400, "内置角色不可删")
    in_use = db.scalar(select(AdminUser).where(AdminUser.role_id == role_id))
    if in_use:
        raise HTTPException(409, "该角色仍有 admin 用户绑定，请先迁移")
    db.delete(role)
    db.commit()


# ===== Admin Users =====


def _serialize_admin(u: AdminUser) -> AdminUserOut:
    return AdminUserOut(
        id=u.id,
        email=u.email,
        display_name=u.display_name,
        role_id=u.role_id,
        role_code=u.role.code if u.role else "",
        role_name=u.role.name if u.role else "",
        is_super_admin=bool(u.role and u.role.is_super_admin),
        app_scope=u.app_scope or [],
        status=u.status,
        last_login_at=u.last_login_at,
        created_at=u.created_at,
    )


@router.get("/admins", response_model=AdminUserListOut)
def list_admins(
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> AdminUserListOut:
    stmt = select(AdminUser).order_by(AdminUser.id.desc())
    total = len(list(db.scalars(stmt).all()))
    items = list(db.scalars(stmt.limit(limit).offset(offset)).all())
    return AdminUserListOut(items=[_serialize_admin(u) for u in items], total=total)


@router.post("/admins", response_model=AdminUserOut, status_code=201)
def create_admin(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> AdminUserOut:
    _require_super_admin(admin)
    email = payload.email.lower().strip()
    if db.scalar(select(AdminUser).where(AdminUser.email == email)):
        raise HTTPException(409, "email 已被占用")
    if not db.get(AdminRole, payload.role_id):
        raise HTTPException(400, f"role_id={payload.role_id} 不存在")
    u = AdminUser(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role_id=payload.role_id,
        app_scope=payload.app_scope,
        status="active",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return _serialize_admin(u)


@router.patch("/admins/{admin_id}", response_model=AdminUserOut)
def update_admin(
    payload: AdminUserUpdate,
    admin_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> AdminUserOut:
    _require_super_admin(admin)
    u = db.get(AdminUser, admin_id)
    if u is None:
        raise HTTPException(404, "admin not found")
    # 不允许 super_admin 自己降级到非 super 角色（防锁死）
    if u.role and u.role.is_super_admin and payload.role_id and payload.role_id != u.role_id:
        target = db.get(AdminRole, payload.role_id)
        if target is None or not target.is_super_admin:
            raise HTTPException(400, "super_admin 不能改成非 super 角色")
    if payload.role_id is not None:
        if not db.get(AdminRole, payload.role_id):
            raise HTTPException(400, f"role_id={payload.role_id} 不存在")
        u.role_id = payload.role_id
    if payload.display_name is not None:
        u.display_name = payload.display_name
    if payload.app_scope is not None:
        u.app_scope = payload.app_scope
    if payload.status is not None:
        if payload.status not in {"active", "suspended"}:
            raise HTTPException(400, "status 只允许 active / suspended")
        u.status = payload.status
    if payload.password is not None:
        u.password_hash = hash_password(payload.password)
    db.commit()
    db.refresh(u)
    return _serialize_admin(u)


@router.delete("/admins/{admin_id}", status_code=204)
def disable_admin(
    admin_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> None:
    """软禁：标 suspended，不真删（保留审计 / FK）"""
    _require_super_admin(admin)
    if admin.id == admin_id:
        raise HTTPException(400, "不能禁用自己")
    u = db.get(AdminUser, admin_id)
    if u is None:
        raise HTTPException(404, "admin not found")
    u.status = "suspended"
    db.commit()
