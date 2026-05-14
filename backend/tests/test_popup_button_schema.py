"""M1.T3：PopupButton + RuleCreate.popup_buttons Pydantic 严格 schema 校验。

覆盖 PRD 4.2.5.1 的严格校验项：
- type 枚举（browser/playstore/inapp_apk/deeplink/none）
- maxLength=5 数组
- text_i18n 字符串 maxLength=200
- i18n key 正则 ^[a-z]{2}(-[A-Z]{2})?$
- url_i18n 在 type != 'none' 时必填
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.channel_pack.schemas import PopupButton, RuleCreate


def _make_button(**overrides) -> dict:
    base = {
        "id": "btn_update",
        "type": "browser",
        "text_i18n": {"en": "Update"},
        "url_i18n": {"en": "https://example.com/update"},
    }
    base.update(overrides)
    return base


def _make_rule_payload(buttons: list[dict]) -> dict:
    return {
        "name": "r1",
        "version_code_min": 0,
        "version_code_max": 999,
        "target_version_code": 200,
        "popup_buttons": buttons,
    }


# ============== 数组长度 ==============


def test_empty_list_ok():
    rule = RuleCreate(**_make_rule_payload([]))
    assert rule.popup_buttons == []


def test_exactly_5_buttons_ok():
    buttons = [_make_button(id=f"b{i}") for i in range(5)]
    rule = RuleCreate(**_make_rule_payload(buttons))
    assert len(rule.popup_buttons) == 5


def test_6_buttons_rejected():
    buttons = [_make_button(id=f"b{i}") for i in range(6)]
    with pytest.raises(ValidationError) as excinfo:
        RuleCreate(**_make_rule_payload(buttons))
    assert "popup_buttons" in str(excinfo.value)


# ============== type 枚举 ==============


def test_unknown_type_rejected():
    # 旧的 'jump_browser' 枚举值应被拒
    with pytest.raises(ValidationError) as excinfo:
        PopupButton(**_make_button(type="jump_browser"))
    assert "type" in str(excinfo.value)


# ============== text_i18n 字符串长度 ==============


def test_text_i18n_value_201_char_rejected():
    too_long = "a" * 201
    with pytest.raises(ValidationError) as excinfo:
        PopupButton(**_make_button(text_i18n={"en": too_long}))
    assert "text_i18n" in str(excinfo.value)


def test_text_i18n_value_200_char_ok():
    just_ok = "a" * 200
    btn = PopupButton(**_make_button(text_i18n={"en": just_ok}))
    assert btn.text_i18n["en"] == just_ok


# ============== i18n key 正则 ==============


def test_text_i18n_key_invalid_regex_rejected():
    # 大写 'EN' 应被拒
    with pytest.raises(ValidationError) as excinfo:
        PopupButton(**_make_button(text_i18n={"EN": "Update"}))
    assert "text_i18n" in str(excinfo.value)

    # 长格式 'english' 应被拒
    with pytest.raises(ValidationError) as excinfo:
        PopupButton(**_make_button(text_i18n={"english": "Update"}))
    assert "text_i18n" in str(excinfo.value)


def test_text_i18n_key_with_country_suffix_ok():
    # 'en-US' 应被接受
    btn = PopupButton(**_make_button(text_i18n={"en-US": "Update"}))
    assert btn.text_i18n["en-US"] == "Update"


# ============== text_i18n 空字典 ==============


def test_text_i18n_empty_dict_rejected():
    with pytest.raises(ValidationError) as excinfo:
        PopupButton(**_make_button(text_i18n={}))
    assert "text_i18n" in str(excinfo.value)


# ============== url_i18n optional 与 type 联动 ==============


def test_url_i18n_optional_for_none_type():
    btn = PopupButton(
        **_make_button(type="none", url_i18n=None, text_i18n={"en": "Close"})
    )
    assert btn.type == "none"
    assert btn.url_i18n is None


def test_url_i18n_required_for_browser_type():
    with pytest.raises(ValidationError) as excinfo:
        PopupButton(**_make_button(type="browser", url_i18n=None))
    assert "url_i18n" in str(excinfo.value)


def test_url_i18n_required_for_playstore_type():
    with pytest.raises(ValidationError) as excinfo:
        PopupButton(**_make_button(type="playstore", url_i18n=None))
    assert "url_i18n" in str(excinfo.value)


def test_url_i18n_empty_dict_treated_as_missing_for_non_none():
    # url_i18n={} 在 model_validator 里 `not self.url_i18n` 会判 True → 报错
    with pytest.raises(ValidationError) as excinfo:
        PopupButton(**_make_button(type="browser", url_i18n={}))
    assert "url_i18n" in str(excinfo.value)
