"""OTP 三层频控（phone / ip / device）单测。

被测：app.modules.user.services.rate_limit
- 滑动窗口语义：满 max_count 后第 N+1 次返回 False
- evict（窗口外的 timestamp 被清掉）：窗口过去后又能通过
- reset() 显式清 bucket 后立刻能通过
- hit_all() 上层接口：触发某一层时返回对应 layer 名字

注意：rate_limit 用进程内字典（threading.Lock）；测试用 monkeypatch time.time 控制时钟。
"""

from __future__ import annotations

import pytest

from app.modules.user.services import rate_limit
from app.modules.user.services.rate_limit import RateLimiter


@pytest.fixture(autouse=True)
def _clear_default_limiter():
    """每个用例都从空 bucket 起，避免跨用例串扰（默认 limiter 是模块单例）。"""
    rate_limit._default_limiter._buckets.clear()
    yield
    rate_limit._default_limiter._buckets.clear()


# ----------------- RateLimiter 底层 -----------------


def test_hit_under_limit_pass() -> None:
    rl = RateLimiter()
    assert rl.hit("k", window_seconds=60, max_count=3) is True
    assert rl.hit("k", window_seconds=60, max_count=3) is True
    assert rl.hit("k", window_seconds=60, max_count=3) is True


def test_hit_over_limit_reject() -> None:
    """连击到达 max_count 后第 N+1 次拒。"""
    rl = RateLimiter()
    for _ in range(5):
        assert rl.hit("k", window_seconds=60, max_count=5) is True
    # 第 6 次：拒
    assert rl.hit("k", window_seconds=60, max_count=5) is False


def test_hit_window_evict_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    """打满后等过窗口期 → bucket 被 evict → 又能通过（滑动窗口）。"""
    rl = RateLimiter()
    fake_now = [1000.0]
    monkeypatch.setattr("app.modules.user.services.rate_limit.time.time", lambda: fake_now[0])

    # t=1000：连击 3 次到上限
    for _ in range(3):
        assert rl.hit("k", window_seconds=60, max_count=3) is True
    assert rl.hit("k", window_seconds=60, max_count=3) is False

    # 推进时钟到 1070（>60s 窗口外）→ 旧 timestamp 被 evict → 通过
    fake_now[0] = 1070.0
    assert rl.hit("k", window_seconds=60, max_count=3) is True


def test_hit_reset_clears_bucket() -> None:
    rl = RateLimiter()
    for _ in range(3):
        rl.hit("k", window_seconds=60, max_count=3)
    assert rl.hit("k", window_seconds=60, max_count=3) is False

    rl.reset("k")
    assert rl.hit("k", window_seconds=60, max_count=3) is True


def test_hit_different_keys_independent() -> None:
    """不同 key 各自计数，互不影响。"""
    rl = RateLimiter()
    for _ in range(3):
        rl.hit("a", window_seconds=60, max_count=3)
    # a 满了
    assert rl.hit("a", window_seconds=60, max_count=3) is False
    # b 还是空的
    assert rl.hit("b", window_seconds=60, max_count=3) is True


# ----------------- hit_all 三层联动 -----------------


def test_hit_all_pass_first_time() -> None:
    """新号、新 IP、新设备 → 全部通过；layer=None。"""
    ok, layer = rate_limit.hit_all("+62811111111", "1.2.3.4", "dev-1")
    assert ok is True
    assert layer is None


def test_hit_all_phone_layer_blocks_second_in_60s() -> None:
    """同号 60s 内第二次 → False, layer='phone'。"""
    ok1, _ = rate_limit.hit_all("+62888888888", "1.1.1.1", "dev-x")
    assert ok1 is True
    ok2, layer = rate_limit.hit_all("+62888888888", "2.2.2.2", "dev-y")
    assert ok2 is False
    assert layer == "phone"


def test_hit_all_ip_layer_blocks_after_5(monkeypatch: pytest.MonkeyPatch) -> None:
    """同 IP 5min 5 次后第 6 次 → False, layer='ip'。
    用 5 个不同手机号避免被 phone 层先拦下。
    """
    ip = "9.9.9.9"
    for i in range(5):
        ok, _ = rate_limit.hit_all(f"+6280000000{i}", ip, f"dev-{i}")
        assert ok is True

    ok, layer = rate_limit.hit_all("+62800000099", ip, "dev-99")
    assert ok is False
    assert layer == "ip"


def test_hit_all_device_layer_blocks_after_10() -> None:
    """同 device 24h 10 次后第 11 次 → False, layer='device'。
    每次换新 phone + 新 IP，确保只可能在 device 层被拦。
    """
    dev = "device-aaa"
    for i in range(10):
        # phone 唯一、ip 唯一 → 只剩 device 计数会撞限
        ok, _ = rate_limit.hit_all(f"+6281110000{i:02d}", f"10.0.0.{i}", dev)
        assert ok is True, f"第 {i + 1} 次本来应通过"

    ok, layer = rate_limit.hit_all("+6281110000xx", "10.0.0.99", dev)
    assert ok is False
    assert layer == "device"


def test_hit_all_compensates_phone_when_ip_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """ip 层拦下时，phone 那次必须被 reset，避免连带阻塞（实现细节兜底）。"""
    ip = "7.7.7.7"
    # 先撑满 IP 5 次（不同 phone）
    for i in range(5):
        rate_limit.hit_all(f"+6281000000{i}", ip, f"dev-{i}")

    new_phone = "+6281000009999"
    ok, layer = rate_limit.hit_all(new_phone, ip, "dev-99")
    assert (ok, layer) == (False, "ip")

    # 该 phone 因为 IP 拦下，phone bucket 应该被 reset；用不同 IP 立刻重试应能通过
    ok2, _ = rate_limit.hit_all(new_phone, "8.8.8.8", "dev-other")
    assert ok2 is True


def test_hit_phone_uses_settings_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """hit_phone 调用底层时用 settings.otp_rate_limit_per_phone_seconds 作为窗口。"""
    captured: dict = {}

    real_hit = rate_limit._default_limiter.hit

    def spy(key: str, window_seconds: int, max_count: int) -> bool:
        captured["key"] = key
        captured["window"] = window_seconds
        captured["max"] = max_count
        return real_hit(key, window_seconds, max_count)

    monkeypatch.setattr(rate_limit._default_limiter, "hit", spy)
    rate_limit.hit_phone("+62811223344")
    assert captured["key"] == "otp:phone:+62811223344"
    assert captured["max"] == 1
    # 默认 60 秒（config.py）
    assert captured["window"] == 60
