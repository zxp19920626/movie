"""M1.T1：CpUpgradeRule.popup_buttons / CpApp.allowed_upgrade_hosts 字段。

覆盖：
- 不指定时默认空 list
- JSON 数组写入 → flush → re-query 一致
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.modules.channel_pack.models import CpApp, CpUpgradeRule


@pytest.fixture
def app_row(db: Session, admin_id: int) -> CpApp:
    app = CpApp(
        tenant_uuid="tenant-popup-1",
        name="AppPopup",
        package_name="com.t.popup",
        owner_admin_user_id=admin_id,
        api_key_hash="x",
        hmac_secret="x",
        status="active",
    )
    db.add(app)
    db.flush()
    return app


def _add_rule(
    db: Session, app_id: int, admin_id: int, **overrides
) -> CpUpgradeRule:
    defaults = dict(
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
    )
    defaults.update(overrides)
    rule = CpUpgradeRule(**defaults)
    db.add(rule)
    db.flush()
    return rule


def test_default_popup_buttons_empty_list(db: Session, app_row: CpApp, admin_id: int):
    rule = _add_rule(db, app_row.id, admin_id)
    db.expire(rule)
    fetched = db.get(CpUpgradeRule, rule.id)
    assert fetched is not None
    assert fetched.popup_buttons == []


def test_default_allowed_hosts_empty_list(db: Session, app_row: CpApp):
    db.expire(app_row)
    fetched = db.get(CpApp, app_row.id)
    assert fetched is not None
    assert fetched.allowed_upgrade_hosts == []


def test_assign_and_read_back_popup_buttons_roundtrip(
    db: Session, app_row: CpApp, admin_id: int
):
    buttons = [
        {"id": "confirm", "label_i18n": {"en": "OK"}, "action": "upgrade"},
        {"id": "later", "label_i18n": {"en": "Later"}, "action": "dismiss"},
    ]
    rule = _add_rule(db, app_row.id, admin_id, popup_buttons=buttons)
    db.expire(rule)
    fetched = db.get(CpUpgradeRule, rule.id)
    assert fetched is not None
    assert fetched.popup_buttons == buttons
    assert fetched.popup_buttons[0]["action"] == "upgrade"
    assert fetched.popup_buttons[1]["label_i18n"]["en"] == "Later"


def test_assign_and_read_back_allowed_hosts_roundtrip(db: Session, app_row: CpApp):
    hosts = ["cdn.example.com", "fallback.example.com"]
    app_row.allowed_upgrade_hosts = hosts
    db.flush()
    db.expire(app_row)
    fetched = db.get(CpApp, app_row.id)
    assert fetched is not None
    assert fetched.allowed_upgrade_hosts == hosts
