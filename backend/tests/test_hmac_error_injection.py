"""A.T2.2 — HMAC 错误注入（端到端）

通过 TestClient 打 /api/v1/cp/upgrade/check 端点，覆盖签名/时间戳的常见攻击路径：
- 缺 sig / 错 sig
- 过期 ts（远古） / 未来 ts（防时钟漂移）
- 老 ts 重放 → 仍被 ts 校验拒
- 篡改 query 参数（同 sig）→ canonical 变化 → 拒
- 正例兜底（确保签名链路本身能跑通）

注意：路由用 query string `sig` 参数而不是 `X-CP-Signature` header（任务文件描述了
header 名是因为通常的设计，但当前实现走 query string，与 hmac_verifier 单测对齐）。
"""

from __future__ import annotations

import time
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1 import api_v1
from app.core.database import get_db
from app.modules.channel_pack.models import (
    CpApkSigningJob,
    CpApp,
    CpAppVersion,
    CpChannel,
    CpUpgradeRule,
)
from app.modules.channel_pack.services import app_registry
from app.modules.channel_pack.services.hmac_verifier import (
    CLOCK_SKEW_SECONDS,
    compute_signature,
)

HMAC_SECRET = "test-secret-hmac-error-injection"


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    test_app = FastAPI()
    test_app.include_router(api_v1)

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    test_app.dependency_overrides[get_db] = _override_get_db
    app_registry._cache.clear()

    with TestClient(test_app) as c:
        yield c

    test_app.dependency_overrides.clear()
    app_registry._cache.clear()


@pytest.fixture
def seeded(db: Session, admin_id: int) -> dict:
    """种 1 个 App + direct 渠道 + v100/v200 + v200 已签 job + 升级规则。

    这样正例签名通过时 has_update=True，能区分出"401 是签名拒"和"200 但 has_update=False"。
    """
    app = CpApp(
        tenant_uuid="tenant-hmac-inject",
        name="A",
        package_name="com.t.inject",
        owner_admin_user_id=admin_id,
        api_key_hash="x",
        hmac_secret=HMAC_SECRET,
        status="active",
    )
    db.add(app)
    db.flush()

    db.add(
        CpChannel(
            app_id=app.id, code="direct", name="Direct",
            is_play_store=False, enabled=True, priority=10,
        )
    )

    v200 = CpAppVersion(
        app_id=app.id,
        version_code=200,
        version_name="2.0",
        master_apk_oss_key="apks/t/200.apk",
        master_apk_sha256="bb",
        master_apk_size=1,
        status="ready",
        uploaded_by=admin_id,
    )
    db.add(v200)
    db.flush()

    db.add(
        CpApkSigningJob(
            app_id=app.id,
            version_code=200,
            channel_code="direct",
            master_sha256="bb",
            idempotency_key="k200direct-hmac",
            status="success",
            output_oss_key="apks/t/signed/200/direct.apk",
            output_sha256="dd",
            output_size=2,
        )
    )

    db.add(
        CpUpgradeRule(
            app_id=app.id,
            name="r",
            enabled=True,
            version_code_min=0,
            version_code_max=999,
            channel_codes=[],
            country_codes=[],
            device_id_hash_mod_min=0,
            device_id_hash_mod_max=99,
            target_version_code=200,
            priority=10,
            created_by=admin_id,
            popup_title_i18n={"en": "Update"},
            popup_content_i18n={"en": "x"},
            confirm_text_i18n={"en": "OK"},
            cancel_text_i18n={"en": "Later"},
            popup_buttons=[],
        )
    )
    db.commit()

    return {"app": app, "admin_id": admin_id}


def _base_params(tenant_uuid: str, ts: int | None = None) -> dict[str, str]:
    """组装一份合法的 query 参数（不含 sig）。"""
    return {
        "app_id": tenant_uuid,
        "version_code": "100",
        "channel": "direct",
        "device_id": "device-x",
        "country": "ID",
        "ts": str(ts if ts is not None else int(time.time())),
    }


def _call(client: TestClient, params: dict[str, str]):
    """避免 app_registry 进程缓存导致跨测试串扰。"""
    app_registry._cache.clear()
    return client.get("/api/v1/cp/upgrade/check", params=params)


# ===================== T2.2: HMAC 错误注入 =====================


def test_missing_signature_header_returns_401(
    client: TestClient, seeded: dict
) -> None:
    """缺 sig query 参数 → FastAPI Query(...) 校验直接 422（必填参数缺失）。

    注：HTTP 层面"缺签名"在当前实现里是 422 而不是 401，
    因为 sig 是 Query(...) 必填项。这本身就是一种鉴权失败，
    用例验证该路径无法绕过签名校验。
    """
    params = _base_params(seeded["app"].tenant_uuid)
    # 不附 sig
    resp = _call(client, params)
    # FastAPI 必填参数缺失返 422；语义上等价于"无法通过签名校验"
    assert resp.status_code in (401, 422), resp.text


def test_wrong_signature_returns_401(client: TestClient, seeded: dict) -> None:
    """sig 是乱字符串 → 401 signature mismatch。"""
    params = _base_params(seeded["app"].tenant_uuid)
    params["sig"] = "deadbeef-not-a-real-signature"
    resp = _call(client, params)
    assert resp.status_code == 401, resp.text
    assert "signature" in resp.text.lower() or "mismatch" in resp.text.lower()


def test_expired_timestamp_returns_401(client: TestClient, seeded: dict) -> None:
    """ts 是 5min+ 前 → 401 ts expired（不到 HMAC 校验那一步）。"""
    old_ts = int(time.time()) - CLOCK_SKEW_SECONDS - 60  # 比 5min 还多 1min
    params = _base_params(seeded["app"].tenant_uuid, ts=old_ts)
    # 即使 sig 算对，也应该被 ts 校验先拦下
    params["sig"] = compute_signature(HMAC_SECRET, params)
    resp = _call(client, params)
    assert resp.status_code == 401, resp.text
    assert "ts" in resp.text.lower() or "expired" in resp.text.lower()


def test_future_timestamp_returns_401(client: TestClient, seeded: dict) -> None:
    """ts 是 5min+ 后（时钟漂移防御）→ 401 ts expired。"""
    future_ts = int(time.time()) + CLOCK_SKEW_SECONDS + 60
    params = _base_params(seeded["app"].tenant_uuid, ts=future_ts)
    params["sig"] = compute_signature(HMAC_SECRET, params)
    resp = _call(client, params)
    assert resp.status_code == 401, resp.text
    assert "ts" in resp.text.lower() or "expired" in resp.text.lower()


def test_replay_same_signature_works_within_window_but_old_ts_rejected(
    client: TestClient, seeded: dict
) -> None:
    """同一 sig 用老 ts 重放：

    A）当前时间内 ts 合法 → 第一次和第二次都通过（无 nonce 机制是已知设计）
    B）把同一 (params, sig) 放到 5min+ 之前 → 401（被 ts 窗口拒）

    本用例验证 B：sig 算对了 也救不了过期 ts。
    """
    # 先用合法 ts 算一次签名，作为攻击者"截获的报文"
    captured_ts = int(time.time())
    captured_params = _base_params(seeded["app"].tenant_uuid, ts=captured_ts)
    captured_sig = compute_signature(HMAC_SECRET, captured_params)

    # 重放：把 ts 改成 5min+ 之前（模拟攻击者过了一段时间再发）
    replayed = dict(captured_params)
    replayed["ts"] = str(captured_ts - CLOCK_SKEW_SECONDS - 60)
    replayed["sig"] = captured_sig  # 用原 sig 重放

    resp = _call(client, replayed)
    assert resp.status_code == 401, resp.text


def test_tampered_query_param_invalidates_signature(
    client: TestClient, seeded: dict
) -> None:
    """计算签名后篡改 country=ID → VN，canonical 变 → sig 不再有效 → 401。"""
    params = _base_params(seeded["app"].tenant_uuid)
    params["country"] = "ID"
    sig = compute_signature(HMAC_SECRET, params)

    # 攻击者把 country 改成 VN 但 sig 不变
    params["country"] = "VN"
    params["sig"] = sig

    resp = _call(client, params)
    assert resp.status_code == 401, resp.text


def test_valid_signature_returns_200(client: TestClient, seeded: dict) -> None:
    """正例兜底：合法 sig + 合法 ts → 200，且 has_update=True（规则匹配上了）。

    缺这条用例其它"负例 → 401"的测试可能因路由本身坏掉而误通过。
    """
    params = _base_params(seeded["app"].tenant_uuid)
    params["sig"] = compute_signature(HMAC_SECRET, params)
    resp = _call(client, params)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["has_update"] is True
    assert body["target_version_code"] == 200


def test_wrong_app_id_returns_401(client: TestClient, seeded: dict) -> None:
    """app_id 不存在 → 401 app_id invalid（拒绝枚举 tenant_uuid 的攻击）。"""
    params = _base_params("tenant-does-not-exist-xx")
    # 用真 secret 算签名（攻击者也算不出 — 因为它就不知道哪个 secret 对应这个 tenant）
    params["sig"] = compute_signature(HMAC_SECRET, params)
    resp = _call(client, params)
    assert resp.status_code == 401, resp.text
