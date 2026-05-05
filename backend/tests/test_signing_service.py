"""signing_service：fan_out_signing_jobs 幂等性 + check_and_mark_ready。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.modules.channel_pack.models import (
    CpApkSigningJob,
    CpApp,
    CpAppVersion,
    CpChannel,
)
from app.modules.channel_pack.services.signing_service import (
    check_and_mark_ready,
    compute_idempotency_key,
    fan_out_signing_jobs,
)


@pytest.fixture
def app_with_channels(db: Session, admin_id: int):
    app = CpApp(
        tenant_uuid="t",
        name="A",
        package_name="c.a",
        owner_admin_user_id=admin_id,
        api_key_hash="x",
        hmac_secret="x",
        status="active",
    )
    db.add(app)
    db.flush()
    direct = CpChannel(
        app_id=app.id, code="direct", name="D", is_play_store=False, enabled=True, priority=10
    )
    other = CpChannel(
        app_id=app.id, code="oth", name="O", is_play_store=False, enabled=True, priority=20
    )
    play = CpChannel(
        app_id=app.id, code="gp", name="GP", is_play_store=True, enabled=True, priority=1
    )
    off = CpChannel(
        app_id=app.id, code="off", name="X", is_play_store=False, enabled=False, priority=99
    )
    db.add_all([direct, other, play, off])

    v = CpAppVersion(
        app_id=app.id,
        version_code=10,
        version_name="0.1",
        master_apk_oss_key="apks/t/10.apk",
        master_apk_sha256="sha256-aa",
        master_apk_size=1,
        status="draft",
        uploaded_by=admin_id,
    )
    db.add(v)
    db.flush()
    return {"app": app, "version": v, "admin_id": admin_id}


def test_fan_out_排除_play_和_disabled(db: Session, app_with_channels):
    s = app_with_channels
    jobs = fan_out_signing_jobs(db, s["app"], s["version"])
    codes = {j.channel_code for j in jobs}
    assert codes == {"direct", "oth"}  # play / off 都被排除
    assert s["version"].status == "signing"


def test_idempotency_重复调用不重复创建(db: Session, app_with_channels):
    s = app_with_channels
    a = fan_out_signing_jobs(db, s["app"], s["version"])
    b = fan_out_signing_jobs(db, s["app"], s["version"])
    assert {j.id for j in a} == {j.id for j in b}
    # DB 里仍然只有 2 条
    rows = db.query(CpApkSigningJob).filter_by(app_id=s["app"].id, version_code=10).all()
    assert len(rows) == 2


def test_idempotency_key_纯函数(db: Session, app_with_channels):
    k1 = compute_idempotency_key(1, 10, "direct", "sha256-aa")
    k2 = compute_idempotency_key(1, 10, "direct", "sha256-aa")
    k3 = compute_idempotency_key(1, 10, "direct", "sha256-bb")
    assert k1 == k2
    assert k1 != k3


def test_check_and_mark_ready_部分_success_不置位(db: Session, app_with_channels):
    s = app_with_channels
    jobs = fan_out_signing_jobs(db, s["app"], s["version"])
    jobs[0].status = "success"
    db.flush()
    assert check_and_mark_ready(db, s["app"].id, 10) is False
    assert s["version"].status == "signing"


def test_check_and_mark_ready_全_success_置_ready(db: Session, app_with_channels):
    s = app_with_channels
    jobs = fan_out_signing_jobs(db, s["app"], s["version"])
    for j in jobs:
        j.status = "success"
    db.flush()
    assert check_and_mark_ready(db, s["app"].id, 10) is True
    assert s["version"].status == "ready"
    assert s["version"].released_at is not None


def test_无_jobs_返回_false(db: Session, app_with_channels):
    s = app_with_channels
    assert check_and_mark_ready(db, s["app"].id, 10) is False
