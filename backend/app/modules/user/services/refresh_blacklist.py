"""refresh token 黑名单 — MVP 用进程内 set + DB（u_refresh_tokens.revoked），生产换 Redis。

接口稳定，切 Redis 只换实现。
"""

import time
from threading import Lock


class _MemoryBlacklist:
    """jti → expires_at(unix); 过期自动 evict"""

    def __init__(self) -> None:
        self._store: dict[str, float] = {}
        self._lock = Lock()

    def add(self, jti: str, expires_at_unix: float) -> None:
        with self._lock:
            self._store[jti] = expires_at_unix
            self._evict_locked()

    def is_blacklisted(self, jti: str) -> bool:
        with self._lock:
            self._evict_locked()
            return jti in self._store

    def _evict_locked(self) -> None:
        now = time.time()
        expired = [k for k, exp in self._store.items() if exp < now]
        for k in expired:
            del self._store[k]


_default_blacklist = _MemoryBlacklist()


def add(jti: str, expires_at_unix: float) -> None:
    _default_blacklist.add(jti, expires_at_unix)


def is_blacklisted(jti: str) -> bool:
    return _default_blacklist.is_blacklisted(jti)
