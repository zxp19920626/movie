"""M2.T1：PopupButtonResolved + UpgradeCheckResponse.popup_buttons schema 校验。

覆盖：
- PopupButtonResolved 5 枚举 type（与 PopupButton 同），text/url 已挑好 locale 的扁平结构
- type='none' 时 url 可空；非 'none' 时 url 必填
- UpgradeCheckResponse.popup_buttons 默认空列表（向后兼容老客户端）
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.channel_pack.schemas import (
    PopupButtonResolved,
    UpgradeCheckResponse,
)

# ============== UpgradeCheckResponse.popup_buttons 默认行为 ==============


def test_default_popup_buttons_empty_list():
    """未传 popup_buttons → 默认 []，老客户端不受影响。"""
    resp = UpgradeCheckResponse(has_update=False)
    assert resp.popup_buttons == []


def test_legacy_fields_still_present():
    """popup_title / confirm_text 等老字段仍保留（向后兼容）。"""
    resp = UpgradeCheckResponse(
        has_update=True,
        popup_title="Update",
        popup_content="New version",
        confirm_text="OK",
        cancel_text="Later",
    )
    assert resp.popup_title == "Update"
    assert resp.popup_content == "New version"
    assert resp.confirm_text == "OK"
    assert resp.cancel_text == "Later"
    assert resp.popup_buttons == []


# ============== PopupButtonResolved 字段校验 ==============


def test_resolved_button_minimal_valid():
    """最小有效 payload：id + type=browser + text + url。"""
    btn = PopupButtonResolved(
        id="btn_update",
        type="browser",
        text="Update",
        url="https://example.com/update",
    )
    assert btn.id == "btn_update"
    assert btn.type == "browser"
    assert btn.text == "Update"
    assert btn.url == "https://example.com/update"
    assert btn.style is None
    assert btn.target is None


def test_resolved_button_none_type_no_url_ok():
    """type='none' 时 url 可为 None（关闭按钮场景）。"""
    btn = PopupButtonResolved(
        id="btn_close",
        type="none",
        text="Close",
        url=None,
    )
    assert btn.type == "none"
    assert btn.url is None


def test_resolved_button_invalid_type_rejected():
    """旧 7 枚举里的 'jump_browser' 不再有效（PRD 已定型为 5 枚举）。"""
    with pytest.raises(ValidationError) as excinfo:
        PopupButtonResolved(
            id="btn_x",
            type="jump_browser",
            text="Go",
            url="https://example.com",
        )
    assert "type" in str(excinfo.value)


def test_resolved_button_with_style_and_target():
    """style + target 字段都填正常通过。"""
    btn = PopupButtonResolved(
        id="btn_deep",
        type="deeplink",
        text="Open",
        url="myapp://path",
        style="primary",
        target={"package": "com.example.app"},
    )
    assert btn.style == "primary"
    assert btn.target == {"package": "com.example.app"}


def test_resolved_button_url_required_for_browser():
    """type != 'none' 时 url 必填，未填报错。"""
    with pytest.raises(ValidationError) as excinfo:
        PopupButtonResolved(
            id="btn_x",
            type="browser",
            text="Update",
            url=None,
        )
    assert "url" in str(excinfo.value)


def test_resolved_button_url_required_for_playstore():
    """playstore 类型同样要求 url。"""
    with pytest.raises(ValidationError) as excinfo:
        PopupButtonResolved(
            id="btn_x",
            type="playstore",
            text="Update",
            url=None,
        )
    assert "url" in str(excinfo.value)


def test_resolved_button_embedded_in_upgrade_response():
    """UpgradeCheckResponse 可包含多个 resolved 按钮。"""
    resp = UpgradeCheckResponse(
        has_update=True,
        popup_buttons=[
            {
                "id": "btn_update",
                "type": "browser",
                "text": "Update",
                "url": "https://example.com/update",
                "style": "primary",
            },
            {
                "id": "btn_close",
                "type": "none",
                "text": "Later",
            },
        ],
    )
    assert len(resp.popup_buttons) == 2
    assert isinstance(resp.popup_buttons[0], PopupButtonResolved)
    assert resp.popup_buttons[0].style == "primary"
    assert resp.popup_buttons[1].type == "none"
    assert resp.popup_buttons[1].url is None
