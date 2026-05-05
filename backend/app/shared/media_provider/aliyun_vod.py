"""阿里云 VOD 适配器（实现 IMediaProvider + IPlayTokenProvider）。

当前状态：**stub**。SDK 未引入；只占位接口形状，让上层业务（content）能写得下去。
P4 阶段把 SDK 装进来后替换成真调用，业务代码 0 改动。

切换 SaaS（譬如转 mux / cloudflare stream）时也只换这个文件。
"""

from __future__ import annotations

import os
from datetime import timedelta

from app.core.clock import get_clock
from app.shared.media_provider.protocol import MediaInfo, PlayToken


class AliyunVodProvider:
    """实现 IMediaProvider。MVP stub：返回占位数据；P4 接入真 SDK。"""

    def __init__(
        self,
        *,
        region: str = "ap-southeast-1",
        access_key_id: str | None = None,
        access_key_secret: str | None = None,
    ) -> None:
        self.region = region
        self.access_key_id = access_key_id or os.getenv("ALIYUN_VOD_AK_ID", "")
        self.access_key_secret = access_key_secret or os.getenv("ALIYUN_VOD_AK_SECRET", "")
        # SDK 客户端在 _init_client() 里懒构造；MVP 不实际建连接
        self._client = None

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        if not (self.access_key_id and self.access_key_secret):
            raise RuntimeError(
                "AliyunVodProvider stub：未配置 ALIYUN_VOD_AK_ID/SECRET；"
                "P4 阶段接入 SDK 后修改本类 _ensure_client 真正建客户端"
            )
        # P4：from alibabacloud_vod20170321 import VodClient
        # self._client = VodClient(...)
        raise NotImplementedError("AliyunVodProvider 真实 SDK 接入留待 P4")

    def get_media(self, file_id: str) -> MediaInfo:
        self._ensure_client()
        raise NotImplementedError

    def list_media(self, page: int, page_size: int) -> list[MediaInfo]:  # noqa: ARG002
        self._ensure_client()
        raise NotImplementedError


class AliyunPlayTokenProvider:
    """实现 IPlayTokenProvider — 签发 VOD PlayAuth。

    MVP stub：返回伪 token（业务可端到端跑通拼接逻辑，但实际无法播放）。
    P4 接入 GetVideoPlayAuth API 后替换。
    """

    def __init__(self, *, ttl_default_sec: int = 300) -> None:
        self.ttl_default_sec = ttl_default_sec

    def issue_play_token(
        self, file_id: str, *, client_ip: str, ttl_sec: int  # noqa: ARG002
    ) -> PlayToken:
        # P4：调阿里云 VOD GetVideoPlayAuth；这里返回 stub
        clock = get_clock()
        return PlayToken(
            token=f"stub-playauth-{file_id}",
            play_url=f"https://stub.vod.example/{file_id}.m3u8",
            expires_at=clock.now() + timedelta(seconds=ttl_sec or self.ttl_default_sec),
        )
