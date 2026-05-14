"""T4.3：测试 ICacheService.invalidate_pattern 性能（10k key + 100 ops/s × 30s）

跑法：
    cd backend && uv run python scripts/perf_invalidate.py

测的是 InMemoryCacheService（MVP 默认实现）。RedisCacheService 走 SCAN+UNLINK，
基线在生产 Redis 实测（这里跑不了）；本脚本仅给本地 InMemory 实现一个上限。

输出：
    setup: 10000 keys 注入耗时
    每次 invalidate("cp:upgrade:*") 的耗时（min/p50/p95/p99/max + 平均）
    平均 ops 实际能跑多少
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.shared.cache_service import InMemoryCacheService  # noqa: E402

KEY_COUNT = 10_000
TARGET_OPS = 100
DURATION_SECONDS = 30


def main() -> None:
    cache = InMemoryCacheService()
    tenant = "perf-tenant-uuid"

    # setup：注入 10k key，全部前缀 cp:upgrade:{tenant}:
    setup_start = time.perf_counter()
    for i in range(KEY_COUNT):
        cache.set(f"cp:upgrade:{tenant}:device-{i}", {"v": i}, ttl_seconds=60)
    setup_elapsed = time.perf_counter() - setup_start
    print(f"[setup] 注入 {KEY_COUNT} keys 耗时 {setup_elapsed * 1000:.1f}ms")

    # 每次 invalidate 后立刻 re-populate（不然第二次没东西可删，测不出真实开销）
    durations_ms: list[float] = []
    ops = 0
    start = time.perf_counter()
    interval = 1.0 / TARGET_OPS
    next_tick = start

    while True:
        now = time.perf_counter()
        if now - start >= DURATION_SECONDS:
            break
        if now < next_tick:
            time.sleep(max(0.0, next_tick - now))

        # 单次：先删，再补回去（保持 invalidate 输入规模稳定）
        t0 = time.perf_counter()
        removed = cache.invalidate_pattern(f"cp:upgrade:{tenant}:*")
        t1 = time.perf_counter()
        durations_ms.append((t1 - t0) * 1000)

        # 立即补回 1k key（足够大但不重新跑满 10k，避免单次循环 setup 把基线吃掉）
        for i in range(1_000):
            cache.set(f"cp:upgrade:{tenant}:device-{i}", {"v": i}, ttl_seconds=60)

        ops += 1
        next_tick += interval
        _ = removed

    total = time.perf_counter() - start
    avg = statistics.mean(durations_ms)
    p50 = statistics.median(durations_ms)
    p95 = statistics.quantiles(durations_ms, n=20)[18] if len(durations_ms) >= 20 else max(durations_ms)
    p99 = statistics.quantiles(durations_ms, n=100)[98] if len(durations_ms) >= 100 else max(durations_ms)
    print(f"[invalidate] {ops} ops in {total:.1f}s → 实际 {ops / total:.1f} ops/s（目标 {TARGET_OPS}）")
    print(f"[invalidate] 耗时 ms — avg={avg:.3f} p50={p50:.3f} p95={p95:.3f} p99={p99:.3f} "
          f"min={min(durations_ms):.3f} max={max(durations_ms):.3f}")
    print(f"[invalidate] 注：本次每轮删完后立即补 1000 keys，模拟稳态。首轮 input 规模 ~10000，后续 ~1000。")


if __name__ == "__main__":
    main()
