"""T4.4：WalleStubSigner.inject_channel 性能（验证生产假设 1-3s/包是否合理）

跑法：
    cd backend && uv run python scripts/perf_walle.py

stub 只 cp + 追加几个字节，应该 << 100ms（输入 APK 越大耗时越长，I/O bound）。
生产 walle CLI 调 java -jar 启动 + 写 APK Signing Block，假设 1-3s/包。
本脚本用 stub 测一个下限基线 + 一个"用足够大输入"模拟近似上限。
"""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.modules.channel_pack.adapters.walle import WalleStubSigner  # noqa: E402

ITERATIONS = 10


def time_signer(input_size_bytes: int) -> tuple[list[float], int]:
    """造一个 input_size_bytes 大小的"假 APK"，跑 ITERATIONS 次签名，返回每次耗时 ms"""
    signer = WalleStubSigner()
    durations_ms: list[float] = []
    out_sizes: list[int] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        in_apk = tmp_path / "master.apk"
        # 写入随机字节 input_size_bytes（模拟 APK）
        in_apk.write_bytes(os.urandom(input_size_bytes))

        for i in range(ITERATIONS):
            out_apk = tmp_path / f"signed-{i}.apk"
            t0 = time.perf_counter()
            signer.inject_channel(str(in_apk), str(out_apk), f"channel-{i}")
            t1 = time.perf_counter()
            durations_ms.append((t1 - t0) * 1000)
            out_sizes.append(out_apk.stat().st_size)
    return durations_ms, out_sizes[0] if out_sizes else 0


def summarize(label: str, durations: list[float], out_size: int) -> None:
    avg = statistics.mean(durations)
    p50 = statistics.median(durations)
    print(f"[{label}] iterations={len(durations)} output_size={out_size} bytes")
    print(f"  耗时 ms — min={min(durations):.2f} avg={avg:.2f} p50={p50:.2f} "
          f"max={max(durations):.2f}")


def main() -> None:
    print("WalleStubSigner 性能基线（注：stub = cp + 追加字节，不是真签名）")
    print()

    # 1) 小输入（1KB）：纯函数调用开销下限
    durations, sz = time_signer(1024)
    summarize("input=1KB", durations, sz)

    # 2) 中等（1MB）：典型 SDK
    durations, sz = time_signer(1024 * 1024)
    summarize("input=1MB", durations, sz)

    # 3) 大（20MB）：典型完整 APK
    durations, sz = time_signer(20 * 1024 * 1024)
    summarize("input=20MB", durations, sz)

    print()
    print("生产假设对比：")
    print("  walle CLI（java -jar 启动 + write APK Signing Block）假设 1000~3000 ms/包")
    print("  stub 实测 << 100 ms（差 1~2 个数量级）→ 单元测试无开销；生产实测必跑 P6.4 任务")


if __name__ == "__main__":
    main()
