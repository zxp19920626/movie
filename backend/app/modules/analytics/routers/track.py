"""POST /api/v1/analytics/track — App / admin-web 埋点接收端点。

设计：
- 公开 + optionalAuth（登录用户附 user_id；未登录看 device_id / IP）
- 事件类型白名单；非法 type 不抛 400 而是计入 rejected（避免一条坏事件让一批失败）
- 限流：100/min/IP（防刷不防误用；超出 429）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user_optional
from app.modules.analytics.models import AnalyticsEvent
from app.modules.analytics.schemas import (
    ALLOWED_EVENT_TYPES,
    TrackBatchIn,
    TrackResp,
)
from app.shared.middleware.rate_limit import rate_limit

router = APIRouter()


def _client_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post(
    "/track",
    response_model=TrackResp,
    dependencies=[Depends(rate_limit("analytics_track", limit=100, per_seconds=60))],
)
def track(
    payload: TrackBatchIn,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_optional),
) -> TrackResp:
    accepted = 0
    rejected: list[str] = []
    ip = _client_ip(request)
    ua = request.headers.get("user-agent")

    for ev in payload.events:
        if ev.event_type not in ALLOWED_EVENT_TYPES:
            rejected.append(ev.event_type)
            continue
        rec = AnalyticsEvent(
            event_type=ev.event_type,
            user_id=user.id if user else None,
            device_id=ev.device_id,
            session_id=ev.session_id,
            page_code=ev.page_code,
            properties=ev.properties,
            country=ev.country.upper() if ev.country else (user.country if user else None),
            app_id=ev.app_id if ev.app_id else (user.app_id if user else None),
            platform=ev.platform,
            ip=ip,
            ua=(ua or "")[:255] or None,
        )
        db.add(rec)
        accepted += 1
    if accepted:
        db.commit()
    return TrackResp(accepted=accepted, rejected=len(rejected), rejected_types=rejected)
