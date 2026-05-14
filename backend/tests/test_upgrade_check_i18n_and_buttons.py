"""M2.T2 + M2.T3：/upgrade/check 接入 i18n helper + 输出 popup_buttons。

T2（i18n 路由）：
- country=ID → 'id'
- country=未知 + Accept-Language='en-US' → 'en'
- country=ID + Accept-Language='en' → 'id'（country 优先）
- 都缺 → 默认 'en'
- 4 个老 i18n 字段统一使用 helper（间接验证：切 country 4 字段都跟着切）

T3（popup_buttons 解析）：
- 老规则空 buttons → response.popup_buttons=[]
- 2 个按钮（browser + none） → response 含 2 个 resolved
- type=browser url_i18n 缺当前 locale → 该按钮丢弃
- type=none 无 url → 保留
- 多按钮输出保留顺序
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
from app.modules.channel_pack.services.hmac_verifier import compute_signature


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    test_app = FastAPI()
    test_app.include_router(api_v1)

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    test_app.dependency_overrides[get_db] = _override_get_db
    # 清掉跨测试可能残留的 app_registry 进程内缓存
    app_registry._cache.clear()

    with TestClient(test_app) as c:
        yield c

    test_app.dependency_overrides.clear()
    app_registry._cache.clear()


@pytest.fixture
def seeded(db: Session, admin_id: int) -> dict:
    """种 1 个 App + direct 渠道 + v100/v200 + v200 已签 job。
    每个测试再单独 add 一条 CpUpgradeRule 即可。
    """
    app = CpApp(
        tenant_uuid="tenant-i18n",
        name="A",
        package_name="com.t.i18n",
        owner_admin_user_id=admin_id,
        api_key_hash="x",
        hmac_secret="secret-i18n",
        status="active",
    )
    db.add(app)
    db.flush()

    direct = CpChannel(
        app_id=app.id, code="direct", name="Direct",
        is_play_store=False, enabled=True, priority=10,
    )
    db.add(direct)

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

    job = CpApkSigningJob(
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
    db.add(job)
    db.flush()
    db.commit()

    return {"app": app, "admin_id": admin_id}


def _add_rule(
    db: Session,
    *,
    app_id: int,
    admin_id: int,
    popup_title_i18n: dict[str, str] | None = None,
    popup_content_i18n: dict[str, str] | None = None,
    confirm_text_i18n: dict[str, str] | None = None,
    cancel_text_i18n: dict[str, str] | None = None,
    popup_buttons: list[dict] | None = None,
) -> CpUpgradeRule:
    rule = CpUpgradeRule(
        app_id=app_id,
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
        popup_title_i18n=popup_title_i18n or {},
        popup_content_i18n=popup_content_i18n or {},
        confirm_text_i18n=confirm_text_i18n or {},
        cancel_text_i18n=cancel_text_i18n or {},
        popup_buttons=popup_buttons or [],
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
    country: str = "",
    accept_language: str | None = None,
    device_id: str = "device-x",
    channel: str = "direct",
    version_code: int = 100,
) -> dict:
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
    headers = {}
    if accept_language is not None:
        headers["Accept-Language"] = accept_language
    # 同一测试内多次调用会命中 app_registry 进程缓存导致 db override 后看不到新写入的 App
    # → 清缓存兜底
    app_registry._cache.clear()
    resp = client.get("/api/v1/cp/upgrade/check", params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ===================== T2: i18n 路由 =====================


def test_upgrade_check_picks_country_locale(
    client: TestClient, db: Session, seeded: dict
) -> None:
    """country=ID → 走 'id' 语言（验证 choose_locale + pick_i18n 接通）。"""
    _add_rule(
        db,
        app_id=seeded["app"].id,
        admin_id=seeded["admin_id"],
        popup_title_i18n={"en": "Update", "id": "Pembaruan"},
        popup_content_i18n={"en": "New version", "id": "Versi baru"},
        confirm_text_i18n={"en": "OK", "id": "OKE"},
        cancel_text_i18n={"en": "Later", "id": "Nanti"},
    )
    body = _signed_call(
        client, hmac_secret="secret-i18n",
        tenant_uuid=seeded["app"].tenant_uuid, country="ID",
    )
    assert body["has_update"] is True
    assert body["popup_title"] == "Pembaruan"
    assert body["popup_content"] == "Versi baru"
    assert body["confirm_text"] == "OKE"
    assert body["cancel_text"] == "Nanti"


def test_upgrade_check_accept_language_fallback(
    client: TestClient, db: Session, seeded: dict
) -> None:
    """country=未知 + Accept-Language='en-US' → 走 'en'。"""
    _add_rule(
        db,
        app_id=seeded["app"].id,
        admin_id=seeded["admin_id"],
        popup_title_i18n={"en": "Update", "id": "Pembaruan"},
    )
    body = _signed_call(
        client, hmac_secret="secret-i18n",
        tenant_uuid=seeded["app"].tenant_uuid,
        country="ZZ", accept_language="en-US,en;q=0.9",
    )
    assert body["popup_title"] == "Update"


def test_upgrade_check_country_priority_over_accept_language(
    client: TestClient, db: Session, seeded: dict
) -> None:
    """country=ID + Accept-Language='en' → 走 'id'（country 优先）。"""
    _add_rule(
        db,
        app_id=seeded["app"].id,
        admin_id=seeded["admin_id"],
        popup_title_i18n={"en": "Update", "id": "Pembaruan"},
    )
    body = _signed_call(
        client, hmac_secret="secret-i18n",
        tenant_uuid=seeded["app"].tenant_uuid,
        country="ID", accept_language="en",
    )
    assert body["popup_title"] == "Pembaruan"


def test_upgrade_check_missing_country_and_al_defaults_en(
    client: TestClient, db: Session, seeded: dict
) -> None:
    """country 和 Accept-Language 都缺 → 走默认 'en'。"""
    _add_rule(
        db,
        app_id=seeded["app"].id,
        admin_id=seeded["admin_id"],
        popup_title_i18n={"en": "Update", "id": "Pembaruan"},
    )
    body = _signed_call(
        client, hmac_secret="secret-i18n",
        tenant_uuid=seeded["app"].tenant_uuid,
        country="", accept_language=None,
    )
    assert body["popup_title"] == "Update"


def test_upgrade_check_old_4_fields_use_helper(
    client: TestClient, db: Session, seeded: dict
) -> None:
    """切 country 时 popup_title/content/confirm/cancel 4 字段一起切。
    间接验证：4 个老字段都走 helper（不再用 inline 死表）。
    """
    _add_rule(
        db,
        app_id=seeded["app"].id,
        admin_id=seeded["admin_id"],
        popup_title_i18n={"en": "T-en", "vi": "T-vi"},
        popup_content_i18n={"en": "C-en", "vi": "C-vi"},
        confirm_text_i18n={"en": "OK-en", "vi": "OK-vi"},
        cancel_text_i18n={"en": "X-en", "vi": "X-vi"},
    )
    # country=VN → choose_locale 第一个是 'vi'
    body_vn = _signed_call(
        client, hmac_secret="secret-i18n",
        tenant_uuid=seeded["app"].tenant_uuid, country="VN",
    )
    assert body_vn["popup_title"] == "T-vi"
    assert body_vn["popup_content"] == "C-vi"
    assert body_vn["confirm_text"] == "OK-vi"
    assert body_vn["cancel_text"] == "X-vi"

    # 切回未知 country → 全部回 'en'
    body_en = _signed_call(
        client, hmac_secret="secret-i18n",
        tenant_uuid=seeded["app"].tenant_uuid, country="ZZ",
    )
    assert body_en["popup_title"] == "T-en"
    assert body_en["popup_content"] == "C-en"
    assert body_en["confirm_text"] == "OK-en"
    assert body_en["cancel_text"] == "X-en"


# ===================== T3: popup_buttons =====================


def test_response_has_popup_buttons_field_empty_for_legacy_rule(
    client: TestClient, db: Session, seeded: dict
) -> None:
    """老规则未配 popup_buttons → response.popup_buttons=[]（向后兼容）。"""
    _add_rule(
        db,
        app_id=seeded["app"].id,
        admin_id=seeded["admin_id"],
        popup_title_i18n={"en": "U"},
        popup_buttons=[],
    )
    body = _signed_call(
        client, hmac_secret="secret-i18n",
        tenant_uuid=seeded["app"].tenant_uuid, country="US",
    )
    assert body["popup_buttons"] == []


def test_response_with_2_buttons_resolved(
    client: TestClient, db: Session, seeded: dict
) -> None:
    """2 个按钮（browser + none）→ response 含 2 个 resolved。"""
    _add_rule(
        db,
        app_id=seeded["app"].id,
        admin_id=seeded["admin_id"],
        popup_title_i18n={"en": "U"},
        popup_buttons=[
            {
                "id": "btn_update",
                "type": "browser",
                "text_i18n": {"en": "Update", "id": "Perbarui"},
                "url_i18n": {"en": "https://example.com/u", "id": "https://example.com/u-id"},
                "style": "primary",
            },
            {
                "id": "btn_close",
                "type": "none",
                "text_i18n": {"en": "Later", "id": "Nanti"},
            },
        ],
    )
    body = _signed_call(
        client, hmac_secret="secret-i18n",
        tenant_uuid=seeded["app"].tenant_uuid, country="ID",
    )
    btns = body["popup_buttons"]
    assert len(btns) == 2
    assert btns[0]["id"] == "btn_update"
    assert btns[0]["type"] == "browser"
    assert btns[0]["text"] == "Perbarui"
    assert btns[0]["url"] == "https://example.com/u-id"
    assert btns[0]["style"] == "primary"
    assert btns[1]["id"] == "btn_close"
    assert btns[1]["type"] == "none"
    assert btns[1]["text"] == "Nanti"
    assert btns[1].get("url") is None


def test_response_drops_button_missing_url_in_picked_locale(
    client: TestClient, db: Session, seeded: dict
) -> None:
    """type=browser 的按钮在当前 locale 缺 url → resolver 丢弃。"""
    _add_rule(
        db,
        app_id=seeded["app"].id,
        admin_id=seeded["admin_id"],
        popup_title_i18n={"en": "U"},
        popup_buttons=[
            {
                # text 在所有语言都有，但 url 只有 'id'，当前 locale='en' 时 helper 拿不到 url → 丢弃
                "id": "btn_url_only_id",
                "type": "browser",
                "text_i18n": {"en": "Update", "id": "Perbarui"},
                "url_i18n": {"id": "https://example.com/u-id"},
            },
            {
                "id": "btn_ok",
                "type": "browser",
                "text_i18n": {"en": "OK"},
                "url_i18n": {"en": "https://example.com/ok"},
            },
        ],
    )
    body = _signed_call(
        client, hmac_secret="secret-i18n",
        tenant_uuid=seeded["app"].tenant_uuid, country="",  # → 'en'
    )
    btns = body["popup_buttons"]
    assert len(btns) == 1
    assert btns[0]["id"] == "btn_ok"


def test_response_none_type_button_kept_without_url(
    client: TestClient, db: Session, seeded: dict
) -> None:
    """type=none 无 url_i18n → 仍保留（关闭按钮场景）。"""
    _add_rule(
        db,
        app_id=seeded["app"].id,
        admin_id=seeded["admin_id"],
        popup_title_i18n={"en": "U"},
        popup_buttons=[
            {
                "id": "btn_close",
                "type": "none",
                "text_i18n": {"en": "Close"},
            },
        ],
    )
    body = _signed_call(
        client, hmac_secret="secret-i18n",
        tenant_uuid=seeded["app"].tenant_uuid, country="",
    )
    btns = body["popup_buttons"]
    assert len(btns) == 1
    assert btns[0]["type"] == "none"
    assert btns[0]["text"] == "Close"
    assert btns[0].get("url") is None


def test_response_popup_buttons_preserve_order(
    client: TestClient, db: Session, seeded: dict
) -> None:
    """多按钮 → 输出顺序保留与输入一致（PRD 4.2.5.1）。"""
    _add_rule(
        db,
        app_id=seeded["app"].id,
        admin_id=seeded["admin_id"],
        popup_title_i18n={"en": "U"},
        popup_buttons=[
            {"id": "a", "type": "none", "text_i18n": {"en": "A"}},
            {"id": "b", "type": "browser", "text_i18n": {"en": "B"},
             "url_i18n": {"en": "https://example.com/b"}},
            {"id": "c", "type": "none", "text_i18n": {"en": "C"}},
            {"id": "d", "type": "deeplink", "text_i18n": {"en": "D"},
             "url_i18n": {"en": "myapp://d"}},
        ],
    )
    body = _signed_call(
        client, hmac_secret="secret-i18n",
        tenant_uuid=seeded["app"].tenant_uuid, country="",
    )
    ids = [b["id"] for b in body["popup_buttons"]]
    assert ids == ["a", "b", "c", "d"]
