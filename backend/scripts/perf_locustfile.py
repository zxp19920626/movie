"""性能基线压测 locustfile（任务 C: T4.1/T4.2 用）

与 scripts/locustfile.py 区别：
- 修正路由参数名（app_id / channel，老版用了 tenant_uuid / channel_code）
- 提供 CACHE_BUST=1 模式：device_id 用 UUID（每请求唯一），模拟缓存命中率 0%
  （T4.2 缓存击穿对比，虽然当前 upgrade_engine 没有 response 级缓存，
   但这也能验证"加缓存前 vs 加缓存后"的基线参考点）
- 缩短 wait_time，避免并发不足

环境变量：
    CP_TENANT_UUID  目标租户
    CP_HMAC_SECRET  HMAC 密钥
    CACHE_BUST      "1" → device_id 每次随机 UUID；否则池里循环（更接近正常分布）

用法：
    cd backend
    export CP_TENANT_UUID=...
    export CP_HMAC_SECRET=...
    uv run locust -f scripts/perf_locustfile.py \
        --host http://localhost:8000 \
        -u 100 -r 20 -t 60s --headless --only-summary
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import random
import time
import uuid

from locust import HttpUser, between, task

TENANT_UUID = os.getenv("CP_TENANT_UUID", "test-tenant")
HMAC_SECRET = os.getenv("CP_HMAC_SECRET", "test-secret")
CACHE_BUST = os.getenv("CACHE_BUST", "0") == "1"

COUNTRIES = ["US", "JP", "ID", "MY", "VN", "TH", "BR", "MX", "EG", "NG"]
CHANNELS = ["direct", "xiaomi_intl", "huawei_intl", "samsung_galaxy"]
VERSION_CODES = ["100", "110", "120", "150"]


def _sign(params: dict[str, str], secret: str) -> str:
    items = sorted((k, v) for k, v in params.items() if k != "sig")
    canonical = "&".join(f"{k}={v}" for k, v in items)
    digest = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


class UpgradeCheckUser(HttpUser):
    # 较短等待 → 维持稳态并发；避免 wait 太长导致 RPS 上不去
    wait_time = between(0.05, 0.2)

    @task
    def upgrade_check(self) -> None:
        if CACHE_BUST:
            device_id = f"uuid-{uuid.uuid4()}"
        else:
            device_id = f"loc-{random.randint(1, 1000)}"

        params = {
            "app_id": TENANT_UUID,
            "ts": str(int(time.time())),
            "channel": random.choice(CHANNELS),
            "version_code": random.choice(VERSION_CODES),
            "country": random.choice(COUNTRIES),
            "device_id": device_id,
        }
        params["sig"] = _sign(params, HMAC_SECRET)
        self.client.get("/api/v1/cp/upgrade/check", params=params, name="/upgrade/check")
