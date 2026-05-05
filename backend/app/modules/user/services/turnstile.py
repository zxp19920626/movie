"""Cloudflare Turnstile 服务端校验

Dev 模式：TURNSTILE_SECRET 为空时 → 接受任何 token（mock）
生产模式：调 Cloudflare verify endpoint
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(token: str, remote_ip: str | None = None) -> bool:
    """返回 True/False；任何 server error 都视为失败。"""
    if not settings.turnstile_secret:
        # Dev mode: 接受任何 token
        logger.warning("TURNSTILE_SECRET 未设置，dev 模式接受所有 token: %s", token[:20])
        return bool(token)
    if not token:
        return False
    data = {"secret": settings.turnstile_secret, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(TURNSTILE_VERIFY_URL, data=data)
            return bool(r.json().get("success"))
    except Exception as e:
        logger.error("Turnstile verify error: %s", e)
        return False
