"""channel_pack 5 张表（前缀 cp_）"""

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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CpApp(Base):
    """cp_apps：多租户根。每行 = 一个接入分发平台的 App"""

    __tablename__ = "cp_apps"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    tenant_uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    package_name: Mapped[str] = mapped_column(String(255))  # com.example.app
    owner_admin_user_id: Mapped[int] = mapped_column(ForeignKey("a_admin_users.id"))
    api_key_hash: Mapped[str] = mapped_column(String(255))  # bcrypt(api_key) for service-to-service
    hmac_secret: Mapped[str] = mapped_column(String(128))  # base64 32 bytes — App SDK 用
    status: Mapped[str] = mapped_column(String(16), default="active")
    allowed_upgrade_hosts: Mapped[list] = mapped_column(
        JSON, default=list, server_default="[]", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CpChannel(Base):
    """cp_channels：渠道（如 gp / direct / xiaomi_intl）"""

    __tablename__ = "cp_channels"
    __table_args__ = (UniqueConstraint("app_id", "code", name="uq_cp_channels_app_code"),)

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    app_id: Mapped[int] = mapped_column(ForeignKey("cp_apps.id"), index=True)
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))
    is_play_store: Mapped[bool] = mapped_column(Boolean, default=False)
    signing_strategy: Mapped[str] = mapped_column(String(16), default="walle")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=10)
    oss_prefix: Mapped[str] = mapped_column(String(255), default="")  # 默认 apks/{tenant}/
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CpAppVersion(Base):
    """cp_app_versions：母包版本（每个 version_code 一行）"""

    __tablename__ = "cp_app_versions"
    __table_args__ = (UniqueConstraint("app_id", "version_code", name="uq_cp_versions_app_vc"),)

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    app_id: Mapped[int] = mapped_column(ForeignKey("cp_apps.id"), index=True)
    version_code: Mapped[int] = mapped_column(Integer)
    version_name: Mapped[str] = mapped_column(String(32))
    master_apk_oss_key: Mapped[str] = mapped_column(String(512))
    master_apk_sha256: Mapped[str] = mapped_column(String(64))
    master_apk_size: Mapped[int] = mapped_column(BigInteger, default=0)
    min_supported_version_code: Mapped[int] = mapped_column(Integer, default=0)
    changelog_i18n: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft/signing/ready/archived
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("a_admin_users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CpUpgradeRule(Base):
    """cp_upgrade_rules：升级规则（target × policy 表达 强制/灰度/分组）"""

    __tablename__ = "cp_upgrade_rules"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    app_id: Mapped[int] = mapped_column(ForeignKey("cp_apps.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # target 维度
    version_code_min: Mapped[int] = mapped_column(Integer)
    version_code_max: Mapped[int] = mapped_column(Integer)
    channel_codes: Mapped[list] = mapped_column(JSON, default=list)  # [] = all
    country_codes: Mapped[list] = mapped_column(JSON, default=list)  # [] = all
    device_id_hash_mod_min: Mapped[int] = mapped_column(Integer, default=0)
    device_id_hash_mod_max: Mapped[int] = mapped_column(Integer, default=99)

    # policy 维度
    target_version_code: Mapped[int] = mapped_column(Integer)
    is_force: Mapped[bool] = mapped_column(Boolean, default=False)
    can_skip: Mapped[bool] = mapped_column(Boolean, default=True)
    popup_strategy: Mapped[str] = mapped_column(
        String(32), default="once_per_session"
    )  # once_per_launch / once_per_session / once_per_day / once_per_week / once_per_release / custom_interval
    popup_interval_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    popup_title_i18n: Mapped[dict] = mapped_column(JSON, default=dict)
    popup_content_i18n: Mapped[dict] = mapped_column(JSON, default=dict)
    confirm_text_i18n: Mapped[dict] = mapped_column(JSON, default=dict)
    cancel_text_i18n: Mapped[dict] = mapped_column(JSON, default=dict)
    popup_buttons: Mapped[list] = mapped_column(
        JSON, default=list, server_default="[]", nullable=False
    )

    priority: Mapped[int] = mapped_column(Integer, default=10, index=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[int] = mapped_column(ForeignKey("a_admin_users.id"))


class CpApkSigningJob(Base):
    """cp_apk_signing_jobs：签名 fan-out 任务（幂等，可重试）"""

    __tablename__ = "cp_apk_signing_jobs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    app_id: Mapped[int] = mapped_column(ForeignKey("cp_apps.id"), index=True)
    version_code: Mapped[int] = mapped_column(Integer)
    channel_code: Mapped[str] = mapped_column(String(32))
    master_sha256: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)

    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    output_oss_key: Mapped[str] = mapped_column(String(512), default="")
    output_sha256: Mapped[str] = mapped_column(String(64), default="")
    output_size: Mapped[int] = mapped_column(BigInteger, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")
    worker_id: Mapped[str] = mapped_column(String(64), default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cdn_warmup_status: Mapped[str] = mapped_column(String(16), default="pending")


Index("ix_cp_signing_jobs_app_vc", CpApkSigningJob.app_id, CpApkSigningJob.version_code)
