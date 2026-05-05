"""InMemoryCacheService 单测（RedisCacheService 接口对齐，未起 redis 不在 CI 跑）。"""

from __future__ import annotations

import time

import pytest

from app.shared.cache_service import InMemoryCacheService, make_key


@pytest.fixture
def cache() -> InMemoryCacheService:
    return InMemoryCacheService()


def test_set_get_basic(cache: InMemoryCacheService) -> None:
    cache.set("k1", {"a": 1})
    assert cache.get("k1") == {"a": 1}


def test_get_missing_returns_none(cache: InMemoryCacheService) -> None:
    assert cache.get("nope") is None


def test_ttl_过期(cache: InMemoryCacheService) -> None:
    cache.set("k1", "v1", ttl_seconds=1)
    assert cache.get("k1") == "v1"
    time.sleep(1.1)
    assert cache.get("k1") is None


def test_delete(cache: InMemoryCacheService) -> None:
    cache.set("k1", "v")
    cache.delete("k1")
    assert cache.get("k1") is None


def test_delete_missing_safe(cache: InMemoryCacheService) -> None:
    cache.delete("nope")  # 不抛


def test_invalidate_pattern(cache: InMemoryCacheService) -> None:
    cache.set("cp:rules:1", "a")
    cache.set("cp:rules:2", "b")
    cache.set("user:profile:1", "c")
    n = cache.invalidate_pattern("cp:rules:*")
    assert n == 2
    assert cache.get("cp:rules:1") is None
    assert cache.get("cp:rules:2") is None
    assert cache.get("user:profile:1") == "c"


def test_make_key_命名规范() -> None:
    assert make_key("cp", "app_registry", "uuid-x") == "cp:app_registry:uuid-x"
    assert make_key("user", "profile", 42) == "user:profile:42"


def test_incr_首次创建返回1(cache: InMemoryCacheService) -> None:
    assert cache.incr("k1", ttl_seconds=10) == 1


def test_incr_累加(cache: InMemoryCacheService) -> None:
    assert cache.incr("k1", ttl_seconds=10) == 1
    assert cache.incr("k1", ttl_seconds=10) == 2
    assert cache.incr("k1", ttl_seconds=10) == 3


def test_incr_过期重置计数(cache: InMemoryCacheService) -> None:
    cache.incr("k1", ttl_seconds=1)
    cache.incr("k1", ttl_seconds=1)
    time.sleep(1.1)
    # 过期后 +1 → 1（不是 3）
    assert cache.incr("k1", ttl_seconds=10) == 1
