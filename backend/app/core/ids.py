from __future__ import annotations

import os
import secrets
import time
import uuid


def uuid7() -> uuid.UUID:
    """RFC 9562 UUIDv7：48 位毫秒时间戳前缀，保证按时间排序，剩余 74 位随机。

    用作业务主键时排序友好，索引顺序写入，避免 uuid4 的随机分布导致 B-tree 写放大。
    """
    ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF  # 48 bits
    rand = secrets.token_bytes(10)  # 80 bits
    b = ms.to_bytes(6, "big") + rand
    # 设置版本位 (b[6] 高 4 位 = 0111)
    b = b[:6] + bytes([(0x70 | (b[6] & 0x0F))]) + b[7:]
    # 设置 variant 位 (b[8] 高 2 位 = 10)
    b = b[:8] + bytes([(0x80 | (b[8] & 0x3F))]) + b[9:]
    return uuid.UUID(bytes=b)


def new_id() -> str:
    return str(uuid7())


# Snowflake-like 64-bit int：41 ms 时间戳 + 10 worker + 12 序列
_EPOCH_MS = 1704067200000  # 2024-01-01 UTC
_WORKER_ID = int(os.getenv("WORKER_ID", "0")) & 0x3FF
_seq = 0
_last_ms = -1


def snowflake_id() -> int:
    global _seq, _last_ms
    now_ms = int(time.time() * 1000) - _EPOCH_MS
    if now_ms == _last_ms:
        _seq = (_seq + 1) & 0xFFF
        if _seq == 0:
            while now_ms <= _last_ms:
                now_ms = int(time.time() * 1000) - _EPOCH_MS
    else:
        _seq = 0
    _last_ms = now_ms
    return (now_ms << 22) | (_WORKER_ID << 12) | _seq
