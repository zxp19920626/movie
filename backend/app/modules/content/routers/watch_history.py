"""watch-history App 端 /api/v1/watch-history。

设计：
- POST upsert：(user_id, video_id, episode_id) 唯一键 → 更新 position/duration/updated_at
- 写入后清理：每用户最多保留 200 条最新（PROMPT.md 5.7），超出删旧
- GET 列表：按 updated_at desc 分页
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.modules.content.models import CtVideo, CtVideoEpisode, CtWatchHistory
from app.modules.content.schemas import (
    OkResponse,
    WatchHistoryItem,
    WatchHistoryList,
    WatchHistoryUpsert,
)

router = APIRouter()

MAX_HISTORY_PER_USER = 200


@router.get("", response_model=WatchHistoryList)
def list_watch_history(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> WatchHistoryList:
    stmt = select(CtWatchHistory).where(CtWatchHistory.user_id == user.id)
    total = len(list(db.scalars(stmt).all()))
    items = list(
        db.scalars(
            stmt.order_by(CtWatchHistory.updated_at.desc()).limit(limit).offset(offset)
        ).all()
    )
    return WatchHistoryList(
        items=[WatchHistoryItem.model_validate(it) for it in items], total=total
    )


@router.post("", response_model=WatchHistoryItem)
def upsert_watch_history(
    payload: WatchHistoryUpsert,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> WatchHistoryItem:
    if not db.get(CtVideo, payload.video_id):
        raise HTTPException(404, "video not found")
    if payload.episode_id is not None and not db.get(CtVideoEpisode, payload.episode_id):
        raise HTTPException(404, "episode not found")

    existing = db.scalar(
        select(CtWatchHistory).where(
            CtWatchHistory.user_id == user.id,
            CtWatchHistory.video_id == payload.video_id,
            CtWatchHistory.episode_id == payload.episode_id,
        )
    )
    if existing:
        existing.position_sec = payload.position_sec
        existing.duration_sec = payload.duration_sec
        # updated_at 由 onupdate=func.now() 触发
        db.flush()
        rec = existing
    else:
        rec = CtWatchHistory(
            user_id=user.id,
            video_id=payload.video_id,
            episode_id=payload.episode_id,
            position_sec=payload.position_sec,
            duration_sec=payload.duration_sec,
        )
        db.add(rec)
        db.flush()
        _prune_old(db, user.id)
    db.commit()
    db.refresh(rec)
    return WatchHistoryItem.model_validate(rec)


@router.delete("/{history_id}", response_model=OkResponse)
def delete_watch_history(
    history_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> OkResponse:
    rec = db.get(CtWatchHistory, history_id)
    if rec is None or rec.user_id != user.id:
        raise HTTPException(404, "history not found")
    db.delete(rec)
    db.commit()
    return OkResponse(ok=True)


def _prune_old(db: Session, user_id: int) -> int:
    """保留每用户最近 MAX_HISTORY_PER_USER 条；超出删除最旧。

    实现：按 updated_at desc 取前 N 个 id，把不在这个集合里的删掉。
    SQLite 用子查询；MySQL 也支持。
    """
    # 当前总数
    total = db.scalar(
        select(CtWatchHistory.id)
        .where(CtWatchHistory.user_id == user_id)
        .order_by(CtWatchHistory.updated_at.desc())
        .limit(1)
        .offset(MAX_HISTORY_PER_USER)
    )
    if total is None:
        return 0
    # 至少有 MAX_HISTORY_PER_USER+1 条；删除 offset>=MAX 的
    keep_ids = list(
        db.scalars(
            select(CtWatchHistory.id)
            .where(CtWatchHistory.user_id == user_id)
            .order_by(CtWatchHistory.updated_at.desc())
            .limit(MAX_HISTORY_PER_USER)
        ).all()
    )
    result = db.execute(
        delete(CtWatchHistory).where(
            CtWatchHistory.user_id == user_id,
            CtWatchHistory.id.notin_(keep_ids),
        )
    )
    return result.rowcount or 0
