"""content 模块共用服务函数（i18n 选择 / 可见性过滤 / 公开序列化）"""

from __future__ import annotations

from sqlalchemy import Select, exists, select
from sqlalchemy.orm import Session

from app.modules.content.models import CtRegionVisibility, CtVideo
from app.modules.content.schemas import VideoPublicOut


def pick_locale(i18n: dict[str, str] | None, lang: str | None, fallback: str = "en") -> str:
    """按优先级取语言文案：精确 lang → 顶层基底（如 zh-CN→zh）→ fallback → 任意一条 → 空串。"""
    if not i18n:
        return ""
    if lang:
        if lang in i18n:
            return i18n[lang]
        # zh-CN → zh
        base = lang.split("-")[0].lower()
        if base in i18n:
            return i18n[base]
    if fallback in i18n:
        return i18n[fallback]
    # 任意一条总比空白好
    for v in i18n.values():
        if v:
            return v
    return ""


def to_public(video: CtVideo, *, lang: str | None = None) -> VideoPublicOut:
    return VideoPublicOut(
        id=video.id,
        code=video.code,
        title=pick_locale(video.title_i18n, lang),
        description=pick_locale(video.description_i18n, lang),
        type=video.type,
        category_id=video.category_id,
        tags=video.tags or [],
        score=video.score,
        rating=video.rating,
        release_year=video.release_year,
        duration_min=video.duration_min,
        director=video.director,
        cast_list=video.cast_list or [],
        studio=video.studio,
        cover_url=video.cover_url,
        poster_url=video.poster_url,
        trailer_url=video.trailer_url,
        required_tier=video.required_tier,
        featured=video.featured,
        trending=video.trending,
        views=video.views,
    )


def apply_public_filters(stmt: Select, *, country: str | None) -> Select:
    """App 端可见性约束（合并到任意 select on CtVideo 上）：
    - status=online 上线
    - secondary_review_status=approved 通过二审
    - vod_status=ready 转码 OK（短片/电影直挂；剧集走 episode 自身 vod_status）
    - 地区可见性（红线 #8 默认 false / 黑名单制 / 运营必须手动开启每个国家）：
        * 必须存在 (video_id, country=user.country, visible=true) 行
        * 没行 → 不可见（不再 fallthrough 全开放）
        * country 缺失（user 没传） → 不可见
    """
    has_visible_for_country = (
        exists()
        .where(
            CtRegionVisibility.video_id == CtVideo.id,
            CtRegionVisibility.country_code == (country or "").upper(),
            CtRegionVisibility.visible.is_(True),
        )
        .correlate(CtVideo)
    )

    stmt = stmt.where(
        CtVideo.status == "online",
        CtVideo.secondary_review_status == "approved",
        CtVideo.vod_status == "ready",
    )
    # 红线 #8：默认 false / 黑名单制 — 必须有 (video, country, visible=true) 行才可见
    stmt = stmt.where(has_visible_for_country)
    return stmt


def is_video_visible_for(db: Session, video: CtVideo, country: str | None) -> bool:
    """单条命中检查（详情页用）。红线 #8：缺行 = 不可见。"""
    if video.status != "online" or video.secondary_review_status != "approved":
        return False
    if video.vod_status != "ready":
        return False
    if not country:
        return False  # 红线 #8：country 缺失 = 不可见
    visible = db.scalar(
        select(
            exists().where(
                CtRegionVisibility.video_id == video.id,
                CtRegionVisibility.country_code == country.upper(),
                CtRegionVisibility.visible.is_(True),
            )
        )
    )
    return bool(visible)
