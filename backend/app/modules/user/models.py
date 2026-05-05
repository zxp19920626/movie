"""user 模块 5 张表（前缀 u_）

设计原则（与 architecture.md 对齐）：
- 不依赖兄弟模块的 internal models
- 跨模块只走 app.core / app.shared protocol
- u_users.app_id FK 到 cp_apps，记录用户从哪个 App 注册进来
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _bigint_pk():
    return mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )


class User(Base):
    """u_users：C 端用户。一个邮箱 / 手机 一行。"""

    __tablename__ = "u_users"
    __table_args__ = (Index("ix_u_users_phone", "phone"),)

    id: Mapped[int] = _bigint_pk()
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True)  # 公开 ID
    email: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)  # E.164 格式 +62xxx
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)  # +62 等
    display_name: Mapped[str] = mapped_column(String(128), default="")
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active/suspended/deleted
    country: Mapped[str | None] = mapped_column(String(8), nullable=True)  # ISO 3166-1 alpha-2
    preferred_language: Mapped[str] = mapped_column(String(8), default="en")
    app_id: Mapped[int | None] = mapped_column(
        ForeignKey("cp_apps.id"), nullable=True, index=True
    )  # 从哪个 cp_apps 注册进来
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def to_public(self) -> dict:
        return {
            "id": str(self.id),
            "uuid": self.uuid,
            "email": self.email,
            "phone": self.phone,
            "country_code": self.country_code,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "status": self.status,
            "country": self.country,
            "preferred_language": self.preferred_language,
            "app_id": self.app_id,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
        }


class UserOauth(Base):
    """u_user_oauth：第三方登录绑定（一个用户可多种 provider）

    provider: email / google / phone / apple / facebook
    provider_uid: provider 侧的稳定 ID
    """

    __tablename__ = "u_user_oauth"
    __table_args__ = (UniqueConstraint("provider", "provider_uid", name="uq_u_oauth_provider_uid"),)

    id: Mapped[int] = _bigint_pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("u_users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(16))
    provider_uid: Mapped[str] = mapped_column(String(255))
    raw_profile: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserDevice(Base):
    """u_devices：用户设备登记。同 user 可有多设备；同 device_id 同 app 唯一一行。"""

    __tablename__ = "u_devices"
    __table_args__ = (
        UniqueConstraint("user_id", "device_id", "app_id", name="uq_u_devices_user_device_app"),
    )

    id: Mapped[int] = _bigint_pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("u_users.id"), index=True)
    device_id: Mapped[str] = mapped_column(String(128))
    app_id: Mapped[int | None] = mapped_column(ForeignKey("cp_apps.id"), nullable=True)
    platform: Mapped[str] = mapped_column(String(16), default="android")
    app_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    push_token: Mapped[str | None] = mapped_column(String(256), nullable=True)
    country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OtpCode(Base):
    """u_otp_codes：手机 OTP 验证码（5 分钟有效，5 次错作废）"""

    __tablename__ = "u_otp_codes"
    __table_args__ = (Index("ix_u_otp_phone_active", "phone", "verified", "expires_at"),)

    id: Mapped[int] = _bigint_pk()
    phone: Mapped[str] = mapped_column(String(32), index=True)
    code_hash: Mapped[str] = mapped_column(String(128))  # bcrypt 防 timing attack
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RefreshToken(Base):
    """u_refresh_tokens：refresh token 旋转（被替换/撤销的入黑名单）

    JWT refresh 签发时记录 jti；旋转/登出时 revoked=true。
    """

    __tablename__ = "u_refresh_tokens"
    __table_args__ = (Index("ix_u_refresh_user_active", "user_id", "revoked", "expires_at"),)

    id: Mapped[int] = _bigint_pk()
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("u_users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
