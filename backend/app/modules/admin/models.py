from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AdminRole(Base):
    """a_admin_roles：6 模块 × view/edit + 4 seed 角色（详见 PROMPT.md §5）"""

    __tablename__ = "a_admin_roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    is_super_admin: Mapped[bool] = mapped_column(default=False)
    is_builtin: Mapped[bool] = mapped_column(default=False)
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdminUser(Base):
    """a_admin_users：管理员账号；带 app_scope 多租户权限隔离"""

    __tablename__ = "a_admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(128), default="")
    role_id: Mapped[int] = mapped_column(ForeignKey("a_admin_roles.id"))
    app_scope: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    role: Mapped[AdminRole] = relationship(lazy="joined")

    def to_public(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role.code if self.role else "",
            "app_scope": self.app_scope or [],
            "permissions": self.role.permissions if self.role else [],
            "is_super_admin": bool(self.role and self.role.is_super_admin),
        }
