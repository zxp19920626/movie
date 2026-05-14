"""M2.T4：Play 渠道防漏出端到端验证（无生产代码改动，验证现有兜底未被破坏）。

现状：/upgrade/check 命中 channel.is_play_store=true 时，upgrade_engine 直接
返回 None → 路由返回 UpgradeCheckResponse(has_update=False)，其余字段全部缺省。

本测试验证：
- 即便存在 apply-to-all 规则配了 popup_buttons，Play 渠道也不能漏出任何按钮 / 弹窗
  字段内容（has_update=False，所有 i18n / button 字段为 None 或空 list）
- 同样规则换非 Play 渠道时，popup_buttons 正常输出（对比项）
- response JSON 不含任何配置的 button text / url 字符串（端到端文本扫描兜底）
"""

from __future__ import annotations

import json
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
from app.modules.channel_pack.services.hmac_verifier import compute_signature


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
    """种 1 个 App + 同时建 Play / direct 两条渠道 + v200 master + v200 在
    direct 渠道签好的 job（Play 渠道没有 signed job，符合 PRD 不可签 Play）。
    """
    app = CpApp(
        tenant_uuid="tenant-play-leak",
        name="A",
        package_name="com.t.playleak",
        owner_admin_user_id=admin_id,
        api_key_hash="x",
        hmac_secret="secret-play-leak",
        status="active",
    )
    db.add(app)
    db.flush()

    play_channel = CpChannel(
        app_id=app.id, code="gp", name="Google Play",
        is_play_store=True, enabled=True, priority=10,
        signing_strategy="play_signed",
    )
    direct_channel = CpChannel(
        app_id=app.id, code="direct", name="Direct",
        is_play_store=False, enabled=True, priority=20,
    )
    db.add_all([play_channel, direct_channel])

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

    direct_signed = CpApkSigningJob(
        app_id=app.id,
        version_code=200,
        channel_code="direct",
        master_sha256="bb",
        idempotency_key="k200direct",
        status="success",
        output_oss_key="apks/t/signed/200/direct.apk",
        output_sha256="dd",
        output_size=2,
    )
    db.add(direct_signed)
    db.flush()
    db.commit()

    return {"app": app, "admin_id": admin_id}


def _add_apply_to_all_rule_with_buttons(
    db: Session,
    *,
    app_id: int,
    admin_id: int,
    popup_buttons: list[dict],
) -> CpUpgradeRule:
    """apply-to-all 规则：channel_codes=[] / country_codes=[]，hash 全段命中。
    若 Play 兜底不工作，这条规则会同时匹配 Play 渠道并漏出 popup_buttons。
    """
    rule = CpUpgradeRule(
        app_id=app_id,
        name="apply-to-all-with-buttons",
        enabled=True,
        version_code_min=0,
        version_code_max=999,
        channel_codes=[],  # all
        country_codes=[],  # all
        device_id_hash_mod_min=0,
        device_id_hash_mod_max=99,
        target_version_code=200,
        priority=10,
        created_by=admin_id,
        popup_title_i18n={"en": "PlayLeakTitle", "id": "JudulBocor"},
        popup_content_i18n={"en": "PlayLeakContent"},
        confirm_text_i18n={"en": "OK"},
        cancel_text_i18n={"en": "Cancel"},
        popup_buttons=popup_buttons,
    )
    db.add(rule)
    db.flush()
    db.commit()
    return rule


def _signed_call(
    client: TestClient,
    *,
    hmac_secret: str,
    tenant_uuid: str,
    channel: str,
    country: str = "",
    device_id: str = "device-play-leak",
    version_code: int = 100,
) -> tuple[int, dict, str]:
    ts = int(time.time())
    params = {
        "app_id": tenant_uuid,
        "version_code": str(version_code),
        "channel": channel,
        "device_id": device_id,
        "country": country,
        "ts": str(ts),
    }
    sig = compute_signature(hmac_secret, params)
    params["sig"] = sig
    app_registry._cache.clear()
    resp = client.get("/api/v1/cp/upgrade/check", params=params)
    assert resp.status_code == 200, resp.text
    return resp.status_code, resp.json(), resp.text


# ===================== T4: Play 渠道防漏出 =====================


def test_play_store_channel_returns_no_update_even_if_rule_exists(
    client: TestClient, db: Session, seeded: dict
) -> None:
    """apply-to-all 规则带 popup_buttons，Play 渠道命中本应漏出 → 兜底必须
    返回 has_update=False 且 popup_buttons 不漏。
    """
    _add_apply_to_all_rule_with_buttons(
        db,
        app_id=seeded["app"].id,
        admin_id=seeded["admin_id"],
        popup_buttons=[
            {
                "id": "btn_update_play",
                "type": "playstore",
                "text_i18n": {"en": "Open in Play Store", "id": "Buka di Play Store"},
                "url_i18n": {
                    "en": "https://play.google.com/store/apps/details?id=com.t.playleak",
                    "id": "https://play.google.com/store/apps/details?id=com.t.playleak",
                },
                "style": "primary",
            },
            {
                "id": "btn_close",
                "type": "none",
                "text_i18n": {"en": "Later", "id": "Nanti"},
            },
        ],
    )
    _, body, _ = _signed_call(
        client,
        hmac_secret="secret-play-leak",
        tenant_uuid=seeded["app"].tenant_uuid,
        channel="gp",
        country="ID",
    )
    # 必须硬拒
    assert body["has_update"] is False
    # popup_buttons 字段存在但为空列表
    assert body.get("popup_buttons") == []
    # 所有 popup 文案字段为 None（response_model 缺省）
    for k in (
        "popup_title",
        "popup_content",
        "confirm_text",
        "cancel_text",
        "target_version_code",
        "target_version_name",
        "is_force",
        "can_skip",
        "popup_strategy",
        "popup_interval_hours",
        "download_url",
        "sha256",
        "size",
    ):
        assert body.get(k) is None, f"Play 漏出字段 {k}={body.get(k)!r}"


def test_non_play_channel_returns_popup_buttons_normally(
    client: TestClient, db: Session, seeded: dict
) -> None:
    """同一条 apply-to-all 规则换 direct（非 Play）渠道 → popup_buttons 正常输出。"""
    _add_apply_to_all_rule_with_buttons(
        db,
        app_id=seeded["app"].id,
        admin_id=seeded["admin_id"],
        popup_buttons=[
            {
                "id": "btn_update_direct",
                "type": "inapp_apk",
                "text_i18n": {"en": "Update Now", "id": "Perbarui Sekarang"},
                "url_i18n": {
                    "en": "https://cdn.example.com/u.apk",
                    "id": "https://cdn.example.com/u.apk",
                },
                "style": "primary",
            },
            {
                "id": "btn_close",
                "type": "none",
                "text_i18n": {"en": "Later", "id": "Nanti"},
            },
        ],
    )
    _, body, _ = _signed_call(
        client,
        hmac_secret="secret-play-leak",
        tenant_uuid=seeded["app"].tenant_uuid,
        channel="direct",
        country="ID",
    )
    assert body["has_update"] is True
    btns = body["popup_buttons"]
    assert len(btns) == 2
    assert btns[0]["id"] == "btn_update_direct"
    assert btns[0]["text"] == "Perbarui Sekarang"
    assert btns[0]["url"] == "https://cdn.example.com/u.apk"
    assert btns[1]["id"] == "btn_close"
    assert btns[1]["type"] == "none"
    # 间接验证 popup_title 也正常出（locale=id）
    assert body["popup_title"] == "JudulBocor"


def test_play_store_channel_request_does_not_leak_button_fields(
    client: TestClient, db: Session, seeded: dict
) -> None:
    """端到端文本扫描兜底：Play 渠道的 response JSON 不得包含任何配置的
    按钮 text / url 字符串内容（防止未来 i18n 字段被绕过短路）。
    """
    button_text_en = "PlayLeakButtonTextEN_zfx"
    button_text_id = "PlayLeakButtonTextID_zfx"
    button_url = "https://play.google.com/store/apps/details?id=zfx.leak.canary"

    _add_apply_to_all_rule_with_buttons(
        db,
        app_id=seeded["app"].id,
        admin_id=seeded["admin_id"],
        popup_buttons=[
            {
                "id": "btn_canary",
                "type": "browser",
                "text_i18n": {"en": button_text_en, "id": button_text_id},
                "url_i18n": {"en": button_url, "id": button_url},
            },
        ],
    )
    _, body, raw_text = _signed_call(
        client,
        hmac_secret="secret-play-leak",
        tenant_uuid=seeded["app"].tenant_uuid,
        channel="gp",
        country="ID",
    )
    # 结构层
    assert body["has_update"] is False
    assert body["popup_buttons"] == []
    # 原始 response body 文本层（防御 schema 演化时漏出）
    assert button_text_en not in raw_text
    assert button_text_id not in raw_text
    assert button_url not in raw_text
    # 顺便保证 popup_title 配置文本也不漏
    assert "PlayLeakTitle" not in raw_text
    assert "JudulBocor" not in raw_text
    # JSON 解析层也再扫一次
    serialized = json.dumps(body)
    assert button_text_en not in serialized
    assert button_url not in serialized
