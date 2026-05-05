from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# 白名单事件类型；新增类型走代码 review，避免脏数据。
ALLOWED_EVENT_TYPES = frozenset(
    {
        "page_view",
        "play_start",
        "play_complete",
        "play_progress",
        "play_error",
        "search",
        "search_no_result",
        "upgrade_check",
        "upgrade_install",
        "ad_impression",
        "ad_click",
        "ad_close",
        "subscribe_start",
        "subscribe_success",
        "share",
        "favorite",
    }
)


class TrackEvent(BaseModel):
    event_type: str = Field(min_length=1, max_length=64)
    page_code: str | None = Field(default=None, max_length=64)
    session_id: str | None = Field(default=None, max_length=128)
    device_id: str | None = Field(default=None, max_length=128)
    properties: dict[str, Any] = Field(default_factory=dict)
    country: str | None = Field(default=None, max_length=8)
    app_id: int | None = None
    platform: str | None = Field(default=None, max_length=16)
    ts: datetime | None = None  # 客户端时间（仅参考；服务端以 created_at 为准）


class TrackBatchIn(BaseModel):
    """单条 / 批量 共用：events 数组（最大 50）。"""

    events: list[TrackEvent] = Field(min_length=1, max_length=50)


class TrackResp(BaseModel):
    accepted: int
    rejected: int
    rejected_types: list[str] = Field(default_factory=list)


# ===== 后台统计 =====


class StatsOverviewOut(BaseModel):
    """24 小时内核心 KPI."""

    period_hours: int
    dau: int  # 不重 user_id（不含匿名）
    daa: int  # 不重 device_id（含匿名 + 登录）
    play_start_count: int
    search_count: int
    ad_pv: int
    upgrade_check_count: int
    # 占位（订阅模块未实装）
    new_subscriptions: int = 0
    revenue_estimate: float = 0.0


class TrendPoint(BaseModel):
    date: str  # YYYY-MM-DD
    value: int


class TrendSeries(BaseModel):
    code: str
    label: str
    points: list[TrendPoint]


class StatsTrendsOut(BaseModel):
    days: int
    series: list[TrendSeries]


class EventCountRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_type: str
    count: int
