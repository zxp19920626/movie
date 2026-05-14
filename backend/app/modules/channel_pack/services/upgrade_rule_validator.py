"""升级规则按钮业务校验（C1 + C2 + https-only）。

PRD 4.2.5 红线：
- Play Store 渠道禁止 inapp_apk 类型按钮（C2，Play 政策）
- 所有 url_i18n value 必须 https://
- 所有 url 的 host 必须落在 cp_apps.allowed_upgrade_hosts 白名单内（严格 host 匹配，不含子域名）

Service 入口校验（红线 #2 + C1）：router 层捕 UpgradeRuleValidationError → 422。
"""

from __future__ import annotations

from urllib.parse import urlparse

from ..models import CpApp, CpChannel
from ..schemas import PopupButton


class UpgradeRuleValidationError(ValueError):
    """业务规则违反；router 层捕获转 422/4xx。"""


def validate_buttons_for_app(
    app: CpApp,
    channel: CpChannel | None,
    buttons: list[PopupButton],
) -> None:
    if not buttons:
        return

    whitelist = [h.lower() for h in (app.allowed_upgrade_hosts or [])]
    is_play = bool(channel and channel.is_play_store)

    for btn in buttons:
        if is_play and btn.type == "inapp_apk":
            raise UpgradeRuleValidationError(
                f"play_store_channel_rejects_inapp_apk: button id={btn.id}"
            )

        if not btn.url_i18n:
            # type='none' 或无 URL 时跳过 https / host 检查
            continue

        for locale, url in btn.url_i18n.items():
            parsed = urlparse(url)
            if parsed.scheme != "https":
                raise UpgradeRuleValidationError(
                    f"https_only: button id={btn.id} locale={locale} url={url}"
                )

            host = (parsed.hostname or "").lower()
            if host not in whitelist:
                raise UpgradeRuleValidationError(
                    f"host_not_in_whitelist: button id={btn.id} locale={locale} "
                    f"host={host} whitelist={whitelist}"
                )
