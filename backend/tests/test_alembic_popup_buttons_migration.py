"""M1.T2：alembic 迁移 add popup_buttons + allowed_upgrade_hosts。

upgrade → 验证两列存在；downgrade → 验证两列消失。
baseline 用 raw SQL 建出迁移前的 cp_apps / cp_upgrade_rules（不含两个新列），
模拟 create_all 时代的旧 schema。
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

# 迁移前 baseline：缺 popup_buttons / allowed_upgrade_hosts，其它列对齐模型
BASELINE_CP_APPS_SQL = """
CREATE TABLE cp_apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_uuid VARCHAR(36) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    package_name VARCHAR(255) NOT NULL,
    owner_admin_user_id INTEGER NOT NULL,
    api_key_hash VARCHAR(255) NOT NULL,
    hmac_secret VARCHAR(128) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

BASELINE_CP_UPGRADE_RULES_SQL = """
CREATE TABLE cp_upgrade_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER NOT NULL,
    name VARCHAR(128) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    version_code_min INTEGER NOT NULL,
    version_code_max INTEGER NOT NULL,
    channel_codes JSON NOT NULL DEFAULT '[]',
    country_codes JSON NOT NULL DEFAULT '[]',
    device_id_hash_mod_min INTEGER NOT NULL DEFAULT 0,
    device_id_hash_mod_max INTEGER NOT NULL DEFAULT 99,
    target_version_code INTEGER NOT NULL,
    is_force BOOLEAN NOT NULL DEFAULT 0,
    can_skip BOOLEAN NOT NULL DEFAULT 1,
    popup_strategy VARCHAR(32) NOT NULL DEFAULT 'once_per_session',
    popup_interval_hours INTEGER,
    popup_title_i18n JSON NOT NULL DEFAULT '{}',
    popup_content_i18n JSON NOT NULL DEFAULT '{}',
    confirm_text_i18n JSON NOT NULL DEFAULT '{}',
    cancel_text_i18n JSON NOT NULL DEFAULT '{}',
    priority INTEGER NOT NULL DEFAULT 10,
    effective_from DATETIME,
    effective_to DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER NOT NULL
)
"""


@pytest.fixture
def tmp_db_url() -> Iterator[str]:
    fd, path = tempfile.mkstemp(suffix=".db", prefix="alembic-popup-buttons-")
    os.close(fd)
    try:
        yield f"sqlite:///{path}"
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def _build_baseline(db_url: str) -> None:
    eng = sa.create_engine(db_url)
    with eng.begin() as conn:
        conn.exec_driver_sql(BASELINE_CP_APPS_SQL)
        conn.exec_driver_sql(BASELINE_CP_UPGRADE_RULES_SQL)
    eng.dispose()


def _make_alembic_config(db_url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _column_names(db_url: str, table: str) -> set[str]:
    eng = sa.create_engine(db_url)
    try:
        inspector = sa.inspect(eng)
        return {c["name"] for c in inspector.get_columns(table)}
    finally:
        eng.dispose()


def test_migration_upgrade_downgrade_smoke(tmp_db_url: str, monkeypatch: pytest.MonkeyPatch):
    # env.py 启动时从 settings.database_url 读 URL；用 monkeypatch 把临时库注进去
    # 这样即便 set_main_option 之外的代码路径，env.py 也能正确连。
    monkeypatch.setenv("DATABASE_URL", tmp_db_url)
    from app.core.config import settings

    monkeypatch.setattr(settings, "database_url", tmp_db_url, raising=False)

    _build_baseline(tmp_db_url)

    pre = _column_names(tmp_db_url, "cp_upgrade_rules")
    assert "popup_buttons" not in pre
    pre_apps = _column_names(tmp_db_url, "cp_apps")
    assert "allowed_upgrade_hosts" not in pre_apps

    cfg = _make_alembic_config(tmp_db_url)
    command.upgrade(cfg, "channel_pack@head")

    after_up_rules = _column_names(tmp_db_url, "cp_upgrade_rules")
    after_up_apps = _column_names(tmp_db_url, "cp_apps")
    assert "popup_buttons" in after_up_rules, after_up_rules
    assert "allowed_upgrade_hosts" in after_up_apps, after_up_apps

    command.downgrade(cfg, "channel_pack@base")

    after_down_rules = _column_names(tmp_db_url, "cp_upgrade_rules")
    after_down_apps = _column_names(tmp_db_url, "cp_apps")
    assert "popup_buttons" not in after_down_rules, after_down_rules
    assert "allowed_upgrade_hosts" not in after_down_apps, after_down_apps
