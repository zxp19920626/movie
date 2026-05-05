"""Walle 渠道注入 adapter（MVP stub）

生产：subprocess 调 walle CLI（java -jar walle-cli.jar put -c CHANNEL in.apk out.apk）
MVP stub：直接 cp 母包到目标位置 + 在文件末尾追加一行 channel 标记，方便测试时验证

接口稳定，将来切真 walle 只换实现，业务代码不动。
"""

import os
from pathlib import Path
from typing import Protocol


class IChannelSigner(Protocol):
    def inject_channel(self, in_apk_path: str, out_apk_path: str, channel_code: str) -> None: ...


class WalleStubSigner:
    """MVP stub：cp 母包 + 追加 channel 标记字节（不是真签名，只是占位）"""

    def inject_channel(self, in_apk_path: str, out_apk_path: str, channel_code: str) -> None:
        Path(out_apk_path).parent.mkdir(parents=True, exist_ok=True)
        # 复制母包
        with open(in_apk_path, "rb") as src, open(out_apk_path, "wb") as dst:
            while chunk := src.read(1024 * 1024):
                dst.write(chunk)
            # 在文件末尾追加渠道标记（仅 stub，让验证时能区分；真 walle 写 APK Signing Block）
            marker = f"\n# WALLE_STUB_CHANNEL={channel_code}\n".encode()
            dst.write(marker)


class WalleCliSigner:
    """生产实现 stub：调用真 walle CLI；当前未启用，TODO 替换 stub"""

    def __init__(self, walle_jar_path: str) -> None:
        self.walle_jar_path = walle_jar_path
        if not os.path.isfile(walle_jar_path):
            raise FileNotFoundError(f"walle jar not found: {walle_jar_path}")

    def inject_channel(self, in_apk_path: str, out_apk_path: str, channel_code: str) -> None:
        import subprocess

        Path(out_apk_path).parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                "java",
                "-jar",
                self.walle_jar_path,
                "put",
                "-c",
                channel_code,
                in_apk_path,
                out_apk_path,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"walle failed: {result.stderr}")


_default_signer: IChannelSigner | None = None


def init_default_signer(stub: bool = True, walle_jar_path: str | None = None) -> None:
    global _default_signer
    if stub or not walle_jar_path:
        _default_signer = WalleStubSigner()
    else:
        _default_signer = WalleCliSigner(walle_jar_path)


def get_default_signer() -> IChannelSigner:
    if _default_signer is None:
        init_default_signer(stub=True)
    assert _default_signer is not None
    return _default_signer
