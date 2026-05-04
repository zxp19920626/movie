"""签名 service：fan-out 创建 cp_apk_signing_jobs"""

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.channel_pack.models import (
    CpApkSigningJob,
    CpApp,
    CpAppVersion,
    CpChannel,
)


def compute_idempotency_key(app_id: int, version_code: int, channel_code: str, master_sha256: str) -> str:
    raw = f"{app_id}|{version_code}|{channel_code}|{master_sha256}"
    return hashlib.sha256(raw.encode()).hexdigest()


def fan_out_signing_jobs(
    db: Session,
    app: CpApp,
    version: CpAppVersion,
) -> list[CpApkSigningJob]:
    """为该 version 所有 enabled & 非 Play 渠道创建签名 job（幂等：已存在 success 的不重复）"""

    # 查所有 enabled & 非 play 渠道
    stmt = select(CpChannel).where(
        CpChannel.app_id == app.id,
        CpChannel.enabled.is_(True),
        CpChannel.is_play_store.is_(False),
    )
    channels = list(db.scalars(stmt).all())

    jobs: list[CpApkSigningJob] = []
    for channel in channels:
        idempotency_key = compute_idempotency_key(
            app.id, version.version_code, channel.code, version.master_apk_sha256
        )
        existing = db.scalars(
            select(CpApkSigningJob).where(CpApkSigningJob.idempotency_key == idempotency_key)
        ).one_or_none()
        if existing is not None:
            jobs.append(existing)
            continue
        job = CpApkSigningJob(
            app_id=app.id,
            version_code=version.version_code,
            channel_code=channel.code,
            master_sha256=version.master_apk_sha256,
            idempotency_key=idempotency_key,
            status="pending",
        )
        db.add(job)
        db.flush()
        jobs.append(job)

    if jobs:
        version.status = "signing"
    db.commit()
    return jobs


def check_and_mark_ready(db: Session, app_id: int, version_code: int) -> bool:
    """检查该版本所有 jobs 是否都 success，是则把 cp_app_versions.status 置为 ready"""
    version = db.scalars(
        select(CpAppVersion).where(
            CpAppVersion.app_id == app_id, CpAppVersion.version_code == version_code
        )
    ).one_or_none()
    if version is None:
        return False
    jobs = list(
        db.scalars(
            select(CpApkSigningJob).where(
                CpApkSigningJob.app_id == app_id, CpApkSigningJob.version_code == version_code
            )
        ).all()
    )
    if not jobs:
        return False
    if all(j.status == "success" for j in jobs):
        from datetime import UTC, datetime

        version.status = "ready"
        version.released_at = datetime.now(UTC)
        db.commit()
        return True
    return False
