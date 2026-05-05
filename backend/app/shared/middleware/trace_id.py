from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

HEADER_NAME = "X-Request-Id"

_trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="-")


def get_trace_id() -> str:
    return _trace_id_ctx.get()


def set_trace_id(value: str) -> None:
    _trace_id_ctx.set(value)


class TraceIdMiddleware(BaseHTTPMiddleware):
    """读 X-Request-Id；缺失则生成 uuid4。在 contextvar 里透传给 logger 用。

    生产环境上游网关（Cloudflare/nginx）会注入；本中间件只是兜底。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(HEADER_NAME)
        trace_id = incoming or uuid.uuid4().hex
        token = _trace_id_ctx.set(trace_id)
        try:
            response = await call_next(request)
        finally:
            _trace_id_ctx.reset(token)
        response.headers[HEADER_NAME] = trace_id
        return response
