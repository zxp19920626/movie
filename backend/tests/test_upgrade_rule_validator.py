"""M1.T7：upgrade_rule_validator 单测（C1 + C2 + https-only + host 白名单）。

覆盖：
- Play Store 渠道禁 inapp_apk
- 非 Play Store 渠道允许 inapp_apk
- 非 https URL 拒
- host 不在白名单拒
- host 在白名单通过
- 子域名严格匹配（cdn.example.com 不命中 example.com）
- buttons=[] 通过
- type='none' 无 url_i18n 通过
"""

from __future__ import annotations

import pytest

from app.modules.channel_pack.models import CpApp, CpChannel
from app.modules.channel_pack.schemas import PopupButton
from app.modules.channel_pack.services.upgrade_rule_validator import (
    UpgradeRuleValidationError,
    validate_buttons_for_app,
)


def _app(allowed_hosts: list[str]) -> CpApp:
    return CpApp(
        tenant_uuid="t-1",
        name="t",
        package_name="com.t",
        owner_admin_user_id=1,
        api_key_hash="x",
        hmac_secret="x",
        status="active",
        allowed_upgrade_hosts=allowed_hosts,
    )


def _channel(is_play_store: bool) -> CpChannel:
    return CpChannel(
        app_id=1,
        code="ch",
        name="Channel",
        is_play_store=is_play_store,
        signing_strategy="walle",
        enabled=True,
        priority=10,
    )


def _btn(
    *,
    btn_id: str = "b1",
    btn_type: str = "browser",
    url: str | None = "https://example.com/u",
    extra_urls: dict[str, str] | None = None,
) -> PopupButton:
    url_i18n: dict[str, str] | None
    if url is None and not extra_urls:
        url_i18n = None
    else:
        url_i18n = {}
        if url is not None:
            url_i18n["en"] = url
        if extra_urls:
            url_i18n.update(extra_urls)
    return PopupButton(
        id=btn_id,
        type=btn_type,
        text_i18n={"en": "Click"},
        url_i18n=url_i18n,
    )


def test_play_channel_inapp_apk_rejected():
    app = _app(["example.com"])
    channel = _channel(is_play_store=True)
    buttons = [_btn(btn_type="inapp_apk", url="https://example.com/a.apk")]
    with pytest.raises(UpgradeRuleValidationError) as ei:
        validate_buttons_for_app(app, channel, buttons)
    assert "play_store_channel_rejects_inapp_apk" in str(ei.value)


def test_play_channel_browser_type_ok():
    app = _app(["example.com"])
    channel = _channel(is_play_store=True)
    buttons = [_btn(btn_type="browser", url="https://example.com/page")]
    validate_buttons_for_app(app, channel, buttons)  # no raise


def test_non_play_channel_inapp_apk_ok():
    app = _app(["cdn.example.com"])
    channel = _channel(is_play_store=False)
    buttons = [_btn(btn_type="inapp_apk", url="https://cdn.example.com/a.apk")]
    validate_buttons_for_app(app, channel, buttons)  # no raise


def test_http_url_rejected():
    app = _app(["example.com"])
    channel = _channel(is_play_store=False)
    buttons = [_btn(btn_type="browser", url="http://example.com/u")]
    with pytest.raises(UpgradeRuleValidationError) as ei:
        validate_buttons_for_app(app, channel, buttons)
    assert "https_only" in str(ei.value)


def test_host_not_in_whitelist_rejected():
    app = _app(["example.com"])
    channel = _channel(is_play_store=False)
    buttons = [_btn(btn_type="browser", url="https://evil.com/u")]
    with pytest.raises(UpgradeRuleValidationError) as ei:
        validate_buttons_for_app(app, channel, buttons)
    msg = str(ei.value)
    assert "host_not_in_whitelist" in msg
    assert "evil.com" in msg
    assert "example.com" in msg  # whitelist included in message


def test_host_in_whitelist_ok():
    app = _app(["example.com", "cdn.other.com"])
    channel = _channel(is_play_store=False)
    buttons = [
        _btn(btn_id="b1", btn_type="browser", url="https://example.com/u"),
        _btn(btn_id="b2", btn_type="browser", url="https://cdn.other.com/u"),
    ]
    validate_buttons_for_app(app, channel, buttons)  # no raise


def test_subdomain_exact_match_required():
    # whitelist=['example.com']，url host='cdn.example.com' → 拒（不含子域名）
    app = _app(["example.com"])
    channel = _channel(is_play_store=False)
    buttons = [_btn(btn_type="browser", url="https://cdn.example.com/u")]
    with pytest.raises(UpgradeRuleValidationError) as ei:
        validate_buttons_for_app(app, channel, buttons)
    assert "host_not_in_whitelist" in str(ei.value)
    assert "cdn.example.com" in str(ei.value)


def test_empty_buttons_passes():
    app = _app(["example.com"])
    channel = _channel(is_play_store=True)
    validate_buttons_for_app(app, channel, [])  # no raise


def test_none_type_no_url_ok():
    # type='none' + url_i18n=None → 跳过 https / host 检查
    app = _app([])  # 空白名单也无所谓
    channel = _channel(is_play_store=True)
    buttons = [
        PopupButton(
            id="close",
            type="none",
            text_i18n={"en": "Close"},
            url_i18n=None,
        )
    ]
    validate_buttons_for_app(app, channel, buttons)  # no raise


def test_channel_none_treated_as_non_play():
    # channel=None（如 rule.channel_codes=[] 适用所有渠道）→ 不触发 Play 限制
    app = _app(["example.com"])
    buttons = [_btn(btn_type="inapp_apk", url="https://example.com/a.apk")]
    validate_buttons_for_app(app, None, buttons)  # no raise


def test_multi_locale_url_each_checked():
    # url_i18n 有多个 locale，每个都必须通过 https + host 校验
    app = _app(["example.com"])
    channel = _channel(is_play_store=False)
    buttons = [
        _btn(
            btn_type="browser",
            url="https://example.com/en",
            extra_urls={"zh": "https://evil.com/zh"},
        )
    ]
    with pytest.raises(UpgradeRuleValidationError) as ei:
        validate_buttons_for_app(app, channel, buttons)
    assert "host_not_in_whitelist" in str(ei.value)
    assert "evil.com" in str(ei.value)
