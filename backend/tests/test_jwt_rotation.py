"""红线 — refresh token 旋转 + 黑名单端到端测试。

被测：
- POST /api/v1/auth/refresh：旧 refresh → 新 access + 新 refresh，旧 jti 入黑名单
- 第二次用同一 old refresh → 401（黑名单 / DB revoked 都能拦）
- access_token / refresh_token 的 exp 字段对齐 settings（默认 15min / 30 天）

注意：access/refresh token 都是 JWT，exp 是 unix 秒；我们解码后只对 (exp - now) 做粗粒度断言。
"""

from __future__ import annotations

import uuid as uuidlib
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1 import api_v1
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    decode_token,
    make_user_access_token,
    make_user_refresh_token,
    new_jti,
)
from app.modules.user.models import RefreshToken, User
from app.modules.user.services import refresh_blacklist


@pytest.fixture(autouse=True)
def _clear_blacklist():
    """每用例从空黑名单起。"""
    refresh_blacklist._default_blacklist._store.clear()
    yield
    refresh_blacklist._default_blacklist._store.clear()


@pytest.fixture
def client(db: Session) -> TestClient:
    test_app = FastAPI()
    test_app.include_router(api_v1)

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    test_app.dependency_overrides[get_db] = _override_get_db
    return TestClient(test_app)


@pytest.fixture
def user_with_refresh(db: Session) -> tuple[User, RefreshToken, str]:
    """造一个 active user + 一个未撤销 refresh token；返回 (user, rt 行, refresh_token JWT 字符串)。"""
    user = User(
        uuid=str(uuidlib.uuid4()),
        email=f"jwt-rot-{datetime.now(UTC).timestamp()}@x.com",
        password_hash="x",
        display_name="jwt-test",
        status="active",
    )
    db.add(user)
    db.flush()
    db.refresh(user)

    jti = new_jti()
    rt = RefreshToken(
        jti=jti,
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(days=settings.user_refresh_token_days),
        revoked=False,
    )
    db.add(rt)
    db.flush()
    db.refresh(rt)
    db.commit()

    token = make_user_refresh_token(user.id, jti)
    return user, rt, token


# ---------------- 旋转成功路径 ----------------


def test_refresh_rotation_returns_new_token_pair(
    db: Session, client: TestClient, user_with_refresh: tuple
):
    user, rt, old_token = user_with_refresh

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_token})
    assert r.status_code == 200, r.text

    body = r.json()
    assert "access_token" in body
    assert "refresh_token" in body
    # 新 refresh != 老 refresh
    assert body["refresh_token"] != old_token

    # 新 access 是 user scope
    access_claims = decode_token(body["access_token"])
    assert access_claims["scope"] == "user"
    assert int(access_claims["sub"]) == user.id

    # 新 refresh 是 user_refresh scope，且 jti 与旧的不同
    new_refresh_claims = decode_token(body["refresh_token"])
    assert new_refresh_claims["scope"] == "user_refresh"
    assert new_refresh_claims["jti"] != rt.jti


def test_old_refresh_marked_revoked_in_db_after_rotation(
    db: Session, client: TestClient, user_with_refresh: tuple
):
    """旋转后旧 jti 的 DB 行：revoked=True, revoked_reason='rotated'。"""
    user, rt, old_token = user_with_refresh
    old_jti = rt.jti

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_token})
    assert r.status_code == 200, r.text

    db.expire_all()
    rt_after = db.query(RefreshToken).filter(RefreshToken.jti == old_jti).one()
    assert rt_after.revoked is True
    assert rt_after.revoked_reason == "rotated"


def test_old_refresh_in_blacklist_after_rotation(
    client: TestClient, user_with_refresh: tuple
):
    """旋转后旧 jti 已加进进程内黑名单。"""
    _, rt, old_token = user_with_refresh
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_token})
    assert r.status_code == 200, r.text
    assert refresh_blacklist.is_blacklisted(rt.jti) is True


# ---------------- 反复用同 token：必须拒 ----------------


def test_second_use_of_old_refresh_rejected(client: TestClient, user_with_refresh: tuple):
    """同一个 old refresh 用第二次 → 401（黑名单）。"""
    _, _rt, old_token = user_with_refresh

    r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_token})
    assert r1.status_code == 200, r1.text

    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_token})
    assert r2.status_code == 401, r2.text
    assert "revoked" in r2.json()["detail"].lower()


# ---------------- 各种非法 refresh ----------------


def test_refresh_invalid_jwt_string(client: TestClient):
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-jwt"})
    assert r.status_code == 401
    assert "invalid refresh token" in r.json()["detail"]


def test_refresh_wrong_scope_rejected(client: TestClient):
    """用 access token（scope=user）当 refresh 用 → 401 wrong scope。"""
    access = make_user_access_token(user_id=1)
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": access})
    assert r.status_code == 401
    assert "wrong scope" in r.json()["detail"]


def test_refresh_jti_not_in_db_rejected(client: TestClient, db: Session):
    """JWT 合法但 jti 不在 u_refresh_tokens（伪造或 DB 已删）→ 401。"""
    # 直接造个孤儿 jti 的 token
    fake = make_user_refresh_token(user_id=999999, jti=new_jti())
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": fake})
    assert r.status_code == 401
    # 触发的是 "not found"（user_id=999999 在 DB 没记录）
    assert r.json()["detail"] in ("refresh token not found",)


def test_refresh_revoked_in_db_rejected(
    db: Session, client: TestClient, user_with_refresh: tuple
):
    """DB 里 revoked=true（如登出标的）→ 401。"""
    _, rt, old_token = user_with_refresh
    rt.revoked = True
    db.commit()

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_token})
    assert r.status_code == 401
    assert "expired/revoked" in r.json()["detail"]


def test_refresh_user_suspended_rejected(
    db: Session, client: TestClient, user_with_refresh: tuple
):
    """user.status != active → 401。"""
    user, _, old_token = user_with_refresh
    user.status = "suspended"
    db.commit()

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_token})
    assert r.status_code == 401
    assert "user not active" in r.json()["detail"]


# ---------------- TTL 验证 ----------------


def test_access_token_expires_in_about_15_minutes():
    """settings.user_access_token_minutes 默认 15min；access token exp ≈ now + 15min。"""
    tok = make_user_access_token(user_id=42)
    claims = pyjwt.decode(tok, options={"verify_signature": False})
    now = int(datetime.now(UTC).timestamp())
    delta = claims["exp"] - now
    expected = settings.user_access_token_minutes * 60
    # 允许 ±10s 时钟漂移
    assert abs(delta - expected) <= 10, f"access token exp δ={delta}, expected={expected}"
    assert claims["scope"] == "user"


def test_refresh_token_expires_in_about_30_days():
    """settings.user_refresh_token_days 默认 30 天；refresh token exp ≈ now + 30 天。"""
    tok = make_user_refresh_token(user_id=42, jti=new_jti())
    claims = pyjwt.decode(tok, options={"verify_signature": False})
    now = int(datetime.now(UTC).timestamp())
    delta = claims["exp"] - now
    expected = settings.user_refresh_token_days * 86400
    assert abs(delta - expected) <= 10, f"refresh token exp δ={delta}, expected={expected}"
    assert claims["scope"] == "user_refresh"


def test_blacklist_evicts_expired_entries(client: TestClient):
    """黑名单内 expires_at 已过期 → is_blacklisted 返回 False（防永久占内存）。"""
    refresh_blacklist.add("evict-jti", expires_at_unix=0.0)  # 永远过期
    assert refresh_blacklist.is_blacklisted("evict-jti") is False
