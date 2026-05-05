"""user 模块 — 认证路由 /api/v1/auth/..."""

import logging
import uuid as uuidlib
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user_refresh_payload
from app.core.security import (
    hash_password,
    make_user_access_token,
    make_user_refresh_token,
    new_jti,
    verify_password,
)
from app.modules.user.models import RefreshToken, User, UserOauth
from app.modules.user.schemas import (
    EmailLoginRequest,
    EmailRegisterRequest,
    GoogleLoginRequest,
    PhoneSendOtpRequest,
    PhoneVerifyRequest,
    RefreshRequest,
    TokensOut,
    UserOut,
)
from app.modules.user.services import otp_service, rate_limit, refresh_blacklist
from app.modules.user.services.google_auth import verify_google_id_token
from app.modules.user.services.turnstile import verify_turnstile

logger = logging.getLogger(__name__)
router = APIRouter()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _new_user(db: Session, **kwargs) -> User:
    user = User(uuid=str(uuidlib.uuid4()), **kwargs)
    db.add(user)
    db.flush()
    return user


def _issue_tokens(db: Session, user: User) -> TokensOut:
    """签发 access + refresh，refresh 入 u_refresh_tokens"""
    user.last_active_at = datetime.now(UTC)
    jti = new_jti()
    rt = RefreshToken(
        jti=jti,
        user_id=user.id,
        expires_at=datetime.now(UTC) + timedelta(days=settings.user_refresh_token_days),
    )
    db.add(rt)
    db.commit()
    db.refresh(user)
    return TokensOut(
        access_token=make_user_access_token(user.id, user.app_id),
        refresh_token=make_user_refresh_token(user.id, jti),
        user=UserOut(**user.to_public()),
    )


# ===== Email =====


@router.post("/email/register", response_model=TokensOut, status_code=201)
def email_register(payload: EmailRegisterRequest, db: Session = Depends(get_db)) -> TokensOut:
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "email already registered")
    user = _new_user(
        db,
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name or email.split("@")[0],
        country=payload.country,
        app_id=payload.app_id,
    )
    db.add(UserOauth(user_id=user.id, provider="email", provider_uid=email))
    return _issue_tokens(db, user)


@router.post("/email/login", response_model=TokensOut)
def email_login(payload: EmailLoginRequest, db: Session = Depends(get_db)) -> TokensOut:
    email = payload.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash or ""):
        raise HTTPException(401, "邮箱或密码错误")
    if user.status != "active":
        raise HTTPException(401, "账号已禁用")
    return _issue_tokens(db, user)


# ===== Google =====


@router.post("/google", response_model=TokensOut)
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)) -> TokensOut:
    try:
        claims = verify_google_id_token(payload.id_token)
    except ValueError as e:
        raise HTTPException(401, str(e))
    sub = str(claims.get("sub", ""))
    email = (claims.get("email") or "").lower() or None
    if not sub:
        raise HTTPException(401, "no sub in id_token")

    # 已绑过？
    oauth = db.scalar(
        select(UserOauth).where(UserOauth.provider == "google", UserOauth.provider_uid == sub)
    )
    if oauth:
        user = db.get(User, oauth.user_id)
    else:
        # 没绑过：用 email 找现有用户；都没有就建新
        user = None
        if email:
            user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = _new_user(
                db,
                email=email,
                display_name=claims.get("name") or (email or sub).split("@")[0],
                avatar_url=claims.get("picture"),
                country=payload.country,
                app_id=payload.app_id,
            )
        db.add(
            UserOauth(
                user_id=user.id, provider="google", provider_uid=sub, raw_profile=claims
            )
        )

    if user.status != "active":
        raise HTTPException(401, "账号已禁用")
    return _issue_tokens(db, user)


# ===== Phone OTP =====


@router.post("/phone/send-otp")
async def phone_send_otp(
    payload: PhoneSendOtpRequest, request: Request, db: Session = Depends(get_db)
) -> dict[str, str]:
    if not otp_service.is_phone_country_allowed(payload.phone):
        raise HTTPException(400, "phone country code not in allowed list")

    # Turnstile（dev mode 自动通过）
    ok = await verify_turnstile(payload.turnstile_token or "", _client_ip(request))
    if not ok:
        raise HTTPException(401, "turnstile failed")

    # 三层频控
    rl_ok, layer = rate_limit.hit_all(payload.phone, _client_ip(request), payload.device_id)
    if not rl_ok:
        raise HTTPException(429, f"rate limited at layer: {layer}")

    rec = otp_service.issue_otp(db, payload.phone, _client_ip(request), payload.device_id)
    return {"status": "sent", "expires_at": rec.expires_at.isoformat()}


@router.post("/phone/verify", response_model=TokensOut)
def phone_verify(payload: PhoneVerifyRequest, db: Session = Depends(get_db)) -> TokensOut:
    if not otp_service.is_phone_country_allowed(payload.phone):
        raise HTTPException(400, "phone country code not in allowed list")
    ok, reason = otp_service.verify_otp(db, payload.phone, payload.code)
    if not ok:
        raise HTTPException(401, reason)

    # 拿到/建用户
    user = db.scalar(select(User).where(User.phone == payload.phone))
    if user is None:
        # 拆出国码
        country_code = None
        for prefix in settings.allowed_phone_prefixes:
            if payload.phone.startswith(prefix):
                country_code = prefix
                break
        user = _new_user(
            db,
            phone=payload.phone,
            country_code=country_code,
            display_name=payload.display_name or payload.phone,
            country=payload.country,
            app_id=payload.app_id,
        )
        db.add(UserOauth(user_id=user.id, provider="phone", provider_uid=payload.phone))

    if user.status != "active":
        raise HTTPException(401, "账号已禁用")
    return _issue_tokens(db, user)


# ===== Refresh =====


@router.post("/refresh", response_model=TokensOut)
def refresh(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
) -> TokensOut:
    # 这里不用 Depends 取 token，因为前端可能在 body 传（也支持 header）
    from app.core.security import decode_token
    try:
        claims = decode_token(payload.refresh_token)
    except Exception as e:
        raise HTTPException(401, f"invalid refresh token: {e}")
    if claims.get("scope") != "user_refresh":
        raise HTTPException(401, "wrong scope")
    jti = claims.get("jti")
    user_id = int(claims.get("sub"))
    if not jti or not user_id:
        raise HTTPException(401, "malformed token")
    if refresh_blacklist.is_blacklisted(jti):
        raise HTTPException(401, "refresh token revoked")

    # DB 校验
    rt = db.scalar(select(RefreshToken).where(RefreshToken.jti == jti))
    if rt is None:
        raise HTTPException(401, "refresh token not found")
    # SQLite 返回 naive datetime；统一按 UTC 处理
    rt_exp = rt.expires_at
    if rt_exp.tzinfo is None:
        rt_exp = rt_exp.replace(tzinfo=UTC)
    if rt.revoked or rt_exp < datetime.now(UTC):
        raise HTTPException(401, "refresh token expired/revoked")

    user = db.get(User, user_id)
    if user is None or user.status != "active":
        raise HTTPException(401, "user not active")

    # 旋转：标旧 jti revoked + 入黑名单 + 签新 token
    rt.revoked = True
    rt.revoked_reason = "rotated"
    refresh_blacklist.add(jti, rt_exp.timestamp())
    db.commit()
    return _issue_tokens(db, user)


# 让 deps unused 不爆 ruff
_ = get_current_user_refresh_payload
