"""Google id_token 验签

Dev 模式：GOOGLE_CLIENT_ID 为空时 → 接受任何 token，从 token 字符串构造 mock claims
生产模式：用 google-auth 验签（需 `uv add google-auth`）

返回 claims 字典：含 sub / email / name / picture / email_verified
"""

import base64
import json
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def verify_google_id_token(id_token: str) -> dict[str, Any]:
    """成功返回 claims；失败抛 ValueError"""
    if not settings.google_client_id:
        # Dev mode：接受任何 token
        logger.warning("GOOGLE_CLIENT_ID 未设置，dev 模式 mock 验签")
        return _mock_decode(id_token)

    # 生产模式：用 google-auth（如未装则 raise）
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token
    except ImportError as e:
        raise ValueError(
            "生产模式需要 google-auth：uv add google-auth；当前 ImportError: " + str(e)
        ) from e

    try:
        info = google_id_token.verify_oauth2_token(
            id_token, google_requests.Request(), settings.google_client_id
        )
        return info
    except Exception as e:
        raise ValueError(f"Google id_token verify failed: {e}") from e


def _mock_decode(id_token: str) -> dict[str, Any]:
    """从 mock token 提取 sub/email。

    支持三种格式：
    1. 真 JWT：解 payload 段不验签
    2. `sub@email`：用作 sub + email
    3. 任意字符串：当 sub，构造 email = `<token>@mock-google.local`
    """
    # 尝试 JWT 解码
    parts = id_token.split(".")
    if len(parts) >= 2:
        try:
            payload = parts[1]
            payload += "=" * (-len(payload) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload))
            if "sub" in claims:
                claims.setdefault("email", f"{claims['sub']}@mock-google.local")
                claims.setdefault("name", claims.get("email", "Mock User").split("@")[0])
                claims.setdefault("email_verified", True)
                return claims
        except Exception:
            pass

    # `sub@domain` 形式
    if "@" in id_token and "." in id_token.split("@")[-1]:
        sub = id_token.split("@")[0]
        return {
            "sub": sub,
            "email": id_token,
            "name": sub,
            "email_verified": True,
            "picture": None,
        }

    # 兜底：任何字符串
    sub = id_token[:64] or "mock"
    return {
        "sub": sub,
        "email": f"{sub}@mock-google.local",
        "name": sub,
        "email_verified": True,
        "picture": None,
    }
