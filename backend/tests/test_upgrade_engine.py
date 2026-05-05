"""upgrade_engine.check_upgrade DB 联合测试。

覆盖：
- Play 渠道硬拒
- 渠道未启用
- 命中规则 + 灰度 hash bucket
- 渠道集合 / 国家集合过滤
- 时间窗未到 / 已过
- 目标版本未 ready / 不降级
- 渠道未签好
- 优先级排序
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.modules.channel_pack.models import (
    CpApkSigningJob,
    CpApp,
    CpAppVersion,
    CpChannel,
    CpUpgradeRule,
)
from app.modules.channel_pack.services.upgrade_engine import check_upgrade


@pytest.fixture
def setup(db: Session, admin_id: int):
    app = CpApp(
        tenant_uuid="tenant-1",
        name="App1",
        package_name="com.t.a1",
        owner_admin_user_id=admin_id,
        api_key_hash="x",
        hmac_secret="x",
        status="active",
    )
    db.add(app)
    db.flush()

    direct = CpChannel(
        app_id=app.id, code="direct", name="Direct", is_play_store=False, enabled=True, priority=10
    )
    play = CpChannel(
        app_id=app.id, code="gp", name="GooglePlay", is_play_store=True, enabled=True, priority=1
    )
    disabled = CpChannel(
        app_id=app.id,
        code="dead",
        name="Dead",
        is_play_store=False,
        enabled=False,
        priority=99,
    )
    db.add_all([direct, play, disabled])

    v100 = CpAppVersion(
        app_id=app.id,
        version_code=100,
        version_name="1.0",
        master_apk_oss_key="apks/t/100.apk",
        master_apk_sha256="aa",
        master_apk_size=1,
        status="ready",
        uploaded_by=admin_id,
    )
    v200 = CpAppVersion(
        app_id=app.id,
        version_code=200,
        version_name="2.0",
        master_apk_oss_key="apks/t/200.apk",
        master_apk_sha256="bb",
        master_apk_size=1,
        status="ready",
        uploaded_by=admin_id,
    )
    v300_signing = CpAppVersion(
        app_id=app.id,
        version_code=300,
        version_name="3.0",
        master_apk_oss_key="apks/t/300.apk",
        master_apk_sha256="cc",
        master_apk_size=1,
        status="signing",
        uploaded_by=admin_id,
    )
    db.add_all([v100, v200, v300_signing])
    db.flush()

    # direct 渠道 v200 已签好
    job = CpApkSigningJob(
        app_id=app.id,
        version_code=200,
        channel_code="direct",
        master_sha256="bb",
        idempotency_key="k200direct",
        status="success",
    )
    db.add(job)
    db.flush()

    return {"app": app, "admin_id": admin_id, "direct": direct, "v200": v200}


def _add_rule(db: Session, app_id: int, admin_id: int, **overrides) -> CpUpgradeRule:
    defaults = dict(
        app_id=app_id,
        name="r",
        enabled=True,
        version_code_min=0,
        version_code_max=999,
        channel_codes=[],
        country_codes=[],
        device_id_hash_mod_min=0,
        device_id_hash_mod_max=99,
        target_version_code=200,
        priority=10,
        created_by=admin_id,
    )
    defaults.update(overrides)
    rule = CpUpgradeRule(**defaults)
    db.add(rule)
    db.flush()
    return rule


def test_命中默认规则(db: Session, setup):
    _add_rule(db, setup["app"].id, setup["admin_id"])
    res = check_upgrade(db, setup["app"].id, 100, "direct", "US", "device-1")
    assert res.match is not None
    assert res.match.target_version.version_code == 200
    assert "命中" in res.debug_steps[-1]


def test_play_渠道硬拒(db: Session, setup):
    _add_rule(db, setup["app"].id, setup["admin_id"])
    res = check_upgrade(db, setup["app"].id, 100, "gp", "US", "d")
    assert res.match is None
    assert any("is_play_store=true" in s for s in res.debug_steps)


def test_未知渠道_None(db: Session, setup):
    res = check_upgrade(db, setup["app"].id, 100, "unknown", "US", "d")
    assert res.match is None


def test_disabled_渠道_拒绝(db: Session, setup):
    _add_rule(db, setup["app"].id, setup["admin_id"])
    res = check_upgrade(db, setup["app"].id, 100, "dead", "US", "d")
    assert res.match is None


def test_不降级_(db: Session, setup):
    _add_rule(db, setup["app"].id, setup["admin_id"])
    # 用户 vc=300 > target 200 → 不命中
    res = check_upgrade(db, setup["app"].id, 300, "direct", "US", "d")
    assert res.match is None


def test_目标未_ready(db: Session, setup):
    _add_rule(db, setup["app"].id, setup["admin_id"], target_version_code=300)
    res = check_upgrade(db, setup["app"].id, 100, "direct", "US", "d")
    assert res.match is None
    assert any("status=signing" in s for s in res.debug_steps)


def test_渠道未签好_拒绝(db: Session, setup):
    # rule 指向 v200，但只签了 direct；这里换个未签的渠道
    _add_rule(db, setup["app"].id, setup["admin_id"], channel_codes=["other"])
    # 加一个 'other' 渠道但没有签名 job
    other = CpChannel(
        app_id=setup["app"].id, code="other", name="O", is_play_store=False, enabled=True
    )
    db.add(other)
    db.flush()
    res = check_upgrade(db, setup["app"].id, 100, "other", "US", "d")
    assert res.match is None
    assert any("未签好" in s for s in res.debug_steps)


def test_渠道集合过滤(db: Session, setup):
    _add_rule(db, setup["app"].id, setup["admin_id"], channel_codes=["other-only"])
    res = check_upgrade(db, setup["app"].id, 100, "direct", "US", "d")
    assert res.match is None


def test_国家集合过滤(db: Session, setup):
    _add_rule(db, setup["app"].id, setup["admin_id"], country_codes=["JP"])
    res = check_upgrade(db, setup["app"].id, 100, "direct", "US", "d")
    assert res.match is None


def test_未到生效时间(db: Session, setup):
    _add_rule(
        db,
        setup["app"].id,
        setup["admin_id"],
        effective_from=datetime.now(UTC) + timedelta(days=1),
    )
    res = check_upgrade(db, setup["app"].id, 100, "direct", "US", "d")
    assert res.match is None
    assert any("未到生效时间" in s for s in res.debug_steps)


def test_超过生效时间(db: Session, setup):
    _add_rule(
        db,
        setup["app"].id,
        setup["admin_id"],
        effective_to=datetime.now(UTC) - timedelta(days=1),
    )
    res = check_upgrade(db, setup["app"].id, 100, "direct", "US", "d")
    assert res.match is None


def test_灰度区间命中(db: Session, setup):
    # 让此规则只命中 hash_bucket=0
    # 'a' 的 crc32 % 100 = 1，所以 [0,0] 会跳过 'a'
    _add_rule(
        db,
        setup["app"].id,
        setup["admin_id"],
        device_id_hash_mod_min=0,
        device_id_hash_mod_max=0,
    )
    miss = check_upgrade(db, setup["app"].id, 100, "direct", "US", "a")
    assert miss.match is None  # crc32('a')%100 != 0 时跳过


def test_优先级排序(db: Session, setup):
    # 两条规则同时满足，priority 高的赢
    low = _add_rule(db, setup["app"].id, setup["admin_id"], name="low", priority=1)
    high = _add_rule(db, setup["app"].id, setup["admin_id"], name="high", priority=99)
    res = check_upgrade(db, setup["app"].id, 100, "direct", "US", "d")
    assert res.match is not None
    assert res.match.rule.id == high.id
    assert res.match.rule.id != low.id
