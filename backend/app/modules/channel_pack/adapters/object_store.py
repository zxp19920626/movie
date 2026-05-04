"""对象存储 adapter

MVP 阶段用本地 FS（backend/storage/apks/），生产换 OSS：实现同样接口换具体类即可。

key 格式约定：
  apks/{tenant_uuid}/master/{version_code}.apk
  apks/{tenant_uuid}/signed/{version_code}/{channel_code}.apk
"""

import hashlib
import os
import shutil
from pathlib import Path
from typing import BinaryIO, Protocol


class IObjectStore(Protocol):
    def put_stream(self, key: str, stream: BinaryIO) -> tuple[str, int]: ...
    def put_file(self, key: str, src_path: str) -> tuple[str, int]: ...
    def exists(self, key: str) -> bool: ...
    def get_local_path(self, key: str) -> str | None: ...
    def public_url(self, key: str) -> str: ...
    def delete(self, key: str) -> None: ...


class LocalFSObjectStore:
    """本地 FS 实现：backend/storage/apks/...，URL 走 FastAPI StaticFiles 挂载到 /storage/"""

    def __init__(self, root_dir: str, public_url_prefix: str = "/storage") -> None:
        self.root = Path(root_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.public_url_prefix = public_url_prefix.rstrip("/")

    def _full_path(self, key: str) -> Path:
        # 防目录穿越
        key = key.lstrip("/")
        if ".." in key.split("/"):
            raise ValueError(f"invalid key: {key}")
        return self.root / key

    def put_stream(self, key: str, stream: BinaryIO) -> tuple[str, int]:
        path = self._full_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        sha = hashlib.sha256()
        size = 0
        with path.open("wb") as f:
            while chunk := stream.read(1024 * 1024):
                sha.update(chunk)
                size += len(chunk)
                f.write(chunk)
        return sha.hexdigest(), size

    def put_file(self, key: str, src_path: str) -> tuple[str, int]:
        with open(src_path, "rb") as f:
            return self.put_stream(key, f)

    def exists(self, key: str) -> bool:
        return self._full_path(key).is_file()

    def get_local_path(self, key: str) -> str | None:
        p = self._full_path(key)
        return str(p) if p.is_file() else None

    def public_url(self, key: str) -> str:
        # 本地 dev 直接拼 /storage/{key}；生产 OSS 会签 CDN URL
        return f"{self.public_url_prefix}/{key.lstrip('/')}"

    def delete(self, key: str) -> None:
        p = self._full_path(key)
        if p.is_file():
            p.unlink()


# 单例（main.py 启动时注入路径）
_default_store: IObjectStore | None = None


def init_default_store(root_dir: str, public_url_prefix: str = "/storage") -> None:
    global _default_store
    _default_store = LocalFSObjectStore(root_dir, public_url_prefix)


def get_default_store() -> IObjectStore:
    if _default_store is None:
        # fallback：当前工作目录下 storage
        init_default_store(os.path.join(os.getcwd(), "storage"))
    assert _default_store is not None
    return _default_store


def compute_master_key(tenant_uuid: str, version_code: int) -> str:
    return f"apks/{tenant_uuid}/master/{version_code}.apk"


def compute_signed_key(tenant_uuid: str, version_code: int, channel_code: str) -> str:
    return f"apks/{tenant_uuid}/signed/{version_code}/{channel_code}.apk"


def file_sha256(path: str) -> tuple[str, int]:
    sha = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            sha.update(chunk)
            size += len(chunk)
    return sha.hexdigest(), size


def copy_file(src: str, dst: str) -> None:
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
