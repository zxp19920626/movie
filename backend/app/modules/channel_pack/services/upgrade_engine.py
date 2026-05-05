"""升级规则匹配引擎（纯函数 + 显式 debug_steps）

输入：app_id（DB id，非 tenant_uuid）、用户当前 version_code、渠道、国家、device_id
输出：UpgradeMatch 对象（含命中规则 + 目标版本 + 已签 APK 信息），或 None

灰度算法：crc32(device_id) % 100
规则候选条件：app + enabled + 生效时间窗 + version 区间 + channel 集合 + country 集合 + hash_bucket 区间
排序：priority DESC, created_at DESC
遍历：跳过目标版本未 ready / 未签好 / 比当前还低 的规则；首条符合即返回
Play 渠道（is_play_store=true）：直接返回 None（后端硬拒，不查规则）
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from zlib import crc32

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.channel_pack.models import (
    CpApkSigningJob,
    CpAppVersion,
    CpChannel,
    CpUpgradeRule,
)


@dataclass
class UpgradeMatch:
    rule: CpUpgradeRule
    target_version: CpAppVersion
    signed_job: CpApkSigningJob


@dataclass
class UpgradeCheckResult:
    match: UpgradeMatch | None
    debug_steps: list[str] = field(default_factory=list)


def check_upgrade(
    db: Session,
    app_id: int,
    user_version_code: int,
    channel_code: str,
    country: str,
    device_id: str,
) -> UpgradeCheckResult:
    steps: list[str] = []

    # Play 渠道硬拒（双保险，编译期已隔离）
    channel = db.scalars(
        select(CpChannel).where(CpChannel.app_id == app_id, CpChannel.code == channel_code)
    ).one_or_none()
    if channel is None:
        steps.append(f"channel '{channel_code}' not found in app_id={app_id}")
        return UpgradeCheckResult(None, steps)
    if channel.is_play_store:
        steps.append(f"channel '{channel_code}' is_play_store=true → 后端硬拒")
        return UpgradeCheckResult(None, steps)
    if not channel.enabled:
        steps.append(f"channel '{channel_code}' disabled")
        return UpgradeCheckResult(None, steps)

    hash_bucket = crc32(device_id.encode()) % 100
    steps.append(f"device_id='{device_id}' → hash_bucket={hash_bucket}")
    now = datetime.now(UTC)

    # 查候选规则
    stmt = (
        select(CpUpgradeRule)
        .where(
            CpUpgradeRule.app_id == app_id,
            CpUpgradeRule.enabled.is_(True),
            CpUpgradeRule.version_code_min <= user_version_code,
            CpUpgradeRule.version_code_max >= user_version_code,
            CpUpgradeRule.device_id_hash_mod_min <= hash_bucket,
            CpUpgradeRule.device_id_hash_mod_max >= hash_bucket,
        )
        .order_by(CpUpgradeRule.priority.desc(), CpUpgradeRule.created_at.desc())
    )
    rules = list(db.scalars(stmt).all())
    steps.append(f"候选规则数（满足 version + hash_bucket）：{len(rules)}")

    for rule in rules:
        # 渠道集合
        if rule.channel_codes and channel_code not in rule.channel_codes:
            steps.append(f"rule#{rule.id}('{rule.name}') 跳过：channel 不在 {rule.channel_codes}")
            continue
        # 国家集合
        if rule.country_codes and country and country not in rule.country_codes:
            steps.append(f"rule#{rule.id}('{rule.name}') 跳过：country 不在 {rule.country_codes}")
            continue
        # 生效时间窗
        if rule.effective_from and now < rule.effective_from:
            steps.append(f"rule#{rule.id}('{rule.name}') 跳过：未到生效时间")
            continue
        if rule.effective_to and now > rule.effective_to:
            steps.append(f"rule#{rule.id}('{rule.name}') 跳过：超过生效时间")
            continue

        # 目标版本就绪
        target = db.scalars(
            select(CpAppVersion).where(
                CpAppVersion.app_id == app_id,
                CpAppVersion.version_code == rule.target_version_code,
            )
        ).one_or_none()
        if target is None:
            steps.append(
                f"rule#{rule.id} 跳过：target_version_code={rule.target_version_code} 不存在"
            )
            continue
        if target.status != "ready":
            steps.append(f"rule#{rule.id} 跳过：目标版本 status={target.status}")
            continue
        if target.version_code <= user_version_code:
            steps.append(f"rule#{rule.id} 跳过：不降级（target<={user_version_code}）")
            continue

        # 该渠道签名 success
        signed = db.scalars(
            select(CpApkSigningJob).where(
                CpApkSigningJob.app_id == app_id,
                CpApkSigningJob.version_code == target.version_code,
                CpApkSigningJob.channel_code == channel_code,
                CpApkSigningJob.status == "success",
            )
        ).one_or_none()
        if signed is None:
            steps.append(f"rule#{rule.id} 跳过：渠道 '{channel_code}' 未签好")
            continue

        steps.append(f"✓ 命中 rule#{rule.id}('{rule.name}') → 升级到 vc={target.version_code}")
        return UpgradeCheckResult(UpgradeMatch(rule, target, signed), steps)

    steps.append("无规则命中 → has_update=false")
    return UpgradeCheckResult(None, steps)
