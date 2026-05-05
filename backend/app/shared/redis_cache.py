"""RedisCacheService：实现 ICacheService（生产推荐用这个）。

懒加载 redis-py：只有 configure_default_cache() 真要切到 Redis 时才 import。
未装依赖也不影响进程内内存缓存的默认实现。
"""

from __future__ import annotations

import json
from typing import Any


class RedisCacheService:
    """SCAN + UNLINK 实现 invalidate_pattern；MSET/MGET 没暴露——按需扩展。

    序列化：JSON。简单可读、跨语言；超大 binary 不要塞进来（用 OSS/外链）。
    """

    def __init__(self, redis_url: str, *, key_prefix: str = "movie:") -> None:
        try:
            import redis
        except ImportError as e:
            raise RuntimeError(
                "redis 包未安装；运行 `uv add redis>=5` 或别在配置里指 RedisCacheService"
            ) from e

        self._client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._prefix = key_prefix

    def _k(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def get(self, key: str) -> Any | None:
        raw = self._client.get(self._k(key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw  # 字符串原样返回（兼容老数据）

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        payload = json.dumps(value, ensure_ascii=False, default=str)
        if ttl_seconds:
            self._client.set(self._k(key), payload, ex=ttl_seconds)
        else:
            self._client.set(self._k(key), payload)

    def delete(self, key: str) -> None:
        self._client.unlink(self._k(key))

    def invalidate_pattern(self, pattern: str) -> int:
        """SCAN 防止 KEYS 阻塞 → 收集匹配 → UNLINK 异步删除。"""
        prefixed = self._k(pattern)
        deleted = 0
        for batch in self._scan_iter(prefixed, count=500):
            if not batch:
                continue
            deleted += self._client.unlink(*batch)
        return deleted

    def _scan_iter(self, match: str, count: int = 500):
        """分批返回 keys，避免单次 KEYS 阻塞 redis 主线程。"""
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor=cursor, match=match, count=count)
            if keys:
                yield keys
            if cursor == 0:
                break

    def incr(self, key: str, ttl_seconds: int | None = None) -> int:
        """原子 INCR；首次写入时设 EXPIRE。后续 +1 不重置 TTL（限流窗口语义）。"""
        full_key = self._k(key)
        n = self._client.incr(full_key)
        if n == 1 and ttl_seconds:
            self._client.expire(full_key, ttl_seconds)
        return int(n)

    def ping(self) -> bool:
        return bool(self._client.ping())
