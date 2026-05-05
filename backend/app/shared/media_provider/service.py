"""media_service：业务代码只用这里的 get_media_provider() / get_play_token_provider()。

依赖注入入口；测试可调 set_*_provider 注入 fake，生产由 main.py 启动时调
configure_default_providers() 装真实实现。
"""

from __future__ import annotations

from app.shared.media_provider.protocol import IMediaProvider, IPlayTokenProvider

_media: IMediaProvider | None = None
_play: IPlayTokenProvider | None = None


def get_media_provider() -> IMediaProvider:
    if _media is None:
        raise RuntimeError(
            "media_provider 未配置；启动时调 configure_default_providers() 或测试用 set_media_provider()"
        )
    return _media


def get_play_token_provider() -> IPlayTokenProvider:
    if _play is None:
        raise RuntimeError("play_token_provider 未配置；同 get_media_provider")
    return _play


def set_media_provider(p: IMediaProvider) -> None:
    global _media
    _media = p


def set_play_token_provider(p: IPlayTokenProvider) -> None:
    global _play
    _play = p


def configure_default_providers() -> None:
    """启动时调一次。MVP 装阿里云 VOD stub；P4 切到真实现时改这里即可。"""
    from app.shared.media_provider.aliyun_vod import (
        AliyunPlayTokenProvider,
        AliyunVodProvider,
    )

    set_media_provider(AliyunVodProvider())
    set_play_token_provider(AliyunPlayTokenProvider())
