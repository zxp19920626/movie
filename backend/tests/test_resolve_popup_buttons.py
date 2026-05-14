"""resolve_popup_buttons 单测（M1.T6 / C4）。

覆盖：
- happy path：完整按钮按 locales 拍平
- 丢弃：text 缺失 / 非 none 类型 url 缺失
- 保留：type='none' 无 url
- pick_i18n lang-only fallback
- 空输入
- 输入顺序保持
"""

from __future__ import annotations

from app.modules.channel_pack.services.popup_button_resolver import (
    resolve_popup_buttons,
)


def test_resolve_happy_3_buttons():
    buttons = [
        {
            "id": "btn_update",
            "type": "browser",
            "text_i18n": {"en": "Update", "zh": "升级"},
            "url_i18n": {"en": "https://example.com/u/en", "zh": "https://example.com/u/zh"},
            "style": "primary",
        },
        {
            "id": "btn_store",
            "type": "playstore",
            "text_i18n": {"en": "Open Store"},
            "url_i18n": {"en": "market://details?id=foo"},
        },
        {
            "id": "btn_close",
            "type": "none",
            "text_i18n": {"en": "Close"},
        },
    ]
    out = resolve_popup_buttons(buttons, ["en"])
    assert len(out) == 3
    assert out[0] == {
        "id": "btn_update",
        "type": "browser",
        "text": "Update",
        "url": "https://example.com/u/en",
        "style": "primary",
    }
    assert out[1] == {
        "id": "btn_store",
        "type": "playstore",
        "text": "Open Store",
        "url": "market://details?id=foo",
    }
    assert out[2] == {
        "id": "btn_close",
        "type": "none",
        "text": "Close",
    }
    # type='none' 不应携带 url 字段
    assert "url" not in out[2]


def test_drop_button_missing_url():
    # type=browser url_i18n['en'] 缺 → 整个按钮丢弃
    buttons = [
        {
            "id": "btn_bad",
            "type": "browser",
            "text_i18n": {"en": "Update"},
            "url_i18n": {"zh": "https://example.com/zh"},
        },
    ]
    out = resolve_popup_buttons(buttons, ["en"])
    assert out == []


def test_drop_button_missing_text():
    # text_i18n 不含 'en' → 丢弃整个按钮
    buttons = [
        {
            "id": "btn_no_text",
            "type": "browser",
            "text_i18n": {"zh": "升级"},
            "url_i18n": {"en": "https://example.com/u"},
        },
    ]
    out = resolve_popup_buttons(buttons, ["en"])
    assert out == []


def test_keep_none_type_button_without_url():
    # type='none' 即使 url_i18n 为空也保留
    buttons = [
        {
            "id": "btn_close",
            "type": "none",
            "text_i18n": {"en": "Close"},
        },
    ]
    out = resolve_popup_buttons(buttons, ["en"])
    assert len(out) == 1
    assert out[0]["id"] == "btn_close"
    assert out[0]["type"] == "none"
    assert out[0]["text"] == "Close"
    assert "url" not in out[0]


def test_fallback_url_lang_only():
    # url_i18n 只有 'en'，locales=['en-US'] 应 lang-only fallback 到 'en'
    buttons = [
        {
            "id": "btn_u",
            "type": "browser",
            "text_i18n": {"en": "Update"},
            "url_i18n": {"en": "https://example.com/u"},
        },
    ]
    out = resolve_popup_buttons(buttons, ["en-US"])
    assert len(out) == 1
    assert out[0]["text"] == "Update"
    assert out[0]["url"] == "https://example.com/u"


def test_empty_input_returns_empty():
    assert resolve_popup_buttons([], ["en"]) == []
    assert resolve_popup_buttons([], []) == []


def test_preserve_order():
    # 4 个按钮，第 2 个 url 缺失被丢弃 → 输出顺序为输入的 1, 3, 4
    buttons = [
        {
            "id": "b1",
            "type": "browser",
            "text_i18n": {"en": "One"},
            "url_i18n": {"en": "https://example.com/1"},
        },
        {
            "id": "b2_drop",
            "type": "browser",
            "text_i18n": {"en": "Two"},
            "url_i18n": {"zh": "https://example.com/2"},  # 无 en → drop
        },
        {
            "id": "b3",
            "type": "playstore",
            "text_i18n": {"en": "Three"},
            "url_i18n": {"en": "market://three"},
        },
        {
            "id": "b4",
            "type": "none",
            "text_i18n": {"en": "Four"},
        },
    ]
    out = resolve_popup_buttons(buttons, ["en"])
    assert [b["id"] for b in out] == ["b1", "b3", "b4"]
