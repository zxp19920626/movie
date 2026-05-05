"""手机 OTP 服务

MVP：rand 6 位数字 + bcrypt 存 DB + 写 stdout/log（mock SMS）
生产：换 Twilio Verify / 阿里云国际 SMS（接口不变，换 send_sms 实现）
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

import bcrypt

from app.core.config import settings
from app.modules.user.models import OtpCode

logger = logging.getLogger(__name__)


def generate_code() -> str:
    """6 位随机数字（不以 0 开头）"""
    n = secrets.randbelow(900_000) + 100_000
    return str(n)


def _hash(code: str) -> str:
    return bcrypt.hashpw(code.encode(), bcrypt.gensalt(rounds=4)).decode()


def _verify(code: str, code_hash: str) -> bool:
    try:
        return bcrypt.checkpw(code.encode(), code_hash.encode())
    except Exception:
        return False


def is_phone_country_allowed(phone: str) -> bool:
    """phone 必须 +<countrycode><number>，且 country code 在白名单"""
    if not phone.startswith("+"):
        return False
    for prefix in settings.allowed_phone_prefixes:
        if phone.startswith(prefix):
            return True
    return False


def send_otp_mock(phone: str, code: str) -> None:
    """MVP 不接 SMS；把验证码打到 log（dev 用）"""
    logger.warning("[MOCK SMS] phone=%s code=%s (TTL=%dmin)", phone, code, settings.otp_ttl_minutes)


def _aware(dt):
    """SQLite naive datetime → UTC aware"""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def issue_otp(
    db: Session, phone: str, ip: str | None = None, device_id: str | None = None
) -> OtpCode:
    """签发新 OTP；同号已有的 active OTP 标 verified=true（作废）"""
    now = datetime.now(UTC)
    # 把同号 active 但未验的 OTP 标作废（SQLite 比较用 naive）
    stmt = select(OtpCode).where(
        OtpCode.phone == phone,
        OtpCode.verified.is_(False),
    )
    for old in db.scalars(stmt).all():
        if _aware(old.expires_at) > now:
            old.verified = True  # 视为消费掉
    code = generate_code()
    rec = OtpCode(
        phone=phone,
        code_hash=_hash(code),
        ip=ip,
        device_id=device_id,
        expires_at=now + timedelta(minutes=settings.otp_ttl_minutes),
        attempts=0,
        verified=False,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    send_otp_mock(phone, code)
    return rec


def verify_otp(db: Session, phone: str, code: str) -> tuple[bool, str]:
    """返回 (ok, reason)"""
    now = datetime.now(UTC)
    stmt = (
        select(OtpCode)
        .where(
            OtpCode.phone == phone,
            OtpCode.verified.is_(False),
        )
        .order_by(OtpCode.id.desc())
        .limit(1)
    )
    rec = db.scalars(stmt).one_or_none()
    if rec is None or _aware(rec.expires_at) <= now:
        return False, "no active otp; request a new code"

    if rec.attempts >= settings.otp_max_attempts:
        rec.verified = True  # 标作废
        db.commit()
        return False, "too many attempts; request a new code"

    rec.attempts += 1
    if not _verify(code, rec.code_hash):
        db.commit()
        return False, "wrong code"

    rec.verified = True
    db.commit()
    return True, "ok"
