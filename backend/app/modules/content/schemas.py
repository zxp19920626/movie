"""content 模块 Pydantic schemas（admin 后台 + 后续 App 端共用）"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ===== Categories =====


class CategoryCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name_i18n: dict[str, str] = Field(default_factory=dict)
    parent_id: int | None = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name_i18n: dict[str, str] | None = None
    parent_id: int | None = None
    sort_order: int | None = None
    status: str | None = None  # active / archived


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name_i18n: dict[str, str]
    parent_id: int | None
    sort_order: int
    status: str
    created_at: datetime


class CategoryList(BaseModel):
    items: list[CategoryOut]
    total: int


# ===== Videos =====


class VideoCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    title_i18n: dict[str, str] = Field(default_factory=dict)
    description_i18n: dict[str, str] = Field(default_factory=dict)
    type: str = "movie"  # movie / series / short
    category_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    score: float | None = None
    rating: str = ""
    release_year: int | None = None
    release_date: datetime | None = None
    duration_min: int | None = None
    director: str = ""
    cast_list: list[str] = Field(default_factory=list)
    studio: str = ""
    cover_url: str = ""
    poster_url: str = ""
    trailer_url: str = ""
    vod_file_id: str | None = None
    required_tier: str = "free"


class VideoUpdate(BaseModel):
    title_i18n: dict[str, str] | None = None
    description_i18n: dict[str, str] | None = None
    type: str | None = None
    category_id: int | None = None
    tags: list[str] | None = None
    score: float | None = None
    rating: str | None = None
    release_year: int | None = None
    release_date: datetime | None = None
    duration_min: int | None = None
    director: str | None = None
    cast_list: list[str] | None = None
    studio: str | None = None
    cover_url: str | None = None
    poster_url: str | None = None
    trailer_url: str | None = None
    vod_file_id: str | None = None
    required_tier: str | None = None
    status: str | None = None  # draft / online / offline / archived
    featured: bool | None = None
    trending: bool | None = None
    recommend_priority: int | None = None


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    title_i18n: dict[str, str]
    description_i18n: dict[str, str]
    type: str
    category_id: int | None
    tags: list[str]
    score: float | None
    rating: str
    release_year: int | None
    release_date: datetime | None
    duration_min: int | None
    director: str
    cast_list: list[str]
    studio: str
    cover_url: str
    poster_url: str
    trailer_url: str
    vod_file_id: str | None
    vod_status: str
    vod_synced_at: datetime | None
    required_tier: str
    status: str
    secondary_review_status: str
    secondary_reviewed_at: datetime | None
    featured: bool
    trending: bool
    views: int
    recommend_priority: int
    created_at: datetime
    updated_at: datetime


class VideoList(BaseModel):
    items: list[VideoOut]
    total: int


# ===== Region Visibility =====


class RegionVisibilityEntry(BaseModel):
    country_code: str = Field(min_length=2, max_length=8)
    visible: bool = True


class RegionVisibilitySet(BaseModel):
    """整批替换：传完整列表，未列出的国家视为不可见。"""

    entries: list[RegionVisibilityEntry]


class RegionVisibilityOut(BaseModel):
    video_id: int
    visible_countries: list[str]
    hidden_countries: list[str]


# ===== Secondary Review =====


class SecondaryReviewAction(BaseModel):
    action: str = Field(pattern="^(submit|approve|reject)$")
    note: str = ""


class SecondaryReviewOut(BaseModel):
    video_id: int
    secondary_review_status: str
    secondary_reviewed_by: int | None
    secondary_reviewed_at: datetime | None
    secondary_review_note: str

    model_config = ConfigDict(from_attributes=True)


# ===== App 端公开 schemas（按用户 country/lang 选 i18n，剔除内部字段）=====


class VideoPublicOut(BaseModel):
    id: int
    code: str
    title: str
    description: str
    type: str
    category_id: int | None
    tags: list[str]
    score: float | None
    rating: str
    release_year: int | None
    duration_min: int | None
    director: str
    cast_list: list[str]
    studio: str
    cover_url: str
    poster_url: str
    trailer_url: str
    required_tier: str
    featured: bool
    trending: bool
    views: int
    # 不暴露 vod_file_id（拿 play-token 换播放凭证）
    # 不暴露 secondary_review_status / status / created_by 等内部字段


class VideoPublicList(BaseModel):
    items: list[VideoPublicOut]
    total: int
    limit: int
    offset: int


class HomeSection(BaseModel):
    code: str  # featured / continue_watching / trending / top10
    title: str
    items: list[VideoPublicOut]


class HomeAggregateOut(BaseModel):
    sections: list[HomeSection]


# ===== 播放凭证 =====


class PlayTokenOut(BaseModel):
    file_id: str
    token: str
    play_url: str
    expires_at: datetime
    ttl_sec: int


# ===== 观看历史 =====


class WatchHistoryUpsert(BaseModel):
    video_id: int
    episode_id: int | None = None
    position_sec: int = Field(ge=0)
    duration_sec: int = Field(ge=0)


class WatchHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    video_id: int
    episode_id: int | None
    position_sec: int
    duration_sec: int
    updated_at: datetime


class WatchHistoryList(BaseModel):
    items: list[WatchHistoryItem]
    total: int


# ===== 通用 =====


class IdResponse(BaseModel):
    id: int
    extra: dict[str, Any] | None = None


class OkResponse(BaseModel):
    ok: bool = True
    extra: dict[str, Any] | None = None
