"""P6.11 Locust 压测脚本：模拟 App 端 /upgrade/check 调用。

依赖（dev only，不进生产镜像）：
    uv add --group dev locust>=2.0   # 或 pip install locust

用法（本地起 backend 后另开终端）：
    cd backend && locust -f scripts/locustfile.py \
        --host http://localhost:8000 \
        -u 1000 -r 50 -t 60s --headless

参数：
    -u 1000        并发用户数（task 起跑后稳态）
    -r 50          每秒新增 ramp-up 速度
    -t 60s         持续时间
    --headless     不开 web UI，直接命令行跑

环境变量：
    CP_TENANT_UUID  目标租户（演练前用 admin 接口建好）
    CP_HMAC_SECRET  对应租户的 HMAC（建租户时一次性返回，存 1Password）

不走 HMAC 也能压（演练 5xx / 容量），但接口会 401 拒绝；要真实压通就配上面两个 env。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import random
import time

try:
    from locust import HttpUser, between, task
except ImportError as e:
    raise SystemExit(
        "locust 未安装；运行：uv add --group dev locust>=2.0  或  pip install locust"
    ) from e


TENANT_UUID = os.getenv("CP_TENANT_UUID", "test-tenant")
HMAC_SECRET = os.getenv("CP_HMAC_SECRET", "test-secret")
COUNTRIES = ["US", "JP", "ID", "MY", "VN", "TH", "BR", "MX", "EG", "NG"]


def _sign(params: dict[str, str], secret: str) -> str:
    items = sorted((k, v) for k, v in params.items() if k != "sig")
    canonical = "&".join(f"{k}={v}" for k, v in items)
    digest = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


class UpgradeCheckUser(HttpUser):
    wait_time = between(0.5, 2.0)

    @task(10)
    def upgrade_check(self) -> None:
        params = {
            "tenant_uuid": TENANT_UUID,
            "ts": str(int(time.time())),
            "channel_code": random.choice(["direct", "xiaomi_intl", "huawei_intl"]),
            "version_code": str(random.choice([100, 110, 120, 150])),
            "country": random.choice(COUNTRIES),
            "device_id": f"loc-{random.randint(1, 100000)}",
        }
        params["sig"] = _sign(params, HMAC_SECRET)
        self.client.get("/api/v1/cp/upgrade/check", params=params, name="/upgrade/check")

    @task(1)
    def healthz(self) -> None:
        self.client.get("/healthz", name="/healthz")
