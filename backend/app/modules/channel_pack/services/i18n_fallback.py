"""i18n fallback helper（C4）: 按 country + Accept-Language 选 locale 优先级链 + 字典 pick。"""

from __future__ import annotations

import re

_COUNTRY_TO_LANG: dict[str, str] = {
    "ID": "id",
    "MY": "ms",
    "TH": "th",
    "VN": "vi",
    "PH": "tl",
    "SG": "en",
    "HK": "zh-HK",
    "TW": "zh-TW",
    "CN": "zh-CN",
    "JP": "ja",
    "KR": "ko",
    "US": "en-US",
    "GB": "en-GB",
}

_AL_ENTRY_RE = re.compile(r"^\s*([A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*)\s*(?:;\s*q\s*=\s*([0-9.]+))?\s*$")


def _normalize_locale(tag: str) -> str:
    """规范化 BCP 47 tag：lang 小写，region 大写。"""
    parts = tag.split("-")
    if not parts:
        return tag
    head = parts[0].lower()
    tail = [p.upper() for p in parts[1:]]
    return "-".join([head, *tail]) if tail else head


def _lang_only(tag: str) -> str:
    return tag.split("-", 1)[0]


def _parse_accept_language(accept_language: str | None) -> list[str]:
    """解析 Accept-Language，按 q 值降序返回规范化 locale 列表。"""
    if not accept_language:
        return []
    items: list[tuple[float, int, str]] = []
    for idx, raw in enumerate(accept_language.split(",")):
        m = _AL_ENTRY_RE.match(raw)
        if not m:
            continue
        tag = m.group(1)
        if tag == "*":
            continue
        q_str = m.group(2)
        try:
            q = float(q_str) if q_str is not None else 1.0
        except ValueError:
            q = 1.0
        if q <= 0:
            continue
        items.append((q, idx, _normalize_locale(tag)))
    # q 降序，同 q 保留原顺序
    items.sort(key=lambda t: (-t[0], t[1]))
    return [tag for _, _, tag in items]


def choose_locale(country: str | None, accept_language: str | None) -> list[str]:
    """返回去重后的 locale 优先级列表（从最高到最低）。

    例: country='ID' + AL='id-ID,en-US;q=0.9'
       → ['id-ID', 'id', 'en-US', 'en']
    去重保序；country 优先于 AL；None 输入安全。
    """
    chain: list[str] = []

    def _push(tag: str) -> None:
        if tag and tag not in chain:
            chain.append(tag)

    if country:
        country_key = country.strip().upper()
        mapped = _COUNTRY_TO_LANG.get(country_key)
        if mapped:
            mapped = _normalize_locale(mapped)
            _push(mapped)
            lang = _lang_only(mapped)
            if lang != mapped:
                _push(lang)

    for tag in _parse_accept_language(accept_language):
        _push(tag)
        lang = _lang_only(tag)
        if lang != tag:
            _push(lang)

    if not chain:
        chain.append("en")
    return chain


def pick_i18n(
    d: dict[str, str], locales: list[str], default_locale: str = "en"
) -> str | None:
    """按 locales 顺序找 key，返回第一个非空值；都缺则尝试 default_locale；都缺返回 None。

    支持 lang-only fallback：locale='en-US' 在 d 找不到时，再试 'en'。
    """
    if not d:
        return None

    def _lookup(tag: str) -> str | None:
        v = d.get(tag)
        if v:
            return v
        lang = _lang_only(tag)
        if lang != tag:
            v = d.get(lang)
            if v:
                return v
        return None

    for loc in locales:
        v = _lookup(loc)
        if v:
            return v
    if default_locale and default_locale not in locales:
        v = _lookup(default_locale)
        if v:
            return v
    return None
