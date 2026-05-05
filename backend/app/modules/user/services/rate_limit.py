"""三层频控（进程内字典 + 时间窗）— MVP 版本，生产换 Redis。

接口稳定（hit_phone / hit_ip / hit_device），切 Redis 只换实现。
"""

import time
from collections import defaultdict
from threading import Lock
from typing import Literal

from app.core.config import settings


class RateLimiter:
    """slide window：每个 key 存一个 timestamp 列表，超过 window 的 evict。"""

    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def hit(self, key: str, window_seconds: int, max_count: int) -> bool:
        """返回 True = 通过；False = 触发限流"""
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            ts = self._buckets[key]
            # evict
            self._buckets[key] = [t for t in ts if t > cutoff]
            if len(self._buckets[key]) >= max_count:
                return False
            self._buckets[key].append(now)
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self._buckets.pop(key, None)


_default_limiter = RateLimiter()


def hit_phone(phone: str) -> bool:
    """同号 60s 一次"""
    return _default_limiter.hit(
        f"otp:phone:{phone}", settings.otp_rate_limit_per_phone_seconds, max_count=1
    )


def hit_ip(ip: str) -> bool:
    """同 IP 5min 5 次"""
    return _default_limiter.hit(
        f"otp:ip:{ip}", 300, max_count=settings.otp_rate_limit_per_ip_per_5min
    )


def hit_device(device_id: str) -> bool:
    """同设备 24h 10 次"""
    return _default_limiter.hit(
        f"otp:device:{device_id}", 86400, max_count=settings.otp_rate_limit_per_device_per_day
    )


def hit_all(
    phone: str, ip: str | None, device_id: str | None
) -> tuple[bool, Literal["phone", "ip", "device"] | None]:
    """三层依次检查；返回 (ok, 触发的层)"""
    if not hit_phone(phone):
        return False, "phone"
    if ip and not hit_ip(ip):
        # 退回 phone 那次（避免连带阻塞）
        _default_limiter.reset(f"otp:phone:{phone}")
        return False, "ip"
    if device_id and not hit_device(device_id):
        _default_limiter.reset(f"otp:phone:{phone}")
        return False, "device"
    return True, None
