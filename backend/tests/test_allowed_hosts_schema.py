"""M1.T4 — allowed_upgrade_hosts 在 AppCreate / AppUpdate 上的 schema 层归一化与校验。

存纯 host（不含 scheme/path/port），自动 lowercase + 去重保序，最多 50 个。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.channel_pack.schemas import AppCreate, AppUpdate


def _make(hosts: list[str]) -> AppCreate:
    return AppCreate(name="t", package_name="com.t.app", allowed_upgrade_hosts=hosts)


def test_valid_simple_host():
    m = _make(["example.com"])
    assert m.allowed_upgrade_hosts == ["example.com"]


def test_valid_subdomain():
    m = _make(["cdn.example.com", "api.example.com"])
    assert m.allowed_upgrade_hosts == ["cdn.example.com", "api.example.com"]


def test_reject_uppercase_input_auto_lowercased():
    m = _make(["CDN.example.com"])
    assert m.allowed_upgrade_hosts == ["cdn.example.com"]


def test_reject_with_scheme_https():
    with pytest.raises(ValidationError) as ei:
        _make(["https://cdn.example.com"])
    assert "no scheme/path/port" in str(ei.value)


def test_reject_with_path():
    with pytest.raises(ValidationError) as ei:
        _make(["cdn.example.com/api"])
    assert "no scheme/path/port" in str(ei.value)


def test_reject_with_port_8080():
    with pytest.raises(ValidationError) as ei:
        _make(["cdn.example.com:8080"])
    assert "no scheme/path/port" in str(ei.value)


def test_normalize_dedup():
    m = _make(["A.com", "a.com", "B.com"])
    assert m.allowed_upgrade_hosts == ["a.com", "b.com"]


def test_empty_list_ok():
    m = _make([])
    assert m.allowed_upgrade_hosts == []


def test_default_empty_when_omitted():
    m = AppCreate(name="t", package_name="com.t.app")
    assert m.allowed_upgrade_hosts == []


def test_blank_strings_dropped():
    m = _make(["", "  ", "good.com"])
    assert m.allowed_upgrade_hosts == ["good.com"]


def test_reject_with_space():
    with pytest.raises(ValidationError) as ei:
        _make(["bad host.com"])
    assert "no scheme/path/port" in str(ei.value)


def test_reject_single_label():
    """example（无 TLD）应被 HOST_REGEX 拒绝"""
    with pytest.raises(ValidationError) as ei:
        _make(["example"])
    assert "invalid host format" in str(ei.value)


def test_reject_leading_hyphen():
    with pytest.raises(ValidationError) as ei:
        _make(["-bad.com"])
    assert "invalid host format" in str(ei.value)


def test_reject_trailing_dot():
    with pytest.raises(ValidationError) as ei:
        _make(["bad.com."])
    assert "invalid host format" in str(ei.value)


def test_max_length_50_ok():
    hosts = [f"h{i}.example.com" for i in range(50)]
    m = _make(hosts)
    assert len(m.allowed_upgrade_hosts) == 50


def test_51_rejected():
    hosts = [f"h{i}.example.com" for i in range(51)]
    with pytest.raises(ValidationError):
        _make(hosts)


def test_update_none_means_no_change():
    """patch 语义：不传字段时为 None，不触发归一化。"""
    u = AppUpdate()
    assert u.allowed_upgrade_hosts is None


def test_update_empty_list_clears():
    """patch 显式传 [] 表示清空。"""
    u = AppUpdate(allowed_upgrade_hosts=[])
    assert u.allowed_upgrade_hosts == []


def test_update_normalizes_same_as_create():
    u = AppUpdate(allowed_upgrade_hosts=["A.com", "a.com"])
    assert u.allowed_upgrade_hosts == ["a.com"]


def test_update_rejects_scheme():
    with pytest.raises(ValidationError):
        AppUpdate(allowed_upgrade_hosts=["http://x.com"])
