"""content App 端路由 /api/v1/videos/...

设计：
- 全部要求 user JWT（admin token 不能直接当 App 用）
- 列表 / 详情 / 首页聚合 / 搜索：按用户 country 过滤 region_visibility
- i18n：按 user.preferred_language 选 title/description；fallback 'en' → 任意一条
- 不暴露 vod_file_id（要播放走 play-token）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import String, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.modules.content.models import CtVideo
from app.modules.content.schemas import (
    HomeAggregateOut,
    HomeSection,
    PlayTokenOut,
    VideoPublicList,
    VideoPublicOut,
)
from app.modules.content.services import (
    apply_public_filters,
    is_video_visible_for,
    to_public,
)
from app.shared.media_provider.service import get_play_token_provider
from app.shared.middleware.app_sign import verify_app_sign
from app.shared.middleware.rate_limit import rate_limit

# 整组 App 端 video 路由都强制包签名（dev 无 APP_SIGN_SECRET 自动放行）
_APP_GUARDS = [Depends(verify_app_sign)]

router = APIRouter(dependencies=_APP_GUARDS)


@router.get("", response_model=VideoPublicList)
def list_videos(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    category_id: int | None = Query(None),
    type_: str | None = Query(None, alias="type"),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
) -> VideoPublicList:
    stmt = select(CtVideo)
    stmt = apply_public_filters(stmt, country=user.country)
    if category_id:
        stmt = stmt.where(CtVideo.category_id == category_id)
    if type_:
        stmt = stmt.where(CtVideo.type == type_)
    total = len(list(db.scalars(stmt).all()))
    rows = list(
        db.scalars(
            stmt.order_by(CtVideo.recommend_priority.desc(), CtVideo.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return VideoPublicList(
        items=[to_public(v, lang=user.preferred_language) for v in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/home", response_model=HomeAggregateOut)
def home_aggregate(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    per_section: int = Query(10, ge=1, le=30),
) -> HomeAggregateOut:
    """首页聚合：单接口减少 App 往返。返回 4 段：featured / trending / top10 / continue_watching。"""
    base = apply_public_filters(select(CtVideo), country=user.country)
    lang = user.preferred_language

    featured = list(
        db.scalars(
            base.where(CtVideo.featured.is_(True))
            .order_by(CtVideo.recommend_priority.desc(), CtVideo.id.desc())
            .limit(per_section)
        ).all()
    )
    trending = list(
        db.scalars(
            base.where(CtVideo.trending.is_(True))
            .order_by(CtVideo.views.desc(), CtVideo.id.desc())
            .limit(per_section)
        ).all()
    )
    top10 = list(
        db.scalars(base.order_by(CtVideo.views.desc(), CtVideo.id.desc()).limit(per_section)).all()
    )

    # continueWatching：用户 watch_history 最近 N 条对应仍可见的 videos
    from app.modules.content.models import CtWatchHistory

    recent_history = list(
        db.scalars(
            select(CtWatchHistory)
            .where(CtWatchHistory.user_id == user.id)
            .order_by(CtWatchHistory.updated_at.desc())
            .limit(per_section * 2)
        ).all()
    )
    continue_watching: list[CtVideo] = []
    for h in recent_history:
        v = db.get(CtVideo, h.video_id)
        if v and is_video_visible_for(db, v, user.country):
            continue_watching.append(v)
        if len(continue_watching) >= per_section:
            break

    sections = [
        HomeSection(
            code="featured",
            title="精选",
            items=[to_public(v, lang=lang) for v in featured],
        ),
        HomeSection(
            code="continue_watching",
            title="继续观看",
            items=[to_public(v, lang=lang) for v in continue_watching],
        ),
        HomeSection(
            code="trending",
            title="热门",
            items=[to_public(v, lang=lang) for v in trending],
        ),
        HomeSection(
            code="top10",
            title="Top 10",
            items=[to_public(v, lang=lang) for v in top10],
        ),
    ]
    return HomeAggregateOut(sections=sections)


@router.get(
    "/search",
    response_model=VideoPublicList,
    dependencies=[Depends(rate_limit("videos_search", limit=60, per_seconds=60))],
)
def search_videos(
    q: str = Query(..., min_length=1, max_length=128),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
) -> VideoPublicList:
    """多字段检索：code / director / cast / studio / tags / title_i18n / description_i18n。
    SQLite 阶段用 ilike + JSON 文本匹配；MySQL 上线后建全文索引或换 OpenSearch。
    """
    pattern = f"%{q}%"
    stmt = select(CtVideo)
    stmt = apply_public_filters(stmt, country=user.country)
    stmt = stmt.where(
        or_(
            CtVideo.code.ilike(pattern),
            CtVideo.director.ilike(pattern),
            CtVideo.studio.ilike(pattern),
            # JSON 字段兜底走文字匹配（生产 MySQL 上换 JSON_CONTAINS / 全文索引）
            CtVideo.cast_list.cast(String).ilike(pattern),
            CtVideo.tags.cast(String).ilike(pattern),
            CtVideo.title_i18n.cast(String).ilike(pattern),
            CtVideo.description_i18n.cast(String).ilike(pattern),
        )
    )
    total = len(list(db.scalars(stmt).all()))
    rows = list(
        db.scalars(
            stmt.order_by(CtVideo.views.desc(), CtVideo.id.desc()).limit(limit).offset(offset)
        ).all()
    )
    return VideoPublicList(
        items=[to_public(v, lang=user.preferred_language) for v in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{video_id}", response_model=VideoPublicOut)
def get_video(
    video_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> VideoPublicOut:
    v = db.get(CtVideo, video_id)
    if v is None:
        raise HTTPException(404, "video not found")
    if not is_video_visible_for(db, v, user.country):
        # 不区分 404 / 403，避免泄露存在性
        raise HTTPException(404, "video not found")
    return to_public(v, lang=user.preferred_language)


PLAY_TOKEN_TTL_SEC = 300  # 5 分钟


@router.get(
    "/{video_id}/play-token",
    response_model=PlayTokenOut,
    dependencies=[Depends(rate_limit("play_token", limit=30, per_seconds=60))],
)
def get_play_token(
    request: Request,
    video_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> PlayTokenOut:
    """签发 PlayAuth：5 分钟过期 + IP 绑定（IP 由 IPlayTokenProvider 实现使用）。

    会员等级（required_tier）暂占位放行；P5+ 接入订阅模块后改成
    `if v.required_tier > user.tier: raise 402 PaymentRequired`。
    """
    v = db.get(CtVideo, video_id)
    if v is None or not is_video_visible_for(db, v, user.country):
        raise HTTPException(404, "video not found")
    if not v.vod_file_id:
        raise HTTPException(409, "video has no vod_file_id (尚未挂 VOD)")

    client_ip = request.client.host if request.client else "0.0.0.0"  # noqa: S104
    provider = get_play_token_provider()
    pt = provider.issue_play_token(v.vod_file_id, client_ip=client_ip, ttl_sec=PLAY_TOKEN_TTL_SEC)
    return PlayTokenOut(
        file_id=v.vod_file_id,
        token=pt.token,
        play_url=pt.play_url,
        expires_at=pt.expires_at,
        ttl_sec=PLAY_TOKEN_TTL_SEC,
    )
