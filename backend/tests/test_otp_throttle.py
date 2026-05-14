"""红线 #5 — OTP 三层频控端到端测试。

被测：POST /api/v1/auth/phone/send-otp（链 phone / IP / device 三层限流）。

红线层级关心：
- 同手机号 60s 内第二次必须拒（layer=phone）
- 同 IP 5 min 内 5 次后第 6 次拒（layer=ip）
- 同 device 10 次/天 后第 11 次拒（layer=device）
- 国码白名单不在表里 → 400
- Turnstile 失败 → 401（dev mode token 必须非空）

注意：Turnstile 走 dev mode（TURNSTILE_SECRET 未设）→ 任意非空 token 通过。
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1 import api_v1
from app.core.database import get_db
from app.modules.user.services import rate_limit


@pytest.fixture(autouse=True)
def _clear_rate_buckets():
    """每个用例清空 limiter，避免跨用例串扰（默认 limiter 是模块单例）。"""
    rate_limit._default_limiter._buckets.clear()
    yield
    rate_limit._default_limiter._buckets.clear()


@pytest.fixture
def client(db: Session) -> TestClient:
    test_app = FastAPI()
    test_app.include_router(api_v1)

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    test_app.dependency_overrides[get_db] = _override_get_db
    return TestClient(test_app)


_VALID_PHONE_BASE = "+62811"  # +62 是白名单内的印尼号
_VALID_TURNSTILE = "ts-token-dev"


def _send(client: TestClient, *, phone: str, device_id: str = "dev-1") -> dict:
    return client.post(
        "/api/v1/auth/phone/send-otp",
        json={
            "phone": phone,
            "turnstile_token": _VALID_TURNSTILE,
            "device_id": device_id,
        },
    )  # type: ignore[return-value]


# ---------------- Layer 1: phone 60s 一次 ----------------


def test_send_otp_first_time_success(client: TestClient):
    r = _send(client, phone=_VALID_PHONE_BASE + "1000001")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "sent"


def test_send_otp_same_phone_second_within_60s_blocked(client: TestClient):
    """同手机号 60s 内第二次 → 429 layer=phone（红线 #5）。"""
    phone = _VALID_PHONE_BASE + "1000002"
    r1 = _send(client, phone=phone)
    assert r1.status_code == 200, r1.text

    r2 = _send(client, phone=phone, device_id="dev-different")
    assert r2.status_code == 429
    assert "phone" in r2.json()["detail"]


# ---------------- Layer 2: IP 5min 5 次 ----------------


def test_send_otp_same_ip_blocks_after_5_in_5min(client: TestClient):
    """同 IP 5min 内第 6 次 → 429 layer=ip。
    TestClient 默认 client host 是 'testclient'，所有请求都共享同一 IP。
    用 5 个不同 phone 让 phone 层不先撞限。
    """
    for i in range(5):
        r = _send(client, phone=f"{_VALID_PHONE_BASE}3{i:06d}", device_id=f"dev-ip-{i}")
        assert r.status_code == 200, f"第 {i + 1} 次应通过, 但 {r.status_code}: {r.text}"

    # 第 6 次同 IP
    r6 = _send(client, phone=f"{_VALID_PHONE_BASE}3999999", device_id="dev-ip-x")
    assert r6.status_code == 429
    assert "ip" in r6.json()["detail"]


# ---------------- Layer 3: device 10/天 ----------------


def test_send_otp_same_device_blocks_after_10_per_day(client: TestClient):
    """同 device 24h 内第 11 次 → 429 layer=device。
    每次换 phone + 切真实 client IP（用 base_url 切；这里走 TestClient 头 X-Forwarded-For 不行，
    只能换 phone 让 phone/IP 不先拦下）。

    注意 TestClient 共享一个 IP，因此 5 次后就会撞 IP 层。要测 device 层需要绕过 IP。
    手段：直接调底层 rate_limit.hit_device 测语义；端点层调用顺序是 phone→ip→device。
    """
    device = "dev-throttle"
    # 直接打 limiter（底层）
    for i in range(10):
        assert rate_limit.hit_device(device) is True, f"第 {i + 1} 次应通过"
    # 第 11 次 → 拒
    assert rate_limit.hit_device(device) is False


def test_send_otp_device_layer_in_hit_all():
    """覆盖 hit_all 上层语义：layer 名字 == 'device'。"""
    device = "dev-otp-throttle-2"
    # 用 10 个不同 phone + 10 个不同 IP 把 device 撑满
    for i in range(10):
        ok, _ = rate_limit.hit_all(f"+6281200000{i:02d}", f"172.16.0.{i}", device)
        assert ok is True

    ok, layer = rate_limit.hit_all("+62812000099", "172.16.0.99", device)
    assert ok is False
    assert layer == "device"


# ---------------- 国码白名单 ----------------


def test_phone_country_not_in_whitelist_400(client: TestClient):
    """+1（美加）不在白名单 → 400。"""
    r = _send(client, phone="+12345678901")
    assert r.status_code == 400, r.text
    assert "phone country code" in r.json()["detail"]


def test_phone_without_plus_400(client: TestClient):
    """phone 没 + 开头 → schema 校验 422 或国码白名单 400。"""
    r = client.post(
        "/api/v1/auth/phone/send-otp",
        json={
            "phone": "62811000000",  # 漏了 +
            "turnstile_token": _VALID_TURNSTILE,
            "device_id": "dev-x",
        },
    )
    # pydantic regex 校验先拦下
    assert r.status_code == 422, r.text


# ---------------- Turnstile ----------------


def test_send_otp_empty_turnstile_token_blocked(client: TestClient):
    """dev mode 下空 token → verify_turnstile 返回 False → 401。"""
    r = client.post(
        "/api/v1/auth/phone/send-otp",
        json={
            "phone": _VALID_PHONE_BASE + "9000001",
            "turnstile_token": "",
            "device_id": "dev-empty-ts",
        },
    )
    assert r.status_code == 401, r.text
    assert "turnstile" in r.json()["detail"].lower()


# ---------------- 互不干扰 ----------------


def test_different_phones_each_first_time_pass(client: TestClient):
    """不同 phone 各自的第一次都应通过（phone 层 key 是 phone 维度）。
    限于 5 个以内避免撞 IP 层。
    """
    for i in range(3):
        r = _send(client, phone=f"{_VALID_PHONE_BASE}88{i:05d}", device_id=f"dev-diff-{i}")
        assert r.status_code == 200, r.text
