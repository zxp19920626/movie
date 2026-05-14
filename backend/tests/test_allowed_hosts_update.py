"""M1.T11 — PATCH /apps/{app_id} 更新 allowed_upgrade_hosts 的边沿检测。

覆盖：
- 扩展白名单 → 200
- 缩短但移除的 host 没被任何规则引用 → 200
- 缩短且移除的 host 仍被规则按钮 url 引用 → 409 含 affected_rules
- 完全替换为超集 → 200
- 大小写归一化（输入 'A.COM' → 落库 'a.com'）
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
from app.modules.channel_pack.models import CpApp, CpUpgradeRule


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


def _make_rule_with_button_url(
    db: Session, app_id: int, super_admin_id: int, *, name: str, button_url: str
) -> CpUpgradeRule:
    rule = CpUpgradeRule(
        app_id=app_id,
        name=name,
        enabled=True,
        version_code_min=1,
        version_code_max=99,
        channel_codes=[],
        country_codes=[],
        target_version_code=100,
        popup_buttons=[
            {
                "id": "b1",
                "type": "browser",
                "text_i18n": {"en": "Open"},
                "url_i18n": {"en": button_url},
            }
        ],
        created_by=super_admin_id,
    )
    db.add(rule)
    db.flush()
    return rule


def test_add_new_host_passes(client: TestClient, db: Session, super_admin: AdminUser):
    """旧 ['a.com']，新 ['a.com','b.com'] → 200"""
    app = _make_app(db, super_admin, allowed_hosts=["a.com"])
    db.commit()

    resp = client.patch(
        f"/api/v1/admin/cp/apps/{app.id}",
        json={"allowed_upgrade_hosts": ["a.com", "b.com"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["allowed_upgrade_hosts"] == ["a.com", "b.com"]

    db.expire_all()
    app_after = db.get(CpApp, app.id)
    assert app_after is not None
    assert app_after.allowed_upgrade_hosts == ["a.com", "b.com"]


def test_remove_unused_host_passes(
    client: TestClient, db: Session, super_admin: AdminUser
):
    """旧 ['a.com','b.com']，没有规则引用 b.com，新 ['a.com'] → 200"""
    app = _make_app(db, super_admin, allowed_hosts=["a.com", "b.com"])
    # 规则只引用 a.com
    _make_rule_with_button_url(
        db,
        app.id,
        super_admin.id,
        name="rule_a",
        button_url="https://a.com/page",
    )
    db.commit()

    resp = client.patch(
        f"/api/v1/admin/cp/apps/{app.id}",
        json={"allowed_upgrade_hosts": ["a.com"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["allowed_upgrade_hosts"] == ["a.com"]


def test_remove_host_in_use_409_with_affected_rules(
    client: TestClient, db: Session, super_admin: AdminUser
):
    """规则按钮 url 用 b.com，新 ['a.com']（移除 b.com） → 409 含 affected_rules"""
    app = _make_app(db, super_admin, allowed_hosts=["a.com", "b.com"])
    rule_b = _make_rule_with_button_url(
        db,
        app.id,
        super_admin.id,
        name="rule_using_b",
        button_url="https://b.com/download",
    )
    # 再加一条规则用 a.com，不应该出现在 affected
    _make_rule_with_button_url(
        db,
        app.id,
        super_admin.id,
        name="rule_using_a",
        button_url="https://a.com/page",
    )
    db.commit()

    resp = client.patch(
        f"/api/v1/admin/cp/apps/{app.id}",
        json={"allowed_upgrade_hosts": ["a.com"]},
    )
    assert resp.status_code == 409, resp.text
    detail = resp.json()["detail"]
    assert detail["message"] == "白名单缩短前请清理引用规则"
    assert detail["removed_hosts"] == ["b.com"]
    affected = detail["affected_rules"]
    assert len(affected) == 1
    assert affected[0]["rule_id"] == rule_b.id
    assert affected[0]["rule_name"] == "rule_using_b"
    assert affected[0]["host"] == "b.com"

    # 规则数据库里没改（事务未提交）
    db.expire_all()
    app_after = db.get(CpApp, app.id)
    assert app_after is not None
    assert set(app_after.allowed_upgrade_hosts) == {"a.com", "b.com"}


def test_replace_with_superset_passes(
    client: TestClient, db: Session, super_admin: AdminUser
):
    """旧 ['a.com']，新 ['a.com','b.com','c.com'] → 200"""
    app = _make_app(db, super_admin, allowed_hosts=["a.com"])
    _make_rule_with_button_url(
        db,
        app.id,
        super_admin.id,
        name="r",
        button_url="https://a.com/p",
    )
    db.commit()

    resp = client.patch(
        f"/api/v1/admin/cp/apps/{app.id}",
        json={"allowed_upgrade_hosts": ["a.com", "b.com", "c.com"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["allowed_upgrade_hosts"] == ["a.com", "b.com", "c.com"]


def test_case_normalization_on_save(
    client: TestClient, db: Session, super_admin: AdminUser
):
    """输入 'A.COM' → schema 归一化为 'a.com'，落库小写。"""
    app = _make_app(db, super_admin, allowed_hosts=[])
    db.commit()

    resp = client.patch(
        f"/api/v1/admin/cp/apps/{app.id}",
        json={"allowed_upgrade_hosts": ["A.COM", "B.com"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["allowed_upgrade_hosts"] == ["a.com", "b.com"]

    # GET 也是小写
    resp_get = client.get(f"/api/v1/admin/cp/apps/{app.id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["allowed_upgrade_hosts"] == ["a.com", "b.com"]


def test_patch_other_field_does_not_touch_hosts(
    client: TestClient, db: Session, super_admin: AdminUser
):
    """只 PATCH name 字段时，allowed_upgrade_hosts 视为未传，不会触发缩短检查。"""
    app = _make_app(db, super_admin, allowed_hosts=["a.com", "b.com"])
    _make_rule_with_button_url(
        db,
        app.id,
        super_admin.id,
        name="r",
        button_url="https://b.com/p",
    )
    db.commit()

    resp = client.patch(
        f"/api/v1/admin/cp/apps/{app.id}",
        json={"name": "new name"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "new name"
    assert set(resp.json()["allowed_upgrade_hosts"]) == {"a.com", "b.com"}


def test_clear_to_empty_blocked_when_rules_reference_hosts(
    client: TestClient, db: Session, super_admin: AdminUser
):
    """显式传 [] 清空 → 移除的 host 中有规则引用 → 409"""
    app = _make_app(db, super_admin, allowed_hosts=["a.com"])
    rule = _make_rule_with_button_url(
        db,
        app.id,
        super_admin.id,
        name="rule_a",
        button_url="https://a.com/x",
    )
    db.commit()

    resp = client.patch(
        f"/api/v1/admin/cp/apps/{app.id}",
        json={"allowed_upgrade_hosts": []},
    )
    assert resp.status_code == 409, resp.text
    detail = resp.json()["detail"]
    assert detail["removed_hosts"] == ["a.com"]
    assert detail["affected_rules"][0]["rule_id"] == rule.id
    assert detail["affected_rules"][0]["host"] == "a.com"
