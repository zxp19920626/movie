"""测试夹具：每个测试一个独立的内存 SQLite 库 + 事务回滚保证彻底隔离。"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# 触发模型注册到 Base.metadata
import app.modules.admin.models  # noqa: F401
import app.modules.channel_pack.models  # noqa: F401
import app.modules.user.models  # noqa: F401
from app.core.database import Base


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db(engine) -> Generator[Session, None, None]:
    """每个测试新事务，结束 rollback；表结构 session 级共享，数据用例级隔离。"""
    connection = engine.connect()
    trans = connection.begin()
    SessionLocal = sessionmaker(bind=connection, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        if trans.is_active:
            trans.rollback()
        connection.close()


@pytest.fixture
def admin_id(db: Session) -> int:
    """单测里塞一个 super_admin 角色 + admin 用户，返回 admin.id。"""
    from app.modules.admin.models import AdminRole, AdminUser

    role = AdminRole(
        code=f"super_{datetime.now(UTC).timestamp()}",
        name="super",
        is_super_admin=True,
        is_builtin=True,
        permissions=[],
    )
    db.add(role)
    db.flush()
    a = AdminUser(
        email=f"a{datetime.now(UTC).timestamp()}@x.com",
        password_hash="x",
        status="active",
        role_id=role.id,
    )
    db.add(a)
    db.flush()
    return a.id
