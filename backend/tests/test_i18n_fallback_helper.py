"""i18n_fallback helper 单测：choose_locale + pick_i18n（M1.T5 / C4）。"""

from __future__ import annotations

from app.modules.channel_pack.services.i18n_fallback import (
    choose_locale,
    pick_i18n,
)


def test_pick_exact_match():
    d = {"en-US": "Hello", "zh-CN": "你好"}
    assert pick_i18n(d, ["en-US"]) == "Hello"


def test_pick_lang_only_fallback():
    # dict 只有 'en'，locales=['en-US'] 命中 'en'
    d = {"en": "Hello"}
    assert pick_i18n(d, ["en-US"]) == "Hello"


def test_pick_default_locale_fallback():
    # locales 全 miss，但 default_locale='en' 存在
    d = {"en": "Hello"}
    assert pick_i18n(d, ["fr"], default_locale="en") == "Hello"


def test_pick_returns_none_if_all_missing():
    # 空 dict
    assert pick_i18n({}, ["en-US", "zh-CN"]) is None
    # 非空 dict 但无可用 key
    assert pick_i18n({"de": "Hallo"}, ["fr"], default_locale="ja") is None


def test_pick_first_non_empty_wins():
    # locales 顺序应被尊重：优先链上第一个非空命中
    d = {"id": "Halo", "en": "Hello"}
    assert pick_i18n(d, ["id", "en"]) == "Halo"
    assert pick_i18n(d, ["en", "id"]) == "Hello"


def test_pick_skips_empty_string_falls_through():
    # 空字符串当缺失处理，继续后续优先级
    d = {"id": "", "en": "Hello"}
    assert pick_i18n(d, ["id", "en"]) == "Hello"


def test_choose_country_first():
    # country='ID' AL='en' → 'id' 应排在 'en' 之前
    chain = choose_locale("ID", "en")
    assert chain.index("id") < chain.index("en")


def test_choose_accept_language_parse():
    # q 值排序：q=1 优先于 q=0.5
    chain = choose_locale(None, "id-ID;q=1, en;q=0.5")
    assert chain[0] == "id-ID"
    # 应包含 lang-only 兜底 'id'
    assert "id" in chain
    # en 在 id 系列之后
    assert chain.index("en") > chain.index("id-ID")


def test_choose_dedup():
    # country='ID' AL='id,en' → 'id' 只出现一次，保序
    chain = choose_locale("ID", "id,en")
    assert chain.count("id") == 1
    assert "id" in chain
    assert "en" in chain
    # id 来自 country 应排在 en 之前
    assert chain.index("id") < chain.index("en")


def test_choose_handles_empty_inputs():
    # 双 None → 兜底返回 ['en']
    assert choose_locale(None, None) == ["en"]
    # 空字符串同样兜底
    assert choose_locale("", "") == ["en"]


def test_choose_accept_language_normalizes_region_case():
    # 'en-us' → 'en-US'，'ZH-cn' → 'zh-CN'
    chain = choose_locale(None, "en-us, zh-cn;q=0.8")
    assert "en-US" in chain
    assert "zh-CN" in chain


def test_choose_skips_q_zero():
    # q=0 应被丢弃
    chain = choose_locale(None, "en;q=0, fr;q=0.9")
    assert "en" not in chain
    assert chain[0] == "fr"


def test_choose_unknown_country_falls_back_to_al():
    # 未知 country code → 只看 AL
    chain = choose_locale("ZZ", "en-US")
    assert chain[0] == "en-US"
    assert "en" in chain


def test_choose_country_with_region_pushes_lang_only():
    # HK 映射 'zh-HK'，链里应同时有 'zh-HK' 和 'zh'
    chain = choose_locale("HK", None)
    assert "zh-HK" in chain
    assert "zh" in chain
    assert chain.index("zh-HK") < chain.index("zh")
