"""C1 兜底：is_play_store false→true 切换时回溯扫描存量规则。"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CpApp, CpChannel, CpUpgradeRule
from ..schemas import PopupButton
from .upgrade_rule_validator import UpgradeRuleValidationError, validate_buttons_for_app


@dataclass
class ViolationItem:
    rule_id: int
    rule_name: str
    reason: str


def rescan_rules_for_play_store_violations(
    session: Session,
    app_id: int,
    candidate_channel: CpChannel,
) -> list[ViolationItem]:
    """
    扫存量规则 → 哪些可能命中 candidate_channel（apply-to-all OR channel_codes 含其 code）
    → 跑 validate_buttons_for_app(app, candidate_channel, buttons) → 收集违规
    """
    app = session.get(CpApp, app_id)
    rules = session.scalars(
        select(CpUpgradeRule).where(CpUpgradeRule.app_id == app_id)
    ).all()
    violations: list[ViolationItem] = []
    for rule in rules:
        applies_to = (not rule.channel_codes) or (
            candidate_channel.code in rule.channel_codes
        )
        if not applies_to:
            continue
        buttons = [PopupButton.model_validate(b) for b in (rule.popup_buttons or [])]
        try:
            validate_buttons_for_app(app, candidate_channel, buttons)
        except UpgradeRuleValidationError as e:
            violations.append(
                ViolationItem(rule_id=rule.id, rule_name=rule.name, reason=str(e))
            )
    return violations
