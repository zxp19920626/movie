"""VOD ↔ 本地 ct_videos / ct_video_episodes 同步。

三个调用点：
1. webhook 事件触发：单条更新（incremental）
2. 定时全量 diff：sync_vod_metadata（每天 03:00；MVP 走 BackgroundTasks，后续切 Celery）
3. 对账：reconcile_videos_against_vod（每天输出"本地有 VOD 没"+"VOD 有本地没"两份告警）

stub：当前 IMediaProvider 没有真实现，调用走 NotImplementedError 路径会被 catch 后留 TODO 日志，
不影响主流程。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.modules.content.models import CtVideo, CtVideoEpisode
from app.shared.media_provider.protocol import MediaInfo
from app.shared.media_provider.service import get_media_provider

log = get_logger("content.vod")


def apply_vod_event(db: Session, event_type: str, file_id: str, payload: dict[str, Any]) -> dict:
    """单条 VOD 事件 → 更新 ct_videos / ct_video_episodes 快照字段。

    支持的 event_type（阿里云 VOD 标准事件）：
    - FileUploadComplete：上传完成（status=transcoding）
    - TranscodeComplete：转码完成（status=ready）
    - FileDeleted：源文件删除（status=failed + 业务 status=archived）
    """
    affected = _find_by_file_id(db, file_id)
    if not affected:
        return {"matched": 0, "updated": False, "note": "no local row references this file_id"}

    new_status = {
        "FileUploadComplete": "transcoding",
        "TranscodeComplete": "ready",
        "FileDeleted": "failed",
    }.get(event_type)
    if new_status is None:
        return {"matched": len(affected), "updated": False, "note": f"unknown event {event_type}"}

    duration = payload.get("Duration") or payload.get("duration") or payload.get("duration_sec")
    now = datetime.now(UTC)
    for obj in affected:
        obj.vod_status = new_status
        obj.vod_synced_at = now
        if duration:
            try:
                obj.vod_duration_sec = int(duration)
            except (TypeError, ValueError):
                pass
        # FileDeleted 极端情况：业务状态自动下线（避免用户播失败片）
        if event_type == "FileDeleted" and isinstance(obj, CtVideo):
            obj.status = "archived"
    db.commit()
    return {"matched": len(affected), "updated": True, "new_status": new_status}


def _find_by_file_id(db: Session, file_id: str) -> list[CtVideo | CtVideoEpisode]:
    rows: list[CtVideo | CtVideoEpisode] = []
    rows.extend(db.scalars(select(CtVideo).where(CtVideo.vod_file_id == file_id)).all())
    rows.extend(
        db.scalars(select(CtVideoEpisode).where(CtVideoEpisode.vod_file_id == file_id)).all()
    )
    return rows


def sync_vod_metadata(db: Session, *, batch_size: int = 100) -> dict:
    """全量 diff：拉 list_media 分页 → 对每个文件调 apply_vod_event(TranscodeComplete) 等价更新。

    P4 接入真 SDK 后才能跑通；当前 stub 抛 NotImplementedError，被本函数 catch 写日志返回。
    """
    try:
        provider = get_media_provider()
    except RuntimeError as e:
        log.warning("vod.sync.no_provider", reason=str(e))
        return {"ran": False, "reason": "no provider"}

    total = 0
    updated = 0
    failed = 0
    page = 1
    while True:
        try:
            items = provider.list_media(page=page, page_size=batch_size)
        except NotImplementedError:
            log.info("vod.sync.stub", reason="provider not implemented; pending P4 SDK")
            return {"ran": False, "reason": "stub"}
        except Exception as e:  # noqa: BLE001
            log.error("vod.sync.error", page=page, error=str(e))
            failed += 1
            break
        if not items:
            break
        for it in items:
            total += 1
            res = _apply_media_info(db, it)
            if res:
                updated += 1
        if len(items) < batch_size:
            break
        page += 1
    return {"ran": True, "total": total, "updated": updated, "failed": failed}


def _apply_media_info(db: Session, info: MediaInfo) -> bool:
    rows = _find_by_file_id(db, info.file_id)
    if not rows:
        return False
    now = datetime.now(UTC)
    for r in rows:
        r.vod_status = info.status
        r.vod_duration_sec = info.duration_sec
        r.vod_synced_at = now
    db.commit()
    return True


def reconcile_videos_against_vod(db: Session) -> dict:
    """对账：返回两份列表，运维 / Telegram bot 收到后人工处理。
    - missing_remote: 本地有 vod_file_id 但远程 list_media 没看到 → 可能被人手动删了
    - extra_remote: 远程有但本地无引用 → 上传后没建业务记录（漏单）
    """
    try:
        provider = get_media_provider()
    except RuntimeError:
        return {"ran": False, "reason": "no provider"}

    local_ids: set[str] = set()
    for v in db.scalars(select(CtVideo).where(CtVideo.vod_file_id.is_not(None))).all():
        if v.vod_file_id:
            local_ids.add(v.vod_file_id)
    for ep in db.scalars(
        select(CtVideoEpisode).where(CtVideoEpisode.vod_file_id.is_not(None))
    ).all():
        if ep.vod_file_id:
            local_ids.add(ep.vod_file_id)

    remote_ids: set[str] = set()
    page = 1
    while True:
        try:
            items = provider.list_media(page=page, page_size=200)
        except NotImplementedError:
            return {"ran": False, "reason": "stub"}
        except Exception as e:  # noqa: BLE001
            log.error("vod.reconcile.error", error=str(e))
            return {"ran": False, "reason": str(e)}
        if not items:
            break
        for it in items:
            remote_ids.add(it.file_id)
        if len(items) < 200:
            break
        page += 1

    return {
        "ran": True,
        "local_count": len(local_ids),
        "remote_count": len(remote_ids),
        "missing_remote": sorted(local_ids - remote_ids)[:100],  # 截断防 payload 过大
        "extra_remote": sorted(remote_ids - local_ids)[:100],
    }
