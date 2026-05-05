"""HMAC 签名验证器单测：纯函数，无 DB 依赖。"""

from __future__ import annotations

import time

import pytest

from app.modules.channel_pack.services.hmac_verifier import (
    CLOCK_SKEW_SECONDS,
    build_canonical,
    compute_signature,
    verify_signature,
    verify_timestamp,
)

SECRET = "test-secret-32-bytes-base64-blob"


class TestBuildCanonical:
    def test_排序后用_amp_拼接(self) -> None:
        assert build_canonical({"b": "2", "a": "1"}) == "a=1&b=2"

    def test_排除_sig_自身(self) -> None:
        assert build_canonical({"a": "1", "sig": "x"}) == "a=1"

    def test_空_dict(self) -> None:
        assert build_canonical({}) == ""


class TestComputeAndVerify:
    def test_compute_确定性(self) -> None:
        params = {"tenant": "t1", "ts": "100", "vc": "5"}
        assert compute_signature(SECRET, params) == compute_signature(SECRET, params)

    def test_顺序不影响签名(self) -> None:
        a = compute_signature(SECRET, {"a": "1", "b": "2"})
        b = compute_signature(SECRET, {"b": "2", "a": "1"})
        assert a == b

    def test_verify_接受正确签名(self) -> None:
        params = {"tenant": "t1", "ts": "100"}
        sig = compute_signature(SECRET, params)
        assert verify_signature(SECRET, params, sig) is True

    def test_verify_拒绝错签(self) -> None:
        params = {"tenant": "t1", "ts": "100"}
        assert verify_signature(SECRET, params, "deadbeef") is False

    def test_verify_拒绝错_secret(self) -> None:
        params = {"tenant": "t1", "ts": "100"}
        sig = compute_signature(SECRET, params)
        assert verify_signature("other-secret", params, sig) is False

    def test_篡改任一参数_签名失效(self) -> None:
        params = {"tenant": "t1", "ts": "100"}
        sig = compute_signature(SECRET, params)
        tampered = dict(params, ts="101")
        assert verify_signature(SECRET, tampered, sig) is False


class TestVerifyTimestamp:
    def test_当前时间通过(self) -> None:
        assert verify_timestamp(int(time.time())) is True

    def test_5分钟内通过(self) -> None:
        assert verify_timestamp(int(time.time()) - 200) is True
        assert verify_timestamp(int(time.time()) + 200) is True

    def test_超过5分钟拒绝(self) -> None:
        assert verify_timestamp(int(time.time()) - CLOCK_SKEW_SECONDS - 10) is False
        assert verify_timestamp(int(time.time()) + CLOCK_SKEW_SECONDS + 10) is False


@pytest.mark.parametrize(
    "params",
    [
        {"a": "1"},
        {"a": "x", "b": "y", "c": "z"},
        {"tenant": "uuid-xxx", "ts": "1234567890", "vc": "99", "ch": "direct"},
    ],
)
def test_round_trip(params: dict[str, str]) -> None:
    sig = compute_signature(SECRET, params)
    assert verify_signature(SECRET, params, sig)
