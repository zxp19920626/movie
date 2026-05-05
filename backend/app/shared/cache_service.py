from __future__ import annotations

import fnmatch
import threading
import time
from typing import Any, Protocol


class ICacheService(Protocol):
    """缓存抽象。

    Key 命名规范：`<module>:<resource>:<id>` 例：`cp:app_registry:tenant-uuid-xxx`。
    invalidate_pattern 支持 glob（fnmatch 语义），生产 Redis 实现走 SCAN+UNLINK。
    """

    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None: ...

    def delete(self, key: str) -> None: ...

    def invalidate_pattern(self, pattern: str) -> int: ...

    def incr(self, key: str, ttl_seconds: int | None = None) -> int:
        """原子 +1；如果键不存在按 0 起，可同时 set EXPIRE。返回新值。"""
        ...


class InMemoryCacheService:
    """进程内 TTL 缓存。MVP 单进程跑足够；多进程/多机切到 Redis 实现同接口。

    注意：这不是 LRU，超大量 key 会占内存——只用作 hot-key 加速场景。
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float | None]] = {}
        self._lock = threading.RLock()

    def _expired(self, exp: float | None) -> bool:
        return exp is not None and exp < time.time()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, exp = entry
            if self._expired(exp):
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        exp = time.time() + ttl_seconds if ttl_seconds else None
        with self._lock:
            self._store[key] = (value, exp)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def invalidate_pattern(self, pattern: str) -> int:
        with self._lock:
            keys = [k for k in self._store.keys() if fnmatch.fnmatchcase(k, pattern)]
            for k in keys:
                self._store.pop(k, None)
            return len(keys)

    def incr(self, key: str, ttl_seconds: int | None = None) -> int:
        with self._lock:
            entry = self._store.get(key)
            if entry is None or self._expired(entry[1]):
                new_val = 1
                exp = time.time() + ttl_seconds if ttl_seconds else None
                self._store[key] = (new_val, exp)
            else:
                cur, exp = entry
                new_val = int(cur) + 1
                # 不重置 TTL（与 Redis INCR 行为一致：只第一次 set EXPIRE）
                self._store[key] = (new_val, exp)
            return new_val


def make_key(module: str, resource: str, id_: Any) -> str:
    return f"{module}:{resource}:{id_}"


_default_cache: ICacheService = InMemoryCacheService()


def get_cache() -> ICacheService:
    return _default_cache


def set_cache(cache: ICacheService) -> None:
    global _default_cache
    _default_cache = cache


def configure_default_cache(redis_url: str | None = None) -> ICacheService:
    """启动时调一次。配了 REDIS_URL 就装 RedisCacheService，否则留进程内字典。"""
    if not redis_url:
        return _default_cache
    from app.shared.redis_cache import RedisCacheService

    cache = RedisCacheService(redis_url)
    cache.ping()  # 启动期就把连不上的问题暴露
    set_cache(cache)
    return cache
