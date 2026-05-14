"""A.T2.1：跨租户隔离测试（红线层级）。

验证 cp 多租户隔离不被 admin app_scope 机制绕过：
- admin app_scope=[tenant_uuid_A] 不能 GET/POST/PATCH/DELETE 属于 App B 的资源
- admin 用 app_scope 内 App 时一切正常
- super_admin (is_super_admin=True) 可见所有 App
- URL 路径注入：path 上是 App A 的 id，但 rule_id 是 App B 的 → 必须 404 不能静默更新

注意：app_scope 是 list[tenant_uuid:str]（不是 app_id），见 deps.get_target_app。
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

# ---------- Fixtures: 多 admin 角色 / 多 App / 多 rule ----------


@pytest.fixture
def super_role(db: Session) -> AdminRole:
    role = AdminRole(
        code=f"super_{datetime.now(UTC).timestamp()}",
        name="super",
        is_super_admin=True,
        is_builtin=True,
        permissions=[],
    )
    db.add(role)
    db.flush()
    return role


@pytest.fixture
def normal_role(db: Session) -> AdminRole:
    role = AdminRole(
        code=f"normal_{datetime.now(UTC).timestamp()}",
        name="normal",
        is_super_admin=False,
        is_builtin=False,
        permissions=[],
    )
    db.add(role)
    db.flush()
    return role


@pytest.fixture
def super_admin(db: Session, super_role: AdminRole) -> AdminUser:
    """super_admin：app_scope=[]（看全部），is_super_admin=True。"""
    admin = AdminUser(
        email=f"super_{datetime.now(UTC).timestamp()}@x.com",
        password_hash="x",
        status="active",
        role_id=super_role.id,
        app_scope=[],
    )
    db.add(admin)
    db.flush()
    db.refresh(admin)
    return admin


@pytest.fixture
def app_a(db: Session, super_admin: AdminUser) -> CpApp:
    a = CpApp(
        tenant_uuid=f"tenant-a-{datetime.now(UTC).timestamp()}",
        name="AppA",
        package_name="com.a.demo",
        owner_admin_user_id=super_admin.id,
        api_key_hash="x",
        hmac_secret="x",
        status="active",
        allowed_upgrade_hosts=["cdn.a.com"],
    )
    db.add(a)
    db.flush()
    return a


@pytest.fixture
def app_b(db: Session, super_admin: AdminUser) -> CpApp:
    b = CpApp(
        tenant_uuid=f"tenant-b-{datetime.now(UTC).timestamp()}",
        name="AppB",
        package_name="com.b.demo",
        owner_admin_user_id=super_admin.id,
        api_key_hash="x",
        hmac_secret="x",
        status="active",
        allowed_upgrade_hosts=["cdn.b.com"],
    )
    db.add(b)
    db.flush()
    return b


@pytest.fixture
def admin_scope_a(
    db: Session, normal_role: AdminRole, app_a: CpApp
) -> AdminUser:
    """普通 admin：app_scope=[app_a.tenant_uuid]，只能访问 A。"""
    admin = AdminUser(
        email=f"scopea_{datetime.now(UTC).timestamp()}@x.com",
        password_hash="x",
        status="active",
        role_id=normal_role.id,
        app_scope=[app_a.tenant_uuid],
    )
    db.add(admin)
    db.flush()
    db.refresh(admin)
    return admin


@pytest.fixture
def admin_scope_b(
    db: Session, normal_role: AdminRole, app_b: CpApp
) -> AdminUser:
    """普通 admin：app_scope=[app_b.tenant_uuid]，只能访问 B。"""
    admin = AdminUser(
        email=f"scopeb_{datetime.now(UTC).timestamp()}@x.com",
        password_hash="x",
        status="active",
        role_id=normal_role.id,
        app_scope=[app_b.tenant_uuid],
    )
    db.add(admin)
    db.flush()
    db.refresh(admin)
    return admin


@pytest.fixture
def rule_b(db: Session, app_b: CpApp, super_admin: AdminUser) -> CpUpgradeRule:
    """属于 App B 的一条规则；用于跨租户访问/修改场景。"""
    rule = CpUpgradeRule(
        app_id=app_b.id,
        name="rule-of-b",
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
    db.flush()
    db.refresh(rule)
    return rule


def _make_client(db: Session, current_admin: AdminUser) -> TestClient:
    """构造 TestClient + override get_db / get_current_admin。"""
    test_app = FastAPI()
    test_app.include_router(api_v1)

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    def _override_get_current_admin() -> AdminUser:
        return current_admin

    test_app.dependency_overrides[get_db] = _override_get_db
    test_app.dependency_overrides[get_current_admin] = _override_get_current_admin

    return TestClient(test_app)


# ---------- 用例 1：scope=A，不能读 App B 详情 ----------


def test_admin_with_app_a_scope_cannot_read_app_b(
    db: Session, admin_scope_a: AdminUser, app_b: CpApp
):
    db.commit()
    client = _make_client(db, admin_scope_a)
    resp = client.get(f"/api/v1/admin/cp/apps/{app_b.id}")
    assert resp.status_code in (403, 404), resp.text


# ---------- 用例 2：scope=A，不能列 App B 的 channels ----------


def test_admin_with_app_a_scope_cannot_list_app_b_channels(
    db: Session, admin_scope_a: AdminUser, app_b: CpApp
):
    # 给 B 加一个 channel，确认跨租户 admin 看不到
    ch = CpChannel(
        app_id=app_b.id,
        code="direct",
        name="DIRECT",
        is_play_store=False,
        signing_strategy="walle",
        enabled=True,
        priority=10,
    )
    db.add(ch)
    db.commit()

    client = _make_client(db, admin_scope_a)
    resp = client.get(f"/api/v1/admin/cp/apps/{app_b.id}/channels")
    assert resp.status_code in (403, 404), resp.text


# ---------- 用例 3：scope=A，不能在 App B 下创建 channel ----------


def test_admin_with_app_a_scope_cannot_create_channel_in_app_b(
    db: Session, admin_scope_a: AdminUser, app_b: CpApp
):
    db.commit()
    client = _make_client(db, admin_scope_a)
    payload = {
        "code": "intruder",
        "name": "Intruder",
        "is_play_store": False,
        "signing_strategy": "walle",
        "enabled": True,
        "priority": 10,
    }
    resp = client.post(f"/api/v1/admin/cp/apps/{app_b.id}/channels", json=payload)
    assert resp.status_code in (403, 404), resp.text

    # 确认 App B 下不会被偷偷写入
    db.expire_all()
    rows = (
        db.query(CpChannel)
        .filter(CpChannel.app_id == app_b.id, CpChannel.code == "intruder")
        .all()
    )
    assert rows == []


# ---------- 用例 4：scope=A，按 id 猜 App B 的 rule → 403/404 ----------


def test_admin_with_app_a_scope_cannot_read_app_b_rule_by_id(
    db: Session, admin_scope_a: AdminUser, app_b: CpApp, rule_b: CpUpgradeRule
):
    """admin scope=A，正确的 rule_id 但属于 App B → 不能读（避免猜 id 攻击）。"""
    db.commit()
    client = _make_client(db, admin_scope_a)
    # 注意：这里走 App B 的路径（get_target_app 应在 admin scope 阶段就拦下）
    resp = client.get(f"/api/v1/admin/cp/apps/{app_b.id}/rules/{rule_b.id}")
    # rules 没有 GET-by-id（admin.py 只有 list）；
    # 但路径 /apps/{app_b.id}/rules 列表也应在 get_target_app 阶段被拦
    # 因此 404（路径不存在）或 403/404 都接受；关键是 admin scope 拦截优先于 200
    assert resp.status_code in (403, 404, 405), resp.text


# ---------- 用例 5：scope=A，PATCH App B 的 rule → 403/404 ----------


def test_admin_with_app_a_scope_cannot_patch_app_b_rule(
    db: Session, admin_scope_a: AdminUser, app_b: CpApp, rule_b: CpUpgradeRule
):
    db.commit()
    original_name = rule_b.name

    client = _make_client(db, admin_scope_a)
    payload = {"name": "hijacked-by-a"}
    resp = client.patch(
        f"/api/v1/admin/cp/apps/{app_b.id}/rules/{rule_b.id}", json=payload
    )
    assert resp.status_code in (403, 404), resp.text

    # 确认 rule_b 没被改
    db.expire_all()
    rule_after = db.get(CpUpgradeRule, rule_b.id)
    assert rule_after is not None
    assert rule_after.name == original_name


# ---------- 用例 6：scope=B 可读自己的 App ----------


def test_admin_with_app_b_scope_can_read_own_app(
    db: Session, admin_scope_b: AdminUser, app_b: CpApp
):
    db.commit()
    client = _make_client(db, admin_scope_b)
    resp = client.get(f"/api/v1/admin/cp/apps/{app_b.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == app_b.id
    assert body["name"] == "AppB"


# ---------- 用例 7：super_admin 可读所有 App ----------


def test_super_admin_can_read_all_apps(
    db: Session, super_admin: AdminUser, app_a: CpApp, app_b: CpApp
):
    """app_scope=[] 且 is_super_admin=True → 任何 App 都能读。"""
    db.commit()
    client = _make_client(db, super_admin)

    resp_a = client.get(f"/api/v1/admin/cp/apps/{app_a.id}")
    assert resp_a.status_code == 200, resp_a.text
    assert resp_a.json()["id"] == app_a.id

    resp_b = client.get(f"/api/v1/admin/cp/apps/{app_b.id}")
    assert resp_b.status_code == 200, resp_b.text
    assert resp_b.json()["id"] == app_b.id


# ---------- 用例 8：URL 路径 app_id 与 rule_id 不属于同一租户 ----------


def test_url_path_injection_app_id_mismatch(
    db: Session, admin_scope_a: AdminUser, app_a: CpApp, rule_b: CpUpgradeRule
):
    """admin scope=A，URL 是 /apps/{app_a.id}/rules/{rule_b.id}
    （path 上是 A 的 app_id 但 rule_id 是 B 的）→ 必须 404，
    严禁在通过 get_target_app 后用 rule_id 直查到 B 的 rule 然后静默更新。
    """
    db.commit()
    original_name = rule_b.name

    client = _make_client(db, admin_scope_a)
    payload = {"name": "cross-tenant-hijack"}
    resp = client.patch(
        f"/api/v1/admin/cp/apps/{app_a.id}/rules/{rule_b.id}", json=payload
    )
    # 关键断言：不能是 200（即不允许跨租户静默修改）
    assert resp.status_code != 200, (
        f"红线 bug：URL path app_id={app_a.id} 是合法 scope，"
        f"但 rule_id={rule_b.id} 属于另一租户 App B，竟然 200 → 跨租户 PATCH 漏洞！"
    )
    # admin.py update_rule 显式检查 rule.app_id != app.id → 404 rule not found
    assert resp.status_code == 404, resp.text

    # 数据一致性：rule_b 未被改
    db.expire_all()
    rule_after = db.get(CpUpgradeRule, rule_b.id)
    assert rule_after is not None
    assert rule_after.name == original_name


# ---------- 额外：list_apps 也要按 scope 过滤（防 admin 看到全部 App 列表） ----------


def test_admin_list_apps_only_returns_scoped_apps(
    db: Session, admin_scope_a: AdminUser, app_a: CpApp, app_b: CpApp
):
    db.commit()
    client = _make_client(db, admin_scope_a)
    resp = client.get("/api/v1/admin/cp/apps")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    returned_ids = {item["id"] for item in body["items"]}
    assert app_a.id in returned_ids, "scope 内 App 应可见"
    assert app_b.id not in returned_ids, "跨租户 App 不应出现在列表里（红线）"
