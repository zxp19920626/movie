"""analytics 1 张表（前缀 s_）。

设计：
- 行级追加，**绝对不更新**（避免事务/锁问题）
- 索引覆盖三大查询路径：(event_type, created_at) / (user_id, created_at) / (app_id, created_at)
- properties 用 JSON dict，灵活存事件级字段（duration / search_q / video_id 等）
- DAU > 1w 后按月分表（partition by created_at YYYY_MM）；当前阶段单表足够
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AnalyticsEvent(Base):
    __tablename__ = "s_analytics_events"
    __table_args__ = (
        Index("ix_s_events_type_time", "event_type", "created_at"),
        Index("ix_s_events_user_time", "user_id", "created_at"),
        Index("ix_s_events_app_time", "app_id", "created_at"),
        Index("ix_s_events_page_time", "page_code", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("u_users.id"), nullable=True, index=True)
    device_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    page_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    app_id: Mapped[int | None] = mapped_column(ForeignKey("cp_apps.id"), nullable=True, index=True)
    platform: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ua: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
