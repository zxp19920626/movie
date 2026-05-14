"""app_registry 单测：tenant_uuid → CpApp 缓存 + 60s TTL + invalidate 路径。

被测：app.modules.channel_pack.services.app_registry
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.modules.channel_pack.models import CpApp
from app.modules.channel_pack.services import app_registry


@pytest.fixture(autouse=True)
def _clear_registry_cache():
    """每个用例都从空缓存起，避免跨用例串扰。"""
    app_registry._cache.clear()
    yield
    app_registry._cache.clear()


@pytest.fixture
def app_active(db: Session, admin_id: int) -> CpApp:
    a = CpApp(
        tenant_uuid=f"tenant-active-{datetime.now(UTC).timestamp()}",
        name="ActiveApp",
        package_name="com.active.demo",
        owner_admin_user_id=admin_id,
        api_key_hash="x",
        hmac_secret="x",
        status="active",
        allowed_upgrade_hosts=[],
    )
    db.add(a)
    db.flush()
    db.refresh(a)
    return a


@pytest.fixture
def app_suspended(db: Session, admin_id: int) -> CpApp:
    a = CpApp(
        tenant_uuid=f"tenant-suspended-{datetime.now(UTC).timestamp()}",
        name="SuspendedApp",
        package_name="com.suspended.demo",
        owner_admin_user_id=admin_id,
        api_key_hash="x",
        hmac_secret="x",
        status="suspended",
        allowed_upgrade_hosts=[],
    )
    db.add(a)
    db.flush()
    db.refresh(a)
    return a


def test_get_by_uuid_not_exist_returns_none(db: Session) -> None:
    """tenant_uuid 不存在 → 返回 None（实现选 one_or_none，不抛异常）。"""
    assert app_registry.get_app_by_uuid(db, "not-exist-uuid") is None


def test_get_by_uuid_active_returns_row(db: Session, app_active: CpApp) -> None:
    got = app_registry.get_app_by_uuid(db, app_active.tenant_uuid)
    assert got is not None
    assert got.id == app_active.id
    assert got.status == "active"


def test_get_by_uuid_suspended_returns_none(db: Session, app_suspended: CpApp) -> None:
    """status != 'active' 的 App 视为查无（避免给挂起的租户继续派流量）。"""
    assert app_registry.get_app_by_uuid(db, app_suspended.tenant_uuid) is None


def test_cache_hit_returns_same_object(db: Session, app_active: CpApp) -> None:
    """两次连续 get 命中缓存 → 返回同一对象（is 相等，不再走 DB）。"""
    first = app_registry.get_app_by_uuid(db, app_active.tenant_uuid)
    second = app_registry.get_app_by_uuid(db, app_active.tenant_uuid)
    assert first is not None
    assert second is not None
    assert first is second  # 缓存命中 → 同一实例


def test_invalidate_then_get_refetches(db: Session, app_active: CpApp) -> None:
    """invalidate 后再 get → 重新查 DB；通过把 active App 改成 suspended，验证旧缓存被击穿。"""
    first = app_registry.get_app_by_uuid(db, app_active.tenant_uuid)
    assert first is not None  # 第一次：active

    # 直接把 DB 里的 status 改为 suspended（绕过缓存）
    app_active.status = "suspended"
    db.flush()

    # 不 invalidate 的话还会拿到缓存（active），证明缓存确实存在
    cached = app_registry.get_app_by_uuid(db, app_active.tenant_uuid)
    assert cached is not None  # 缓存命中：还是 active

    # invalidate 后重查 → DB 里 status=suspended → 服务过滤掉 → None
    app_registry.invalidate(app_active.tenant_uuid)
    after = app_registry.get_app_by_uuid(db, app_active.tenant_uuid)
    assert after is None, "invalidate 后必须重新查 DB；当前实现拿到 None 说明 status='active' 过滤生效"


def test_invalidate_missing_uuid_safe() -> None:
    """invalidate 不存在的 key 不应抛错（防御性测试边界）。"""
    app_registry.invalidate("nope-uuid-xxx")  # 不抛


def test_cache_miss_on_new_uuid(db: Session, app_active: CpApp) -> None:
    """先查 A，再查 B，不会拿到 A 的缓存。"""
    a = app_registry.get_app_by_uuid(db, app_active.tenant_uuid)
    b = app_registry.get_app_by_uuid(db, "totally-different-uuid")
    assert a is not None
    assert b is None
