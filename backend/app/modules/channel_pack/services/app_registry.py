"""按 tenant_uuid 加载 cp_apps，进程内缓存 60s。

生产换 Redis 缓存即可（接口不变）。
"""

import time
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.channel_pack.models import CpApp

_CACHE_TTL = 60.0
_cache: dict[str, tuple[float, CpApp | None]] = {}
_cache_lock = Lock()


def get_app_by_uuid(db: Session, tenant_uuid: str) -> CpApp | None:
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(tenant_uuid)
        if cached and now - cached[0] < _CACHE_TTL:
            return cached[1]

    stmt = select(CpApp).where(CpApp.tenant_uuid == tenant_uuid, CpApp.status == "active")
    app = db.scalars(stmt).one_or_none()

    with _cache_lock:
        _cache[tenant_uuid] = (now, app)
    return app


def invalidate(tenant_uuid: str) -> None:
    with _cache_lock:
        _cache.pop(tenant_uuid, None)
