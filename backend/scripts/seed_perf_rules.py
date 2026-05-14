"""为性能基线压测准备数据：1 个 CpApp + 5 channel + 多版本 + 1000 条 cp_upgrade_rules

用法：
    cd backend && uv run python scripts/seed_perf_rules.py

幂等：基于 package_name=com.perf.bench 检测已存在 → 不重复创建租户；
但每次会清空并重建 1000 条压测规则，确保压测前数据规模一致。

完成后打印：
    CP_TENANT_UUID=<uuid>
    CP_HMAC_SECRET=<secret>
"""

from __future__ import annotations

import base64
import random
import secrets
import sys
from pathlib import Path

# 让脚本能 import app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.modules.admin.models import AdminRole, AdminUser  # noqa: E402
from app.modules.channel_pack.models import (  # noqa: E402
    CpApkSigningJob,
    CpApp,
    CpAppVersion,
    CpChannel,
    CpUpgradeRule,
)

PACKAGE_NAME = "com.perf.bench"
APP_DISPLAY_NAME = "perf-bench-app"
RULE_COUNT = 1000
CHANNELS = [
    {"code": "direct", "name": "Direct", "is_play_store": False, "priority": 10},
    {"code": "xiaomi_intl", "name": "Xiaomi Intl", "is_play_store": False, "priority": 20},
    {"code": "huawei_intl", "name": "Huawei Intl", "is_play_store": False, "priority": 30},
    {"code": "samsung_galaxy", "name": "Samsung Galaxy", "is_play_store": False, "priority": 40},
    {"code": "gp", "name": "Google Play", "is_play_store": True, "priority": 50},
]
VERSION_CODES = [100, 110, 120, 150, 200]
TARGET_VERSION_CODE = 200  # 所有规则统一指向 200，确保有 1 个就绪的目标
COUNTRY_POOL = [
    "US", "JP", "ID", "MY", "VN", "TH", "BR", "MX", "EG", "NG",
    "IN", "PH", "TR", "AR", "PK", "BD", "CO", "DE", "FR", "ES",
]
NON_PLAY_CHANNEL_CODES = [c["code"] for c in CHANNELS if not c["is_play_store"]]


def get_or_create_admin(db) -> AdminUser:
    role = db.query(AdminRole).filter_by(code="super_admin").one_or_none()
    if role is None:
        role = AdminRole(
            code="super_admin",
            name="超级管理员",
            is_super_admin=True,
            is_builtin=True,
            permissions=[],
        )
        db.add(role)
        db.flush()
    admin = db.query(AdminUser).filter_by(email="perf-seed@local").one_or_none()
    if admin is None:
        admin = AdminUser(
            email="perf-seed@local",
            password_hash=hash_password("perf-seed-pwd"),
            display_name="Perf Seed",
            role_id=role.id,
            app_scope=[],
            status="active",
        )
        db.add(admin)
        db.flush()
    return admin


def get_or_create_app(db, admin: AdminUser) -> CpApp:
    app = db.query(CpApp).filter_by(package_name=PACKAGE_NAME).one_or_none()
    if app is not None:
        return app
    hmac_secret = base64.b64encode(secrets.token_bytes(32)).decode()
    app = CpApp(
        tenant_uuid=secrets.token_hex(16) + "-perf",
        name=APP_DISPLAY_NAME,
        package_name=PACKAGE_NAME,
        owner_admin_user_id=admin.id,
        api_key_hash=hash_password(secrets.token_hex(16)),
        hmac_secret=hmac_secret,
        status="active",
        allowed_upgrade_hosts=[],
    )
    db.add(app)
    db.flush()
    return app


def ensure_channels(db, app: CpApp) -> dict[str, CpChannel]:
    existing = {c.code: c for c in db.query(CpChannel).filter_by(app_id=app.id).all()}
    for spec in CHANNELS:
        if spec["code"] in existing:
            continue
        ch = CpChannel(
            app_id=app.id,
            code=spec["code"],
            name=spec["name"],
            is_play_store=spec["is_play_store"],
            signing_strategy="walle",
            enabled=True,
            priority=spec["priority"],
            oss_prefix=f"apks/{app.tenant_uuid}/",
        )
        db.add(ch)
        existing[spec["code"]] = ch
    db.flush()
    return existing


def ensure_versions(db, app: CpApp, admin: AdminUser) -> dict[int, CpAppVersion]:
    existing = {v.version_code: v for v in db.query(CpAppVersion).filter_by(app_id=app.id).all()}
    for vc in VERSION_CODES:
        if vc in existing:
            continue
        v = CpAppVersion(
            app_id=app.id,
            version_code=vc,
            version_name=f"1.{vc // 100}.{vc % 100}",
            master_apk_oss_key=f"apks/{app.tenant_uuid}/master/{vc}.apk",
            master_apk_sha256="0" * 64,
            master_apk_size=1024,
            min_supported_version_code=0,
            changelog_i18n={"en": f"version {vc}"},
            status="ready",
            uploaded_by=admin.id,
        )
        db.add(v)
        existing[vc] = v
    db.flush()
    return existing


def ensure_signing_jobs(db, app: CpApp) -> None:
    """非 Play 渠道 × TARGET_VERSION_CODE 都得有 status=success 的 job"""
    have = {
        (j.channel_code, j.version_code)
        for j in db.query(CpApkSigningJob).filter_by(app_id=app.id, version_code=TARGET_VERSION_CODE).all()
    }
    for code in NON_PLAY_CHANNEL_CODES:
        if (code, TARGET_VERSION_CODE) in have:
            continue
        job = CpApkSigningJob(
            app_id=app.id,
            version_code=TARGET_VERSION_CODE,
            channel_code=code,
            master_sha256="0" * 64,
            idempotency_key=f"perf-{app.tenant_uuid}-{TARGET_VERSION_CODE}-{code}",
            status="success",
            output_oss_key=f"apks/{app.tenant_uuid}/signed/{TARGET_VERSION_CODE}/{code}.apk",
            output_sha256="f" * 64,
            output_size=2048,
            attempts=1,
            cdn_warmup_status="success",
        )
        db.add(job)
    db.flush()


def reset_rules(db, app: CpApp, admin: AdminUser) -> None:
    db.query(CpUpgradeRule).filter_by(app_id=app.id).delete()
    db.flush()
    rng = random.Random(42)  # 可复现
    for i in range(RULE_COUNT):
        # 把 channel_codes 维度做出多样性：1/3 空（命中所有）、1/3 单渠道、1/3 双渠道
        r = rng.random()
        if r < 0.34:
            channel_codes: list[str] = []
        elif r < 0.67:
            channel_codes = [rng.choice(NON_PLAY_CHANNEL_CODES)]
        else:
            channel_codes = rng.sample(NON_PLAY_CHANNEL_CODES, 2)

        r2 = rng.random()
        if r2 < 0.34:
            country_codes: list[str] = []
        elif r2 < 0.67:
            country_codes = [rng.choice(COUNTRY_POOL)]
        else:
            country_codes = rng.sample(COUNTRY_POOL, 3)

        # 灰度区间：大部分覆盖全量 0-99，小部分窄区间制造未命中
        if rng.random() < 0.7:
            hmin, hmax = 0, 99
        else:
            hmin = rng.randint(0, 80)
            hmax = rng.randint(hmin, 99)

        rule = CpUpgradeRule(
            app_id=app.id,
            name=f"perf-rule-{i}",
            enabled=True,
            version_code_min=0,
            version_code_max=199,
            channel_codes=channel_codes,
            country_codes=country_codes,
            device_id_hash_mod_min=hmin,
            device_id_hash_mod_max=hmax,
            target_version_code=TARGET_VERSION_CODE,
            is_force=False,
            can_skip=True,
            popup_strategy="once_per_session",
            popup_interval_hours=None,
            popup_title_i18n={"en": "Upgrade", "zh": "升级"},
            popup_content_i18n={"en": "New version", "zh": "新版本"},
            confirm_text_i18n={"en": "Update"},
            cancel_text_i18n={"en": "Later"},
            popup_buttons=[],
            priority=rng.randint(1, 100),
            created_by=admin.id,
        )
        db.add(rule)
        if i % 200 == 0:
            db.flush()
    db.flush()


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        admin = get_or_create_admin(db)
        app = get_or_create_app(db, admin)
        ensure_channels(db, app)
        ensure_versions(db, app, admin)
        ensure_signing_jobs(db, app)
        reset_rules(db, app, admin)
        db.commit()

        rule_count = db.query(CpUpgradeRule).filter_by(app_id=app.id).count()
        ch_count = db.query(CpChannel).filter_by(app_id=app.id).count()
        v_count = db.query(CpAppVersion).filter_by(app_id=app.id).count()
        job_count = db.query(CpApkSigningJob).filter_by(app_id=app.id).count()
        print(f"[seed-perf] tenant_uuid={app.tenant_uuid}")
        print(f"[seed-perf] hmac_secret={app.hmac_secret}")
        print(f"[seed-perf] channels={ch_count} versions={v_count} signed_jobs={job_count} rules={rule_count}")
        print()
        print("export CP_TENANT_UUID=" + app.tenant_uuid)
        print("export CP_HMAC_SECRET='" + app.hmac_secret + "'")
    finally:
        db.close()


if __name__ == "__main__":
    main()
