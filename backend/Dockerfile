# syntax=docker/dockerfile:1.7
# ===== Stage 1: builder — uv 装依赖到独立 .venv =====
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# uv 官方静态 binary
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /uvx /usr/local/bin/

WORKDIR /app

# 仅 copy 依赖描述，先 sync 一次 → 利用 layer cache
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# 再 copy 源码（业务代码）
COPY app ./app

# 把项目本体也 install 进来（package=false 时只是 path mark，仍要执行）
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# ===== Stage 2: runtime — 非 root，最小镜像 =====
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# 创建非 root 账户（UID/GID 1000 与多数 host 用户一致，volume 权限友好）
RUN groupadd --system --gid 1000 app \
 && useradd  --system --uid 1000 --gid app --create-home --shell /sbin/nologin app

WORKDIR /app

# 从 builder 拷贝 .venv + app/，所有权直接归 app:app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/app   /app/app

# storage 目录给写权限（生产换 OSS 后此 volume 可移除）
RUN mkdir -p /app/storage && chown -R app:app /app/storage

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
