"""HMAC-SHA256 签名校验（App SDK ↔ /api/v1/cp/upgrade/check）

签名规则：
  canonical = "&".join(sorted(query 参数排除 sig))，每个参数 url-decode 后用 k=v
  sig = base64(HMAC-SHA256(hmac_secret, canonical))

ts 必须在服务器当前时间 ±5min 内（防 replay）。
"""

import base64
import hashlib
import hmac
import time

CLOCK_SKEW_SECONDS = 300  # 5min


def compute_signature(hmac_secret: str, params: dict[str, str]) -> str:
    canonical = build_canonical(params)
    digest = hmac.new(hmac_secret.encode(), canonical.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def build_canonical(params: dict[str, str]) -> str:
    items = [(k, v) for k, v in params.items() if k != "sig"]
    items.sort()
    return "&".join(f"{k}={v}" for k, v in items)


def verify_signature(hmac_secret: str, params: dict[str, str], provided_sig: str) -> bool:
    expected = compute_signature(hmac_secret, params)
    return hmac.compare_digest(expected, provided_sig)


def verify_timestamp(ts: int) -> bool:
    now = int(time.time())
    return abs(now - ts) <= CLOCK_SKEW_SECONDS
