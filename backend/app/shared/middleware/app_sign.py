"""App SDK 包签名校验（P5.4）— Depends 形式挂在敏感公开端点上。

目的：阻止用 curl / Postman 等非 App 客户端直接打 App 端口（防被白嫖 VOD/CDN 流量）。
强度：reverse-engineerable，但抬高门槛。真要硬防需要 SafetyNet / Play Integrity（成本高）。

请求头要求：
- X-App-Ts: unix 秒（服务端 ±settings.app_sign_skew_sec 内有效）
- X-App-Sig: hex(hmac_sha256(secret, f"{ts}|{user_agent}"))

未配 APP_SIGN_SECRET 时 dev 模式直接放行（log warning）。
secret 真要在 App 内安全存储 + obfuscate；至少不进 git，由 CI 注入。
"""

from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import HTTPException, Request

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("app_sign")


def verify_app_sign(request: Request) -> None:
    """FastAPI Depends 兼容；不做就不抛，做就强制。"""
    if not settings.app_sign_secret:
        # dev：偶尔记一下，避免上线漏配
        log.debug("app_sign.skipped_dev_mode")
        return

    ts_header = request.headers.get("x-app-ts")
    sig_header = request.headers.get("x-app-sig")
    if not ts_header or not sig_header:
        raise HTTPException(401, "missing X-App-Ts / X-App-Sig")
    try:
        ts = int(ts_header)
    except ValueError as e:
        raise HTTPException(400, "X-App-Ts not int") from e
    if abs(int(time.time()) - ts) > settings.app_sign_skew_sec:
        raise HTTPException(401, "X-App-Ts expired")

    ua = request.headers.get("user-agent", "")
    canonical = f"{ts}|{ua}"
    expected = hmac.new(
        settings.app_sign_secret.encode(), canonical.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, sig_header):
        raise HTTPException(401, "X-App-Sig mismatch")
