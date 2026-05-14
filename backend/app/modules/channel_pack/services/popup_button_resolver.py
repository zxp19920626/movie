"""升级弹窗按钮 i18n 解析（C4）

把 RuleOut.popup_buttons（含 text_i18n / url_i18n 多语言字典）解析为
端上即可渲染的扁平按钮列表：每个按钮按 locales 链选定单语 text/url。

丢弃规则：
- text 缺失 → 整个按钮丢弃
- type != 'none' 且 url 缺失 → 整个按钮丢弃（type='none' 不需要 url）

保留输入顺序，便于 PRD 4.2.5.1 中"按钮排列顺序由后台配置决定"。
"""

from __future__ import annotations

from .i18n_fallback import pick_i18n


def resolve_popup_buttons(
    buttons: list[dict],
    locales: list[str],
) -> list[dict]:
    out: list[dict] = []
    for btn in buttons:
        text = pick_i18n(btn.get("text_i18n") or {}, locales)
        if not text:
            continue

        btn_type = btn.get("type")
        url = pick_i18n(btn.get("url_i18n") or {}, locales)
        if btn_type != "none" and not url:
            continue

        resolved: dict = {
            "id": btn.get("id"),
            "type": btn_type,
            "text": text,
        }
        if url is not None:
            resolved["url"] = url
        style = btn.get("style")
        if style is not None:
            resolved["style"] = style
        target = btn.get("target")
        if target is not None:
            resolved["target"] = target
        out.append(resolved)
    return out
