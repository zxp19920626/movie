"""M1.T9：play_store_toggle_guard 单测（C1 兜底，回溯扫存量规则）。

覆盖：
- 规则 buttons=[] → 无违规
- apply-to-all 规则 + inapp_apk → 命中 C2
- 按钮 url 非 https → 违规
- host 不在白名单 → 违规
- 别的 app 的规则不被扫
- rule.channel_codes 指定其他 code 而 candidate_channel.code 不在内 → 跳过
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.modules.channel_pack.models import CpApp, CpChannel, CpUpgradeRule
from app.modules.channel_pack.services.play_store_toggle_guard import (
    rescan_rules_for_play_store_violations,
)


def _mk_app(db: Session, admin_id: int, *, allowed_hosts: list[str]) -> CpApp:
    app = CpApp(
        tenant_uuid=f"t-{datetime.now(UTC).timestamp()}-{id(allowed_hosts)}",
        name="A",
        package_name="com.a.b",
        owner_admin_user_id=admin_id,
        api_key_hash="x",
        hmac_secret="x",
        status="active",
        allowed_upgrade_hosts=allowed_hosts,
    )
    db.add(app)
    db.flush()
    return app


def _mk_channel(
    db: Session,
    app_id: int,
    *,
    code: str,
    is_play_store: bool,
) -> CpChannel:
    ch = CpChannel(
        app_id=app_id,
        code=code,
        name=code.upper(),
        is_play_store=is_play_store,
        signing_strategy="play_signed" if is_play_store else "walle",
        enabled=True,
        priority=10,
    )
    db.add(ch)
    db.flush()
    return ch


def _mk_rule(
    db: Session,
    app_id: int,
    admin_id: int,
    *,
    name: str = "r",
    channel_codes: list[str] | None = None,
    popup_buttons: list[dict] | None = None,
) -> CpUpgradeRule:
    rule = CpUpgradeRule(
        app_id=app_id,
        name=name,
        enabled=True,
        version_code_min=1,
        version_code_max=99,
        channel_codes=channel_codes if channel_codes is not None else [],
        country_codes=[],
        target_version_code=100,
        popup_buttons=popup_buttons if popup_buttons is not None else [],
        created_by=admin_id,
    )
    db.add(rule)
    db.flush()
    return rule


@pytest.fixture
def candidate_play_channel(db: Session, admin_id: int) -> tuple[CpApp, CpChannel]:
    """返回一个 app + 一个 code='gp' 即将 toggle 到 is_play_store=true 的渠道。"""
    app = _mk_app(db, admin_id, allowed_hosts=["cdn.example.com"])
    # 注意：此 channel 在 DB 里目前是 is_play_store=False（业务上即将切真）；
    # 但我们传给 guard 时构造一个 in-memory 的 candidate 拷贝（is_play_store=True）
    return app, _mk_channel(db, app.id, code="gp", is_play_store=False)


def _candidate(code: str) -> CpChannel:
    """构造一个 in-memory candidate channel（is_play_store=True，未入库）。"""
    return CpChannel(
        app_id=0,  # 不写库
        code=code,
        name=code.upper(),
        is_play_store=True,
        signing_strategy="play_signed",
        enabled=True,
        priority=10,
    )


def test_rescan_clean_returns_empty(db: Session, admin_id: int) -> None:
    """规则 popup_buttons=[] → 空违规列表。"""
    app = _mk_app(db, admin_id, allowed_hosts=["cdn.example.com"])
    _mk_rule(db, app.id, admin_id, name="empty-rule", popup_buttons=[])
    db.flush()

    violations = rescan_rules_for_play_store_violations(db, app.id, _candidate("gp"))
    assert violations == []


def test_rescan_finds_inapp_apk_violation(db: Session, admin_id: int) -> None:
    """apply-to-all 规则（channel_codes=[]） + inapp_apk → 命中 C2。"""
    app = _mk_app(db, admin_id, allowed_hosts=["cdn.example.com"])
    rule = _mk_rule(
        db,
        app.id,
        admin_id,
        name="inapp-apk-rule",
        channel_codes=[],
        popup_buttons=[
            {
                "id": "install",
                "type": "inapp_apk",
                "text_i18n": {"en": "Install"},
                "url_i18n": {"en": "https://cdn.example.com/a.apk"},
            }
        ],
    )
    db.flush()

    violations = rescan_rules_for_play_store_violations(db, app.id, _candidate("gp"))
    assert len(violations) == 1
    assert violations[0].rule_id == rule.id
    assert violations[0].rule_name == "inapp-apk-rule"
    assert "play_store_channel_rejects_inapp_apk" in violations[0].reason


def test_rescan_finds_non_https_violation(db: Session, admin_id: int) -> None:
    """按钮 url='http://' → 违规。"""
    app = _mk_app(db, admin_id, allowed_hosts=["cdn.example.com"])
    rule = _mk_rule(
        db,
        app.id,
        admin_id,
        name="http-rule",
        channel_codes=[],
        popup_buttons=[
            {
                "id": "b1",
                "type": "browser",
                "text_i18n": {"en": "Open"},
                "url_i18n": {"en": "http://cdn.example.com/x"},
            }
        ],
    )
    db.flush()

    violations = rescan_rules_for_play_store_violations(db, app.id, _candidate("gp"))
    assert len(violations) == 1
    assert violations[0].rule_id == rule.id
    assert "https_only" in violations[0].reason


def test_rescan_finds_host_not_whitelisted(db: Session, admin_id: int) -> None:
    """host 不在 app.allowed_upgrade_hosts → 违规。"""
    app = _mk_app(db, admin_id, allowed_hosts=["ok.com"])
    rule = _mk_rule(
        db,
        app.id,
        admin_id,
        name="evil-host-rule",
        channel_codes=[],
        popup_buttons=[
            {
                "id": "b1",
                "type": "browser",
                "text_i18n": {"en": "Open"},
                "url_i18n": {"en": "https://evil.com/x"},
            }
        ],
    )
    db.flush()

    violations = rescan_rules_for_play_store_violations(db, app.id, _candidate("gp"))
    assert len(violations) == 1
    assert violations[0].rule_id == rule.id
    assert "host_not_in_whitelist" in violations[0].reason
    assert "evil.com" in violations[0].reason


def test_rescan_only_scans_target_app(db: Session, admin_id: int) -> None:
    """别的 app 的规则不被扫。"""
    target = _mk_app(db, admin_id, allowed_hosts=["cdn.example.com"])
    other = _mk_app(db, admin_id, allowed_hosts=["cdn.example.com"])
    # target app：clean
    _mk_rule(db, target.id, admin_id, name="target-clean", popup_buttons=[])
    # other app：本应违规，但不该被扫
    _mk_rule(
        db,
        other.id,
        admin_id,
        name="other-bad",
        channel_codes=[],
        popup_buttons=[
            {
                "id": "b",
                "type": "inapp_apk",
                "text_i18n": {"en": "x"},
                "url_i18n": {"en": "https://cdn.example.com/a.apk"},
            }
        ],
    )
    db.flush()

    violations = rescan_rules_for_play_store_violations(db, target.id, _candidate("gp"))
    assert violations == []


def test_rescan_skips_rules_not_applying_to_candidate_channel(
    db: Session, admin_id: int
) -> None:
    """rule.channel_codes 指定其他 code，candidate_channel.code 不在内 → 跳过。"""
    app = _mk_app(db, admin_id, allowed_hosts=["cdn.example.com"])
    # 这条规则本身有 inapp_apk 违规，但只对 direct 渠道生效，所以扫 gp 时跳过
    _mk_rule(
        db,
        app.id,
        admin_id,
        name="direct-only-rule",
        channel_codes=["direct"],
        popup_buttons=[
            {
                "id": "install",
                "type": "inapp_apk",
                "text_i18n": {"en": "Install"},
                "url_i18n": {"en": "https://cdn.example.com/a.apk"},
            }
        ],
    )
    db.flush()

    violations = rescan_rules_for_play_store_violations(db, app.id, _candidate("gp"))
    assert violations == []


def test_rescan_multiple_violations_collected(db: Session, admin_id: int) -> None:
    """多条违规规则全部收集（确保不是 short-circuit）。"""
    app = _mk_app(db, admin_id, allowed_hosts=["ok.com"])
    r1 = _mk_rule(
        db,
        app.id,
        admin_id,
        name="r1-inapp",
        channel_codes=[],
        popup_buttons=[
            {
                "id": "b",
                "type": "inapp_apk",
                "text_i18n": {"en": "x"},
                "url_i18n": {"en": "https://ok.com/a.apk"},
            }
        ],
    )
    r2 = _mk_rule(
        db,
        app.id,
        admin_id,
        name="r2-host",
        channel_codes=["gp"],
        popup_buttons=[
            {
                "id": "b",
                "type": "browser",
                "text_i18n": {"en": "x"},
                "url_i18n": {"en": "https://evil.com/x"},
            }
        ],
    )
    db.flush()

    violations = rescan_rules_for_play_store_violations(db, app.id, _candidate("gp"))
    ids = {v.rule_id for v in violations}
    assert ids == {r1.id, r2.id}
