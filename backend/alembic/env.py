"""alembic env.py — 多 head + 多模块汇总。

每个业务模块（channel_pack / user / content / admin）都把模型 import 进来，
让 Base.metadata 能感知所有表，autogenerate 才能生成完整 diff。
"""

from __future__ import annotations

# === 让 alembic 能 import app.* ===
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# 触发各模块模型加载到 Base.metadata
from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.modules.admin import models as _admin_models  # noqa: E402,F401
from app.modules.channel_pack import models as _cp_models  # noqa: E402,F401
from app.modules.user import models as _user_models  # noqa: E402,F401

# alembic Config 对象
config = context.config

# 从应用 settings 读 DB URL（避免在 alembic.ini 里写明文）
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
