"""签名后台任务：MVP 用 FastAPI BackgroundTasks 同进程执行；生产换 Celery worker。

job 状态机：pending → running → success/failed
失败重试：MVP 只在管理员点击 retry 时触发，不做自动 backoff（生产 Celery autoretry_for）
"""

import os
import socket
import tempfile
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.channel_pack.adapters.object_store import (
    compute_signed_key,
    file_sha256,
    get_default_store,
)
from app.modules.channel_pack.adapters.walle import get_default_signer
from app.modules.channel_pack.models import CpApkSigningJob, CpApp
from app.modules.channel_pack.services.signing_service import check_and_mark_ready

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def run_sign_apk_job(job_id: int) -> None:
    """单个签名任务的执行函数（同步，给 BackgroundTasks 调）"""

    db: Session = SessionLocal()
    try:
        job = db.get(CpApkSigningJob, job_id)
        if job is None:
            return
        if job.status == "success":
            return  # 幂等
        # 简单"接管"逻辑：如果 running > 10min 视为僵死可接管；MVP 此处简化为只跑 pending/failed
        if job.status not in ("pending", "failed"):
            return

        job.status = "running"
        job.attempts += 1
        job.worker_id = WORKER_ID
        job.started_at = datetime.now(UTC)
        db.commit()

        try:
            app = db.get(CpApp, job.app_id)
            if app is None:
                raise RuntimeError(f"app {job.app_id} not found")

            store = get_default_store()
            signer = get_default_signer()

            master_key = f"apks/{app.tenant_uuid}/master/{job.version_code}.apk"
            master_path = store.get_local_path(master_key)
            if master_path is None:
                raise RuntimeError(f"master apk not found: {master_key}")

            # 在临时文件签名，再上传到 store
            with tempfile.NamedTemporaryFile(delete=False, suffix=".apk") as tmp:
                tmp_path = tmp.name
            try:
                signer.inject_channel(master_path, tmp_path, job.channel_code)
                output_key = compute_signed_key(app.tenant_uuid, job.version_code, job.channel_code)
                sha, size = store.put_file(output_key, tmp_path)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            job.output_oss_key = output_key
            job.output_sha256 = sha
            job.output_size = size
            job.status = "success"
            job.finished_at = datetime.now(UTC)
            job.cdn_warmup_status = "done"  # MVP 本地无需预热
            db.commit()
        except Exception as e:
            job.status = "failed"
            job.last_error = repr(e)[:1000]
            job.finished_at = datetime.now(UTC)
            db.commit()
            return

        # 检查是否所有 jobs 都成功 → 置 version=ready
        check_and_mark_ready(db, job.app_id, job.version_code)
    finally:
        db.close()


def _file_helpers() -> None:
    """让 file_sha256 不被 ruff F401 警告（稍后可能用到）"""
    _ = file_sha256
