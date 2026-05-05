"""限流工具：FastAPI Depends 形式。

设计：
- 后端走 cache_service.incr（Redis 实现 INCR+EXPIRE，进程内字典 fallback）
- 命中超限 → 429 Too Many Requests + Retry-After header
- key 由 (scope, ip) 组合：scope 用来给不同接口独立限流桶
- 不在中间件层做（避免 admin / 健康检查也被限）；按需挂 Depends

用法：
    from app.shared.middleware.rate_limit import rate_limit

    @router.get("/play-token", dependencies=[Depends(rate_limit("play_token", 30, 60))])
    def get_play_token(...): ...
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException, Request, Response

from app.shared.cache_service import get_cache, make_key


def _client_ip(request: Request) -> str:
    # 优先信任反代 X-Forwarded-For 第一段（生产 nginx / Cloudflare 注入）
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"  # noqa: S104


def rate_limit(scope: str, limit: int, per_seconds: int) -> Callable[..., None]:
    """工厂：返回一个可作为 Depends 用的 callable。

    Args:
        scope: 桶名，避免不同接口共用计数（例 "play_token" / "videos_search"）
        limit: per_seconds 内允许的最大请求数
        per_seconds: 滑动窗（实际上是固定窗，简单可用）
    """

    def dep(request: Request, response: Response) -> None:
        ip = _client_ip(request)
        key = make_key("rl", scope, ip)
        cache = get_cache()
        n = cache.incr(key, ttl_seconds=per_seconds)
        # 把当前用量回写 header，方便前端调试
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - n))
        if n > limit:
            response.headers["Retry-After"] = str(per_seconds)
            raise HTTPException(
                status_code=429,
                detail=f"rate limited (scope={scope}, limit={limit}/{per_seconds}s)",
            )

    return dep
