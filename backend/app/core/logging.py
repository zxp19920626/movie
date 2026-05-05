from __future__ import annotations

import logging
import sys

import structlog

from app.shared.middleware.trace_id import get_trace_id


def _add_trace_id(_, __, event_dict: dict) -> dict:
    event_dict["trace_id"] = get_trace_id()
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    """启动时调一次；之后用 structlog.get_logger() 拿 logger。

    输出 JSON：ts / level / logger / trace_id / module / event / 其他 kwargs
    """
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts")

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        _add_trace_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 把 stdlib logging（uvicorn / sqlalchemy）也走 JSON
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # uvicorn/access 日志降噪
    logging.getLogger("uvicorn.access").setLevel("WARNING")


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
