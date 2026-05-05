from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class MediaInfo:
    file_id: str
    duration_sec: int
    cover_url: str | None
    status: str  # "uploading" | "transcoding" | "ready" | "failed"


@dataclass(frozen=True)
class PlayToken:
    token: str
    play_url: str
    expires_at: datetime


class IMediaProvider(Protocol):
    """媒体源抽象。MVP 阶段无实现；P4 阿里云 VOD 实现该接口。

    业务代码只持有 IMediaProvider，不许直接调 VOD SDK；
    切换 SaaS（譬如转用 mux/aws medialive）时只换一个文件。
    """

    def get_media(self, file_id: str) -> MediaInfo: ...

    def list_media(self, page: int, page_size: int) -> list[MediaInfo]: ...


class IPlayTokenProvider(Protocol):
    """播放凭证抽象。VOD 用 PlayAuth；自建 HLS 时换签名 URL，接口不变。"""

    def issue_play_token(self, file_id: str, *, client_ip: str, ttl_sec: int) -> PlayToken: ...
