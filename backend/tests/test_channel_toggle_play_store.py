"""M1.T10：admin 端 update_channel is_play_store False→True 切换接入 C1 兜底。

覆盖：
- 无违规规则 → PATCH 成功 200，is_play_store=True 落库
- 现有规则有 inapp_apk → 409，detail 含 violations 列表
- 当前已经 True 再 True → 不走 rescan（200 通过）
- True→False 不需要 rescan → 200
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
    db.refresh(admin)
    return admin


@pytest.fixture
def client(db: Session, super_admin: AdminUser) -> Generator[TestClient, None, None]:
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
    code: str = "gp",
    is_play_store: bool = False,
    enabled: bool = True,
) -> CpChannel:
    ch = CpChannel(
        app_id=app_id,
        code=code,
        name=code.upper(),
        is_play_store=is_play_store,
        signing_strategy="play_signed" if is_play_store else "walle",
        enabled=enabled,
        priority=10,
    )
    db.add(ch)
    db.flush()
    return ch


def _make_rule(
    db: Session,
    app_id: int,
    super_admin: AdminUser,
    *,
    name: str = "r1",
    channel_codes: list[str] | None = None,
    popup_buttons: list[dict] | None = None,
) -> CpUpgradeRule:
    rule = CpUpgradeRule(
        app_id=app_id,
        name=name,
        enabled=True,
        version_code_min=1,
        version_code_max=99,
        channel_codes=channel_codes if channel_codes is not None else [],
        country_codes=[],
        target_version_code=100,
        popup_buttons=popup_buttons if popup_buttons is not None else [],
        created_by=super_admin.id,
    )
    db.add(rule)
    db.flush()
    return rule


def test_toggle_no_violations_passes_200(
    client: TestClient, db: Session, super_admin: AdminUser
) -> None:
    """无违规规则 → PATCH 成功 200，is_play_store=True 落库。"""
    app = _make_app(db, super_admin, allowed_hosts=["cdn.example.com"])
    channel = _make_channel(db, app.id, code="gp", is_play_store=False)
    # 一条只含合法 browser 按钮的规则
    _make_rule(
        db,
        app.id,
        super_admin,
        name="clean-rule",
        channel_codes=[],
        popup_buttons=[
            {
                "id": "open",
                "type": "browser",
                "text_i18n": {"en": "Open"},
                "url_i18n": {"en": "https://cdn.example.com/page"},
            }
        ],
    )
    db.commit()

    resp = client.patch(
        f"/api/v1/admin/cp/apps/{app.id}/channels/{channel.id}",
        json={"is_play_store": True},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_play_store"] is True

    db.expire_all()
    refreshed = db.get(CpChannel, channel.id)
    assert refreshed is not None
    assert refreshed.is_play_store is True


def test_toggle_with_inapp_apk_existing_rule_409_with_violations(
    client: TestClient, db: Session, super_admin: AdminUser
) -> None:
    """现有规则有 inapp_apk button → 409，detail 含 violations 列表。规则与渠道未被改。"""
    app = _make_app(db, super_admin, allowed_hosts=["cdn.example.com"])
    channel = _make_channel(db, app.id, code="gp", is_play_store=False)
    bad_rule = _make_rule(
        db,
        app.id,
        super_admin,
        name="has-inapp",
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
    db.commit()

    resp = client.patch(
        f"/api/v1/admin/cp/apps/{app.id}/channels/{channel.id}",
        json={"is_play_store": True},
    )
    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert body["detail"]["message"] == "切换前请清理违规规则"
    violations = body["detail"]["violations"]
    assert len(violations) == 1
    assert violations[0]["rule_id"] == bad_rule.id
    assert violations[0]["rule_name"] == "has-inapp"
    assert "play_store_channel_rejects_inapp_apk" in violations[0]["reason"]

    # 渠道未被改
    db.expire_all()
    refreshed = db.get(CpChannel, channel.id)
    assert refreshed is not None
    assert refreshed.is_play_store is False


def test_toggle_already_true_to_true_no_rescan_passes(
    client: TestClient, db: Session, super_admin: AdminUser
) -> None:
    """当前已经 True 再 True → 不走 rescan（即使存在违规规则也 200 通过）。"""
    app = _make_app(db, super_admin, allowed_hosts=["cdn.example.com"])
    # 渠道一开始就是 Play
    channel = _make_channel(db, app.id, code="gp", is_play_store=True)
    # 注意：apply-to-all 的 inapp_apk 规则若被 rescan 一定会违规；这里测它不被扫
    _make_rule(
        db,
        app.id,
        super_admin,
        name="would-violate-if-rescanned",
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
    db.commit()

    resp = client.patch(
        f"/api/v1/admin/cp/apps/{app.id}/channels/{channel.id}",
        json={"is_play_store": True, "name": "GP-Renamed"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_play_store"] is True
    assert body["name"] == "GP-Renamed"


def test_toggle_true_to_false_no_check_passes(
    client: TestClient, db: Session, super_admin: AdminUser
) -> None:
    """True→False 不需要 rescan → 200（哪怕规则里有 inapp_apk 也不该触发 409）。"""
    app = _make_app(db, super_admin, allowed_hosts=["cdn.example.com"])
    channel = _make_channel(db, app.id, code="gp", is_play_store=True)
    _make_rule(
        db,
        app.id,
        super_admin,
        name="inapp-rule",
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
    db.commit()

    resp = client.patch(
        f"/api/v1/admin/cp/apps/{app.id}/channels/{channel.id}",
        json={"is_play_store": False},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_play_store"] is False

    db.expire_all()
    refreshed = db.get(CpChannel, channel.id)
    assert refreshed is not None
    assert refreshed.is_play_store is False
