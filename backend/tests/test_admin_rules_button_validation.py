"""M1.T8：admin 端 create_rule / update_rule 接入 validate_buttons_for_app。

覆盖：
- POST /apps/{app_id}/rules 当 app 有 Play 渠道、channel_codes=[]、按钮含 inapp_apk → 422
- POST 当按钮 host 不在白名单 → 422
- POST 当按钮 url 非 https → 422
- POST 合法按钮（非 Play 渠道 + 白名单 + https） → 201
- PATCH 原规则空按钮、追加违规按钮 → 422
- GET 老规则（popup_buttons=[]）返回空数组而非 null
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1 import api_v1
from app.core.database import get_db
from app.core.deps import get_current_admin
from app.modules.admin.models import AdminRole, AdminUser
from app.modules.channel_pack.models import CpApp, CpChannel, CpUpgradeRule


@pytest.fixture
def super_admin(db: Session) -> AdminUser:
    role = AdminRole(
        code=f"super_{datetime.now(UTC).timestamp()}",
        name="super",
        is_super_admin=True,
        is_builtin=True,
        permissions=[],
    )
    db.add(role)
    db.flush()
    admin = AdminUser(
        email=f"a{datetime.now(UTC).timestamp()}@x.com",
        password_hash="x",
        status="active",
        role_id=role.id,
    )
    db.add(admin)
    db.flush()
    # 让 admin.role 关系可访问（lazy load 会再开会话；这里 flush 后直接 attach）
    db.refresh(admin)
    return admin


@pytest.fixture
def client(db: Session, super_admin: AdminUser) -> Generator[TestClient, None, None]:
    """构造仅装载 api_v1 的 FastAPI 实例，覆盖 get_db / get_current_admin。"""
    test_app = FastAPI()
    test_app.include_router(api_v1)

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    def _override_get_current_admin() -> AdminUser:
        return super_admin

    test_app.dependency_overrides[get_db] = _override_get_db
    test_app.dependency_overrides[get_current_admin] = _override_get_current_admin

    with TestClient(test_app) as c:
        yield c

    test_app.dependency_overrides.clear()


def _make_app(db: Session, super_admin: AdminUser, allowed_hosts: list[str]) -> CpApp:
    app = CpApp(
        tenant_uuid=f"t-{datetime.now(UTC).timestamp()}",
        name="A",
        package_name="com.a.b",
        owner_admin_user_id=super_admin.id,
        api_key_hash="x",
        hmac_secret="x",
        status="active",
        allowed_upgrade_hosts=allowed_hosts,
    )
    db.add(app)
    db.flush()
    return app


def _make_channel(
    db: Session,
    app_id: int,
    *,
    code: str = "direct",
    is_play_store: bool = False,
    enabled: bool = True,
) -> CpChannel:
    ch = CpChannel(
        app_id=app_id,
        code=code,
        name=code.upper(),
        is_play_store=is_play_store,
        signing_strategy="walle" if not is_play_store else "play_signed",
        enabled=enabled,
        priority=10,
    )
    db.add(ch)
    db.flush()
    return ch


def _rule_payload(
    *,
    name: str = "r1",
    channel_codes: list[str] | None = None,
    popup_buttons: list[dict] | None = None,
    target_version_code: int = 100,
) -> dict:
    return {
        "name": name,
        "enabled": True,
        "version_code_min": 1,
        "version_code_max": 99,
        "channel_codes": channel_codes if channel_codes is not None else [],
        "country_codes": [],
        "device_id_hash_mod_min": 0,
        "device_id_hash_mod_max": 99,
        "target_version_code": target_version_code,
        "is_force": False,
        "can_skip": True,
        "popup_strategy": "once_per_session",
        "popup_buttons": popup_buttons if popup_buttons is not None else [],
        "priority": 10,
    }


def test_post_rule_play_channel_inapp_apk_422(
    client: TestClient, db: Session, super_admin: AdminUser
):
    """app 有启用的 Play 渠道，规则 channel_codes=[]（apply-to-all），button=inapp_apk → 422"""
    app = _make_app(db, super_admin, allowed_hosts=["cdn.example.com"])
    _make_channel(db, app.id, code="gp", is_play_store=True, enabled=True)
    _make_channel(db, app.id, code="direct", is_play_store=False, enabled=True)
    db.commit()

    payload = _rule_payload(
        channel_codes=[],
        popup_buttons=[
            {
                "id": "install",
                "type": "inapp_apk",
                "text_i18n": {"en": "Install"},
                "url_i18n": {"en": "https://cdn.example.com/a.apk"},
            }
        ],
    )
    resp = client.post(f"/api/v1/admin/cp/apps/{app.id}/rules", json=payload)
    assert resp.status_code == 422, resp.text
    assert "play_store_channel_rejects_inapp_apk" in resp.json()["detail"]


def test_post_rule_host_not_whitelisted_422(
    client: TestClient, db: Session, super_admin: AdminUser
):
    """allowed_upgrade_hosts=['ok.com']，按钮 url host=bad.com → 422"""
    app = _make_app(db, super_admin, allowed_hosts=["ok.com"])
    _make_channel(db, app.id, code="direct", is_play_store=False, enabled=True)
    db.commit()

    payload = _rule_payload(
        channel_codes=[],
        popup_buttons=[
            {
                "id": "b1",
                "type": "browser",
                "text_i18n": {"en": "Open"},
                "url_i18n": {"en": "https://bad.com/x"},
            }
        ],
    )
    resp = client.post(f"/api/v1/admin/cp/apps/{app.id}/rules", json=payload)
    assert resp.status_code == 422, resp.text
    assert "host_not_in_whitelist" in resp.json()["detail"]
    assert "bad.com" in resp.json()["detail"]


def test_post_rule_https_only_422(client: TestClient, db: Session, super_admin: AdminUser):
    """按钮 url='http://ok.com/x' → 422"""
    app = _make_app(db, super_admin, allowed_hosts=["ok.com"])
    _make_channel(db, app.id, code="direct", is_play_store=False, enabled=True)
    db.commit()

    payload = _rule_payload(
        channel_codes=[],
        popup_buttons=[
            {
                "id": "b1",
                "type": "browser",
                "text_i18n": {"en": "Open"},
                "url_i18n": {"en": "http://ok.com/x"},
            }
        ],
    )
    resp = client.post(f"/api/v1/admin/cp/apps/{app.id}/rules", json=payload)
    assert resp.status_code == 422, resp.text
    assert "https_only" in resp.json()["detail"]


def test_post_rule_valid_buttons_201(client: TestClient, db: Session, super_admin: AdminUser):
    """白名单 + https + 非 Play 渠道 → 201"""
    app = _make_app(db, super_admin, allowed_hosts=["cdn.example.com"])
    _make_channel(db, app.id, code="direct", is_play_store=False, enabled=True)
    db.commit()

    payload = _rule_payload(
        channel_codes=["direct"],
        popup_buttons=[
            {
                "id": "open",
                "type": "browser",
                "text_i18n": {"en": "Open"},
                "url_i18n": {"en": "https://cdn.example.com/page"},
            }
        ],
    )
    resp = client.post(f"/api/v1/admin/cp/apps/{app.id}/rules", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["popup_buttons"][0]["id"] == "open"
    assert body["popup_buttons"][0]["url_i18n"]["en"] == "https://cdn.example.com/page"


def test_patch_rule_buttons_revalidated(client: TestClient, db: Session, super_admin: AdminUser):
    """原规则 popup_buttons=[]，PATCH 加入非白名单按钮 → 422，规则不变。"""
    app = _make_app(db, super_admin, allowed_hosts=["ok.com"])
    _make_channel(db, app.id, code="direct", is_play_store=False, enabled=True)
    db.flush()

    rule = CpUpgradeRule(
        app_id=app.id,
        name="r",
        enabled=True,
        version_code_min=1,
        version_code_max=99,
        channel_codes=[],
        country_codes=[],
        target_version_code=100,
        popup_buttons=[],
        created_by=super_admin.id,
    )
    db.add(rule)
    db.commit()

    patch_payload = {
        "popup_buttons": [
            {
                "id": "bad",
                "type": "browser",
                "text_i18n": {"en": "Bad"},
                "url_i18n": {"en": "https://evil.com/x"},
            }
        ]
    }
    resp = client.patch(
        f"/api/v1/admin/cp/apps/{app.id}/rules/{rule.id}", json=patch_payload
    )
    assert resp.status_code == 422, resp.text
    assert "host_not_in_whitelist" in resp.json()["detail"]

    # 数据库里规则未被改（commit 在 raise 之前没发生）
    db.expire_all()
    rule_after = db.get(CpUpgradeRule, rule.id)
    assert rule_after is not None
    assert rule_after.popup_buttons == []


def test_patch_rule_valid_buttons_ok(client: TestClient, db: Session, super_admin: AdminUser):
    """PATCH 合法按钮 → 200，buttons 落库。"""
    app = _make_app(db, super_admin, allowed_hosts=["ok.com"])
    _make_channel(db, app.id, code="direct", is_play_store=False, enabled=True)
    db.flush()

    rule = CpUpgradeRule(
        app_id=app.id,
        name="r",
        enabled=True,
        version_code_min=1,
        version_code_max=99,
        channel_codes=["direct"],
        country_codes=[],
        target_version_code=100,
        popup_buttons=[],
        created_by=super_admin.id,
    )
    db.add(rule)
    db.commit()

    patch_payload = {
        "popup_buttons": [
            {
                "id": "open",
                "type": "browser",
                "text_i18n": {"en": "Open"},
                "url_i18n": {"en": "https://ok.com/x"},
            }
        ]
    }
    resp = client.patch(
        f"/api/v1/admin/cp/apps/{app.id}/rules/{rule.id}", json=patch_payload
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["popup_buttons"][0]["id"] == "open"


def test_get_rule_with_legacy_empty_popup_buttons_returns_empty_list(
    client: TestClient, db: Session, super_admin: AdminUser
):
    """老规则（popup_buttons=[] 兜底）→ GET list 返回 [] 而非 null。"""
    app = _make_app(db, super_admin, allowed_hosts=["ok.com"])
    db.flush()
    rule = CpUpgradeRule(
        app_id=app.id,
        name="legacy",
        enabled=True,
        version_code_min=1,
        version_code_max=99,
        channel_codes=[],
        country_codes=[],
        target_version_code=100,
        popup_buttons=[],
        created_by=super_admin.id,
    )
    db.add(rule)
    db.commit()

    resp = client.get(f"/api/v1/admin/cp/apps/{app.id}/rules")
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["popup_buttons"] == []
