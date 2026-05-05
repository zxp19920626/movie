"""VOD webhook 端点 + admin "Pull from VOD" / "Sync All" / "Reconcile" 触发器。

webhook：阿里云 VOD 控制台事件 → 我方端点（验签后更新 ct_videos.vod_status 等）
admin：手动触发同步 / 对账（不阻塞，返回结果摘要）
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Path, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_admin
from app.core.logging import get_logger
from app.modules.content.models import CtVideo
from app.modules.content.services_vod import (
    apply_vod_event,
    reconcile_videos_against_vod,
    sync_vod_metadata,
)

log = get_logger("vod.webhook")

webhook_router = APIRouter()
admin_vod_router = APIRouter()


def _verify_webhook_signature(body: bytes, provided: str | None) -> bool:
    """阿里云 VOD 事件回调通常 HMAC-SHA1/SHA256 签 body；这里用 SHA256 + base64 简化。
    没设 secret 时 dev 模式直接放行（log warning）。
    """
    secret = settings.vod_webhook_secret
    if not secret:
        log.warning("vod.webhook.no_secret_dev_mode")
        return True
    if not provided:
        return False
    expected = base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(expected, provided)


@webhook_router.post("/vod/webhook")
async def vod_webhook(
    request: Request,
    x_vod_signature: str | None = Header(default=None, alias="X-VOD-Signature"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await request.body()
    if not _verify_webhook_signature(body, x_vod_signature):
        raise HTTPException(401, "signature mismatch")
    try:
        payload = json.loads(body.decode())
    except json.JSONDecodeError as e:
        raise HTTPException(400, "invalid JSON body") from e

    event_type = payload.get("EventType") or payload.get("event_type") or ""
    file_id = payload.get("FileId") or payload.get("file_id") or payload.get("VideoId")
    if not event_type or not file_id:
        raise HTTPException(400, "missing EventType / FileId")

    res = apply_vod_event(db, event_type, file_id, payload)
    log.info("vod.webhook", event_type=event_type, file_id=file_id, **res)
    return {"ok": True, **res}


# ===== 后台手动触发 =====


class VideoPullResp(BaseModel):
    video_id: int
    file_id: str
    new_status: str | None
    note: str = ""


@admin_vod_router.post("/videos/{video_id}/pull-from-vod", response_model=VideoPullResp)
def admin_pull_from_vod(
    video_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> VideoPullResp:
    """单条强制刷新：拿对应 file_id 调 provider.get_media() 更新本地快照。"""
    v = db.get(CtVideo, video_id)
    if v is None:
        raise HTTPException(404, "video not found")
    if not v.vod_file_id:
        raise HTTPException(400, "video has no vod_file_id")

    from app.shared.media_provider.service import get_media_provider

    try:
        provider = get_media_provider()
        info = provider.get_media(v.vod_file_id)
    except (RuntimeError, NotImplementedError) as e:
        return VideoPullResp(
            video_id=video_id, file_id=v.vod_file_id, new_status=None, note=f"stub mode: {e}"
        )
    from datetime import UTC, datetime

    v.vod_status = info.status
    v.vod_duration_sec = info.duration_sec
    v.vod_synced_at = datetime.now(UTC)
    db.commit()
    return VideoPullResp(
        video_id=video_id, file_id=v.vod_file_id, new_status=info.status, note="updated"
    )


class SyncResp(BaseModel):
    queued: bool
    message: str


@admin_vod_router.post("/sync-all", response_model=SyncResp)
def admin_sync_all(
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> SyncResp:
    """全量同步：放后台跑（避免长 HTTP 请求超时）。"""
    background.add_task(sync_vod_metadata, db)
    return SyncResp(queued=True, message="sync_vod_metadata 已排进 BackgroundTasks")


@admin_vod_router.post("/reconcile")
def admin_reconcile(
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
) -> dict:
    """前台触发对账，结果同步返回（小流量阶段；上百万视频时切异步）。"""
    return reconcile_videos_against_vod(db)
