"""content 后台路由 /api/v1/admin/content/...

涵盖：
- categories CRUD（i18n 多语言名）
- videos CRUD（含全字段编辑 / 上下线）
- region-visibility 矩阵替换
- secondary-review 状态机（draft → pending → approved/rejected）
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.modules.content.models import (
    CtCategory,
    CtRegionVisibility,
    CtVideo,
)
from app.modules.content.schemas import (
    CategoryCreate,
    CategoryList,
    CategoryOut,
    CategoryUpdate,
    RegionVisibilityOut,
    RegionVisibilitySet,
    SecondaryReviewAction,
    SecondaryReviewOut,
    VideoCreate,
    VideoList,
    VideoOut,
    VideoUpdate,
)

router = APIRouter()


# ============== Categories ==============


@router.get("/categories", response_model=CategoryList)
def list_categories(
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> CategoryList:
    stmt = select(CtCategory).order_by(CtCategory.sort_order.asc(), CtCategory.id.asc())
    total = len(list(db.scalars(stmt).all()))
    items = list(db.scalars(stmt.limit(limit).offset(offset)).all())
    return CategoryList(items=[CategoryOut.model_validate(c) for c in items], total=total)


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> CategoryOut:
    if db.scalar(select(CtCategory).where(CtCategory.code == payload.code)):
        raise HTTPException(409, f"category code '{payload.code}' 已存在")
    cat = CtCategory(
        code=payload.code,
        name_i18n=payload.name_i18n,
        parent_id=payload.parent_id,
        sort_order=payload.sort_order,
        status="active",
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return CategoryOut.model_validate(cat)


@router.patch("/categories/{cat_id}", response_model=CategoryOut)
def update_category(
    payload: CategoryUpdate,
    cat_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> CategoryOut:
    cat = db.get(CtCategory, cat_id)
    if cat is None:
        raise HTTPException(404, "category not found")
    for f in ("name_i18n", "parent_id", "sort_order", "status"):
        v = getattr(payload, f)
        if v is not None:
            setattr(cat, f, v)
    db.commit()
    return CategoryOut.model_validate(cat)


@router.delete("/categories/{cat_id}", status_code=204)
def delete_category(
    cat_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> None:
    cat = db.get(CtCategory, cat_id)
    if cat is None:
        raise HTTPException(404, "category not found")
    # 软删：标 archived，不真删（可能仍有 videos 关联）
    cat.status = "archived"
    db.commit()


# ============== Videos ==============


@router.get("/videos", response_model=VideoList)
def list_videos(
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
    status: str | None = Query(None),
    secondary_review_status: str | None = Query(None),
    category_id: int | None = Query(None),
    q: str | None = Query(None, description="按 code 模糊匹配"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> VideoList:
    stmt = select(CtVideo)
    if status:
        stmt = stmt.where(CtVideo.status == status)
    if secondary_review_status:
        stmt = stmt.where(CtVideo.secondary_review_status == secondary_review_status)
    if category_id:
        stmt = stmt.where(CtVideo.category_id == category_id)
    if q:
        stmt = stmt.where(CtVideo.code.ilike(f"%{q}%"))
    total = len(list(db.scalars(stmt).all()))
    items = list(
        db.scalars(
            stmt.order_by(CtVideo.recommend_priority.desc(), CtVideo.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return VideoList(items=[VideoOut.model_validate(v) for v in items], total=total)


@router.post("/videos", response_model=VideoOut, status_code=201)
def create_video(
    payload: VideoCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
) -> VideoOut:
    if db.scalar(select(CtVideo).where(CtVideo.code == payload.code)):
        raise HTTPException(409, f"video code '{payload.code}' 已存在")
    if payload.category_id and not db.get(CtCategory, payload.category_id):
        raise HTTPException(400, f"category_id={payload.category_id} 不存在")
    v = CtVideo(
        code=payload.code,
        title_i18n=payload.title_i18n,
        description_i18n=payload.description_i18n,
        type=payload.type,
        category_id=payload.category_id,
        tags=payload.tags,
        score=payload.score,
        rating=payload.rating,
        release_year=payload.release_year,
        release_date=payload.release_date,
        duration_min=payload.duration_min,
        director=payload.director,
        cast_list=payload.cast_list,
        studio=payload.studio,
        cover_url=payload.cover_url,
        poster_url=payload.poster_url,
        trailer_url=payload.trailer_url,
        vod_file_id=payload.vod_file_id,
        required_tier=payload.required_tier,
        status="draft",
        secondary_review_status="draft",
        created_by=admin.id,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return VideoOut.model_validate(v)


@router.get("/videos/{video_id}", response_model=VideoOut)
def get_video(
    video_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> VideoOut:
    v = db.get(CtVideo, video_id)
    if v is None:
        raise HTTPException(404, "video not found")
    return VideoOut.model_validate(v)


@router.put("/videos/{video_id}", response_model=VideoOut)
def update_video(
    payload: VideoUpdate,
    video_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> VideoOut:
    v = db.get(CtVideo, video_id)
    if v is None:
        raise HTTPException(404, "video not found")
    if payload.category_id is not None and not db.get(CtCategory, payload.category_id):
        raise HTTPException(400, f"category_id={payload.category_id} 不存在")
    # 状态机：上线必须 secondary_review_status=approved
    if payload.status == "online" and v.secondary_review_status != "approved":
        raise HTTPException(400, "video 未通过二审，不能上线")
    for f, val in payload.model_dump(exclude_unset=True).items():
        setattr(v, f, val)
    db.commit()
    return VideoOut.model_validate(v)


@router.delete("/videos/{video_id}", status_code=204)
def delete_video(
    video_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> None:
    v = db.get(CtVideo, video_id)
    if v is None:
        raise HTTPException(404, "video not found")
    # 软删：archived（避免破坏 watch_history 引用）
    v.status = "archived"
    db.commit()


# ============== Region Visibility ==============


@router.get("/videos/{video_id}/region-visibility", response_model=RegionVisibilityOut)
def get_region_visibility(
    video_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> RegionVisibilityOut:
    v = db.get(CtVideo, video_id)
    if v is None:
        raise HTTPException(404, "video not found")
    rows = list(
        db.scalars(select(CtRegionVisibility).where(CtRegionVisibility.video_id == video_id)).all()
    )
    visible = [r.country_code for r in rows if r.visible]
    hidden = [r.country_code for r in rows if not r.visible]
    return RegionVisibilityOut(
        video_id=video_id, visible_countries=visible, hidden_countries=hidden
    )


@router.post("/videos/{video_id}/region-visibility", response_model=RegionVisibilityOut)
def set_region_visibility(
    payload: RegionVisibilitySet,
    video_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> RegionVisibilityOut:
    """整批替换：删除旧记录，写入新列表。"""
    v = db.get(CtVideo, video_id)
    if v is None:
        raise HTTPException(404, "video not found")

    # 去重 country_code
    seen = {}
    for e in payload.entries:
        seen[e.country_code.upper()] = e.visible

    # 删旧
    db.query(CtRegionVisibility).filter(CtRegionVisibility.video_id == video_id).delete()
    # 写新
    for cc, vis in seen.items():
        db.add(CtRegionVisibility(video_id=video_id, country_code=cc, visible=vis))
    db.commit()

    rows = list(
        db.scalars(select(CtRegionVisibility).where(CtRegionVisibility.video_id == video_id)).all()
    )
    return RegionVisibilityOut(
        video_id=video_id,
        visible_countries=[r.country_code for r in rows if r.visible],
        hidden_countries=[r.country_code for r in rows if not r.visible],
    )


# ============== Secondary Review ==============


_REVIEW_TRANSITIONS = {
    # current → allowed actions
    "draft": {"submit"},
    "pending": {"approve", "reject"},
    "approved": {"reject"},  # 已通过 → 撤回（拒绝）
    "rejected": {"submit"},  # 重新提审
}


@router.post("/videos/{video_id}/secondary-review", response_model=SecondaryReviewOut)
def secondary_review(
    payload: SecondaryReviewAction,
    video_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
) -> SecondaryReviewOut:
    v = db.get(CtVideo, video_id)
    if v is None:
        raise HTTPException(404, "video not found")
    current = v.secondary_review_status or "draft"
    if payload.action not in _REVIEW_TRANSITIONS.get(current, set()):
        raise HTTPException(
            400,
            f"非法状态流转：{current} → {payload.action}（合法动作 {_REVIEW_TRANSITIONS.get(current, [])}）",
        )

    # 状态转换
    if payload.action == "submit":
        v.secondary_review_status = "pending"
    elif payload.action == "approve":
        v.secondary_review_status = "approved"
    elif payload.action == "reject":
        v.secondary_review_status = "rejected"

    v.secondary_reviewed_by = admin.id
    v.secondary_reviewed_at = datetime.now(UTC)
    if payload.note:
        v.secondary_review_note = payload.note
    db.commit()
    return SecondaryReviewOut.model_validate(v)
