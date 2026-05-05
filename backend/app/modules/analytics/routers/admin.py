"""GET /api/v1/admin/stats/* — 后台仪表盘聚合接口。

实现策略：
- 直接 SQL 聚合（小流量阶段够用；DAU > 5w 切到预聚合表）
- overview 默认 24h 窗；trends 默认 30 天日粒度
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.modules.analytics.models import AnalyticsEvent
from app.modules.analytics.schemas import (
    StatsOverviewOut,
    StatsTrendsOut,
    TrendPoint,
    TrendSeries,
)

router = APIRouter()


def _count(db: Session, since: datetime, *predicates) -> int:
    stmt = (
        select(func.count()).select_from(AnalyticsEvent).where(AnalyticsEvent.created_at >= since)
    )
    for p in predicates:
        stmt = stmt.where(p)
    return int(db.scalar(stmt) or 0)


def _count_distinct(db: Session, col, since: datetime, *predicates) -> int:
    stmt = (
        select(func.count(distinct(col)))
        .select_from(AnalyticsEvent)
        .where(AnalyticsEvent.created_at >= since)
    )
    for p in predicates:
        stmt = stmt.where(p)
    return int(db.scalar(stmt) or 0)


@router.get("/overview", response_model=StatsOverviewOut)
def overview(
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
    period_hours: int = Query(24, ge=1, le=720),
) -> StatsOverviewOut:
    since = datetime.now(UTC) - timedelta(hours=period_hours)
    return StatsOverviewOut(
        period_hours=period_hours,
        dau=_count_distinct(db, AnalyticsEvent.user_id, since, AnalyticsEvent.user_id.is_not(None)),
        daa=_count_distinct(
            db, AnalyticsEvent.device_id, since, AnalyticsEvent.device_id.is_not(None)
        ),
        play_start_count=_count(db, since, AnalyticsEvent.event_type == "play_start"),
        search_count=_count(db, since, AnalyticsEvent.event_type == "search"),
        ad_pv=_count(db, since, AnalyticsEvent.event_type.like("ad_%")),
        upgrade_check_count=_count(db, since, AnalyticsEvent.event_type == "upgrade_check"),
        # P5+ 接订阅模块后真填
        new_subscriptions=0,
        revenue_estimate=0.0,
    )


def _daily_series(db: Session, days: int, predicate) -> list[TrendPoint]:
    """按天 group + count；按天 zero-fill 保证前端 echarts 不断点。"""
    since = datetime.now(UTC) - timedelta(days=days)
    # SQLite/MySQL 通用：group by date 字符串
    date_expr = func.strftime("%Y-%m-%d", AnalyticsEvent.created_at)
    # MySQL 8 也支持 strftime（DATE_FORMAT 更严格但需方言判断）；
    # 演化：上 RDS 后切 func.date_format(..., "%%Y-%%m-%%d") 或 cast(... as Date)
    rows = list(
        db.execute(
            select(date_expr.label("d"), func.count().label("c"))
            .where(AnalyticsEvent.created_at >= since)
            .where(predicate)
            .group_by(date_expr)
            .order_by(date_expr)
        ).all()
    )
    counts = {r[0]: int(r[1]) for r in rows if r[0]}
    points: list[TrendPoint] = []
    today = datetime.now(UTC).date()
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        points.append(TrendPoint(date=d, value=counts.get(d, 0)))
    return points


@router.get("/trends", response_model=StatsTrendsOut)
def trends(
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
    days: int = Query(30, ge=1, le=180),
) -> StatsTrendsOut:
    series = [
        TrendSeries(
            code="play_start",
            label="播放次数",
            points=_daily_series(db, days, AnalyticsEvent.event_type == "play_start"),
        ),
        TrendSeries(
            code="search",
            label="搜索",
            points=_daily_series(db, days, AnalyticsEvent.event_type == "search"),
        ),
        TrendSeries(
            code="upgrade_check",
            label="升级检查",
            points=_daily_series(db, days, AnalyticsEvent.event_type == "upgrade_check"),
        ),
        TrendSeries(
            code="ad_pv",
            label="广告曝光",
            points=_daily_series(db, days, AnalyticsEvent.event_type.like("ad_%")),
        ),
    ]
    return StatsTrendsOut(days=days, series=series)
