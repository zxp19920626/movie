"""Celery app（P2.19）— 与 BackgroundTasks 并存的可选异步路径。

启用条件：settings.celery_broker_url 非空（默认走 BackgroundTasks）。
适用场景：APK 签名 fan-out / VOD sync_vod_metadata 等需要：
  - 跨进程跑（API worker 不占 CPU）
  - 失败重试（BackgroundTasks 没有 retry/backoff 机制）
  - 任务可观测（flower / prometheus exporter）

依赖：未默认装。启用前：
  uv add celery[redis]>=5.4

启动 worker：
  cd backend && uv run celery -A app.celery_app worker --loglevel=info --concurrency=2

任务定义在各业务模块自身的 tasks/ 子目录，celery_app 通过 include 自动加载。
"""

from __future__ import annotations

from app.core.config import settings


def make_celery():
    """延迟构造：装好 celery 包 + 配 broker 才返回真 app；否则返回 None。"""
    if not settings.celery_broker_url:
        return None
    try:
        from celery import Celery
    except ImportError:
        return None

    app = Celery(
        "movie",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend or settings.celery_broker_url,
        include=[
            "app.modules.channel_pack.tasks.sign_apk",  # 现有 BackgroundTasks 入口
            # 后续添加：
            #   "app.modules.content.tasks.vod_sync",
            #   "app.modules.content.tasks.reconcile",
        ],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        # 失败重试默认（任务级可覆盖）
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        # 防 task 永久卡住
        task_time_limit=600,  # 10 分钟硬上限
        task_soft_time_limit=540,
    )
    return app


celery_app = make_celery()
