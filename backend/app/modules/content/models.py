"""content 5 张表（前缀 ct_）。

设计要点（来自 TASKS.md P4 + PROMPT.md A1' 媒体抽象层 + B1 secondary review）：
- 多语言：i18n 字段统一用 JSON dict，key 用 ISO-639-1 / BCP-47 子集（en/zh/id/vi/...）
- VOD 同步：本地保留快照字段（vod_status / vod_synced_at / vod_duration_sec），admin 可
  手动 "Pull from VOD" 强制刷新；webhook 来事件后增量更新
- 二审：secondary_review_status 状态机 draft → pending → approved/rejected；
  只有 approved 才对 App 端可见
- 地区可见性：ct_region_visibility 单独一张表，video × country 二维矩阵
- 观看历史：watch_history 用 (user_id, video_id, episode_id) 唯一约束 + updated_at
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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CtCategory(Base):
    """ct_categories：影片分类（树形 i18n）"""

    __tablename__ = "ct_categories"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # 业务编码
    name_i18n: Mapped[dict] = mapped_column(JSON, default=dict)  # {"en":"Movie","zh":"电影"}
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("ct_categories.id"), nullable=True, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active / archived
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CtVideo(Base):
    """ct_videos：影片主体（含 VOD 文件引用 + 多语言 + 二审 + 推荐位）"""

    __tablename__ = "ct_videos"
    __table_args__ = (Index("ix_ct_videos_status_secondary", "status", "secondary_review_status"),)

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # 业务编码（ascii）

    # i18n 文案
    title_i18n: Mapped[dict] = mapped_column(JSON, default=dict)
    description_i18n: Mapped[dict] = mapped_column(JSON, default=dict)

    # 业务字段
    type: Mapped[str] = mapped_column(String(16), default="movie")  # movie / series / short
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("ct_categories.id"), nullable=True, index=True
    )
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    score: Mapped[float | None] = mapped_column(nullable=True)  # 0.0~10.0
    rating: Mapped[str] = mapped_column(String(16), default="")  # PG / PG-13 / R / ...
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    release_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    director: Mapped[str] = mapped_column(String(255), default="")
    cast_list: Mapped[list[str]] = mapped_column(JSON, default=list)
    studio: Mapped[str] = mapped_column(String(255), default="")

    # 资源 URL（封面/海报/预告片）
    cover_url: Mapped[str] = mapped_column(String(512), default="")
    poster_url: Mapped[str] = mapped_column(String(512), default="")
    trailer_url: Mapped[str] = mapped_column(String(512), default="")

    # VOD 集成（短片/电影直挂；剧集走 episodes）
    vod_file_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    vod_status: Mapped[str] = mapped_column(
        String(16), default="pending"
    )  # pending / transcoding / ready / failed
    vod_duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vod_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 占位：会员等级（P5/P5+ 真接入再启用）
    required_tier: Mapped[str] = mapped_column(String(16), default="free")  # free / vip1 / vip2

    # 上线 / 二审 状态
    status: Mapped[str] = mapped_column(
        String(16), default="draft", index=True
    )  # draft / online / offline / archived
    secondary_review_status: Mapped[str] = mapped_column(
        String(16), default="draft", index=True
    )  # draft / pending / approved / rejected
    secondary_reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("a_admin_users.id"), nullable=True
    )
    secondary_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    secondary_review_note: Mapped[str] = mapped_column(Text, default="")

    # 推荐位 / 运营位
    featured: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    trending: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    views: Mapped[int] = mapped_column(BigInteger, default=0)
    recommend_priority: Mapped[int] = mapped_column(Integer, default=0, index=True)

    # 审计
    created_by: Mapped[int | None] = mapped_column(ForeignKey("a_admin_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CtVideoEpisode(Base):
    """ct_video_episodes：剧集 episode（season + episode_no 唯一）"""

    __tablename__ = "ct_video_episodes"
    __table_args__ = (
        UniqueConstraint("video_id", "season", "episode_no", name="uq_ct_episode_video_se_ep"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    video_id: Mapped[int] = mapped_column(ForeignKey("ct_videos.id"), index=True)
    season: Mapped[int] = mapped_column(Integer, default=1)
    episode_no: Mapped[int] = mapped_column(Integer)
    title_i18n: Mapped[dict] = mapped_column(JSON, default=dict)
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)

    vod_file_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    vod_status: Mapped[str] = mapped_column(String(16), default="pending")
    vod_duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vod_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CtRegionVisibility(Base):
    """ct_region_visibility：影片 × 国家二维矩阵。
    visible=True 才对该国家用户可见；缺行视作不可见（默认黑名单制）。
    """

    __tablename__ = "ct_region_visibility"
    __table_args__ = (
        UniqueConstraint("video_id", "country_code", name="uq_ct_region_visibility"),
        Index("ix_ct_region_country_visible", "country_code", "visible"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    video_id: Mapped[int] = mapped_column(ForeignKey("ct_videos.id"), index=True)
    country_code: Mapped[str] = mapped_column(String(8))  # ISO-3166-1 alpha-2 (US/JP/MY/...)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CtWatchHistory(Base):
    """ct_watch_history：观看进度（每用户最近 200 条，超出删旧）"""

    __tablename__ = "ct_watch_history"
    __table_args__ = (
        UniqueConstraint("user_id", "video_id", "episode_id", name="uq_ct_watch_user_video_ep"),
        Index("ix_ct_watch_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("u_users.id"), index=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("ct_videos.id"), index=True)
    episode_id: Mapped[int | None] = mapped_column(
        ForeignKey("ct_video_episodes.id"), nullable=True, index=True
    )
    position_sec: Mapped[int] = mapped_column(Integer, default=0)
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
