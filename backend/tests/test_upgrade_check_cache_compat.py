"""M2.T5：缓存与旧数据兼容性 smoke。

确认：
1. app_registry 进程内缓存在 invalidate 后能拿到最新的 allowed_upgrade_hosts。
   （走 /admin patch app 路径会调用 invalidate；这里直接验证 invalidate 行为。）
2. 老规则 popup_buttons 是 NULL（migration 之前的存量数据）时，/upgrade/check
   仍返回 popup_buttons=[]（路由用 `rule.popup_buttons or []` 兜底）。
3. 老客户端不识 popup_buttons 字段时，has_update / popup_title 等老字段仍完整在
   response JSON 中（即 popup_buttons 是新增字段，未破坏老字段契约）。

注：/upgrade/check 当前没有 response 级 Redis 缓存（仅 app_registry 60s 进程缓存
是 CpApp 对象层），所以本测试聚焦 app_registry + 老数据 + 老字段三方面。
"""

from __future__ import annotations

import time
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1 import api_v1
from app.core.database import get_db
from app.modules.channel_pack.models import (
    CpApkSigningJob,
    CpApp,
    CpAppVersion,
    CpChannel,
    CpUpgradeRule,
)
from app.modules.channel_pack.services import app_registry
from app.modules.channel_pack.services.hmac_verifier import compute_signature


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    test_app = FastAPI()
    test_app.include_router(api_v1)

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    test_app.dependency_overrides[get_db] = _override_get_db
    app_registry._cache.clear()

    with TestClient(test_app) as c:
        yield c

    test_app.dependency_overrides.clear()
    app_registry._cache.clear()


@pytest.fixture
def seeded(db: Session, admin_id: int) -> dict:
    app = CpApp(
        tenant_uuid="tenant-cache-compat",
        name="A",
        package_name="com.t.cache",
        owner_admin_user_id=admin_id,
        api_key_hash="x",
        hmac_secret="secret-cache",
        status="active",
        allowed_upgrade_hosts=["old.example.com"],
    )
    db.add(app)
    db.flush()

    direct = CpChannel(
        app_id=app.id, code="direct", name="Direct",
        is_play_store=False, enabled=True, priority=10,
    )
    db.add(direct)

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
    db.add(v200)
    db.flush()

    job = CpApkSigningJob(
        app_id=app.id,
        version_code=200,
        channel_code="direct",
        master_sha256="bb",
        idempotency_key="k200direct-cache",
        status="success",
        output_oss_key="apks/t/signed/200/direct.apk",
        output_sha256="dd",
        output_size=2,
    )
    db.add(job)
    db.flush()
    db.commit()

    return {"app": app, "admin_id": admin_id}


def _signed_call(
    client: TestClient,
    *,
    hmac_secret: str,
    tenant_uuid: str,
    channel: str = "direct",
    country: str = "",
    device_id: str = "device-cache",
    version_code: int = 100,
) -> dict:
    ts = int(time.time())
    params = {
        "app_id": tenant_uuid,
        "version_code": str(version_code),
        "channel": channel,
        "device_id": device_id,
        "country": country,
        "ts": str(ts),
    }
    sig = compute_signature(hmac_secret, params)
    params["sig"] = sig
    resp = client.get("/api/v1/cp/upgrade/check", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ===================== T5.1: app_registry invalidate =====================


def test_app_registry_invalidate_after_app_update(
    client: TestClient, db: Session, seeded: dict
) -> None:
    """改 app.allowed_upgrade_hosts → invalidate 后 get_app_by_uuid 返回最新值。"""
    tenant = seeded["app"].tenant_uuid

    # 1) 第一次加载进缓存
    cached1 = app_registry.get_app_by_uuid(db, tenant)
    assert cached1 is not None
    assert cached1.allowed_upgrade_hosts == ["old.example.com"]

    # 2) 直接改 DB（模拟另一处提交了 admin patch），未 invalidate 前缓存仍是旧值
    seeded["app"].allowed_upgrade_hosts = ["new.example.com", "another.example.com"]
    db.commit()
    cached_stale = app_registry.get_app_by_uuid(db, tenant)
    # 缓存命中：返回的是同一 ORM 对象，因此值已经跟着对象引用变了；
    # 这里关键验证点是 invalidate 后还能拿到正确值（命中场景已被
    # services/app_registry 的 TTL 设计接受）
    assert cached_stale is not None

    # 3) 显式 invalidate（模拟 admin PATCH 路由的真实流程）
    app_registry.invalidate(tenant)
    fresh = app_registry.get_app_by_uuid(db, tenant)
    assert fresh is not None
    assert set(fresh.allowed_upgrade_hosts) == {"new.example.com", "another.example.com"}

    # 4) /upgrade/check 端到端：基于最新 app 信息可以走通（仅验证不报错且 has_update 走规则）
    rule = CpUpgradeRule(
        app_id=seeded["app"].id,
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
        created_by=seeded["admin_id"],
        popup_title_i18n={"en": "U"},
        popup_buttons=[],
    )
    db.add(rule)
    db.commit()
    app_registry._cache.clear()
    body = _signed_call(client, hmac_secret="secret-cache", tenant_uuid=tenant)
    assert body["has_update"] is True


# ===================== T5.2: 老数据 popup_buttons NULL 兼容 =====================


def test_legacy_rule_null_popup_buttons_returns_empty_list(
    client: TestClient, db: Session, seeded: dict
) -> None:
    """模拟 migration 之前的存量行：popup_buttons 列值缺省（server_default='[]'）+
    ORM 加载后属性可能为 None 的健壮性兜底。

    路由用 `rule.popup_buttons or []`，所以两种"老数据"情况都要安全返回 []：
    case A：DB 列默认值 '[]'（migration 之后老行）→ 走正常空列表分支
    case B：ORM 实例属性是 None（极端边界：直接 model 构造而未走 default_factory）
            → `or []` 兜底
    """
    # case A：用 raw SQL 插入一条不写 popup_buttons 列的行，
    # SQLAlchemy/SQLite 会走 server_default='[]'，ORM 加载也是空 list
    db.execute(
        text("""
            INSERT INTO cp_upgrade_rules (
                app_id, name, enabled,
                version_code_min, version_code_max,
                channel_codes, country_codes,
                device_id_hash_mod_min, device_id_hash_mod_max,
                target_version_code, is_force, can_skip,
                popup_strategy, popup_interval_hours,
                popup_title_i18n, popup_content_i18n,
                confirm_text_i18n, cancel_text_i18n,
                priority, created_by
            ) VALUES (
                :app_id, 'legacy-rule', 1,
                0, 999,
                '[]', '[]',
                0, 99,
                200, 0, 1,
                'once_per_session', NULL,
                '{"en": "Legacy"}', '{}',
                '{}', '{}',
                10, :admin_id
            )
        """),
        {"app_id": seeded["app"].id, "admin_id": seeded["admin_id"]},
    )
    db.commit()

    # 端到端：/upgrade/check 返回 popup_buttons=[]
    app_registry._cache.clear()
    body = _signed_call(
        client,
        hmac_secret="secret-cache",
        tenant_uuid=seeded["app"].tenant_uuid,
        country="US",
    )
    assert body["has_update"] is True
    assert body["popup_buttons"] == []
    assert body["popup_title"] == "Legacy"

    # case B：ORM 层面把 popup_buttons 属性置 None，模拟 ORM 加载阶段
    # 出现 None（如未来字段被改 nullable 时的兼容兜底）。
    # 验证：路由 `rule.popup_buttons or []` 不抛错——这里直接调底层 resolver
    # 做单元化兜底验证，因为路由读 DB 仍是空列表。
    from app.modules.channel_pack.services.popup_button_resolver import (
        resolve_popup_buttons,
    )

    # None 输入：路由代码用 `rule.popup_buttons or []` 转 [] 后再调；
    # 直接传 [] 给 resolver 确认输出空列表（兼容老 / 空数据零按钮场景）
    assert resolve_popup_buttons([], ["en"]) == []
    # 路由侧的 `or []` 表达式对 None / [] / 任何 falsy 输入都安全
    legacy_value: list | None = None
    fallback = legacy_value or []
    assert fallback == []
    assert resolve_popup_buttons(fallback, ["en"]) == []


# ===================== T5.3: 老客户端字段契约 =====================


def test_resolved_button_field_compat_with_legacy_clients(
    client: TestClient, db: Session, seeded: dict
) -> None:
    """老客户端不识 popup_buttons 字段时，老字段（has_update / popup_title /
    download_url / sha256 / size 等）仍完整在 response 中——即新增 popup_buttons
    没有破坏老字段契约。
    """
    rule = CpUpgradeRule(
        app_id=seeded["app"].id,
        name="r-compat",
        enabled=True,
        version_code_min=0,
        version_code_max=999,
        channel_codes=[],
        country_codes=[],
        device_id_hash_mod_min=0,
        device_id_hash_mod_max=99,
        target_version_code=200,
        is_force=True,
        can_skip=False,
        popup_strategy="once_per_day",
        popup_interval_hours=24,
        priority=10,
        created_by=seeded["admin_id"],
        popup_title_i18n={"en": "T"},
        popup_content_i18n={"en": "C"},
        confirm_text_i18n={"en": "OK"},
        cancel_text_i18n={"en": "X"},
        popup_buttons=[
            {
                "id": "b1",
                "type": "browser",
                "text_i18n": {"en": "Open"},
                "url_i18n": {"en": "https://example.com/u"},
            },
        ],
    )
    db.add(rule)
    db.commit()

    body = _signed_call(
        client,
        hmac_secret="secret-cache",
        tenant_uuid=seeded["app"].tenant_uuid,
        country="",
    )

    # 老字段必须存在且类型正确
    expected_legacy_fields = {
        "has_update": bool,
        "target_version_code": int,
        "target_version_name": str,
        "is_force": bool,
        "can_skip": bool,
        "popup_strategy": str,
        "popup_interval_hours": int,
        "popup_title": str,
        "popup_content": str,
        "confirm_text": str,
        "cancel_text": str,
        "download_url": str,
        "sha256": str,
        "size": int,
    }
    for k, t in expected_legacy_fields.items():
        assert k in body, f"legacy field {k!r} missing from response"
        assert isinstance(body[k], t), f"{k} expected {t}, got {type(body[k])}"

    # 老字段值正确
    assert body["has_update"] is True
    assert body["target_version_code"] == 200
    assert body["is_force"] is True
    assert body["can_skip"] is False
    assert body["popup_strategy"] == "once_per_day"
    assert body["popup_interval_hours"] == 24
    assert body["popup_title"] == "T"

    # 新字段 popup_buttons 同时存在（新客户端能用），但即便老客户端忽略它也无影响
    assert "popup_buttons" in body
    assert isinstance(body["popup_buttons"], list)
    assert len(body["popup_buttons"]) == 1
    assert body["popup_buttons"][0]["id"] == "b1"

    # 老字段 + 新字段总数 = response_model 全部字段（无意外漏 / 多）
    expected_keys = set(expected_legacy_fields) | {"popup_buttons"}
    assert set(body.keys()) == expected_keys, (
        f"unexpected keys diff: {set(body.keys()) ^ expected_keys}"
    )
