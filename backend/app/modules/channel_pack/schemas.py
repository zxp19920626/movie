"""channel_pack Pydantic schemas"""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

POPUP_STRATEGIES = Literal[
    "once_per_launch",
    "once_per_session",
    "once_per_day",
    "once_per_week",
    "once_per_release",
    "custom_interval",
]

# ISO 639-1（小写）+ 可选 -XX（大写国家后缀），如 "en" / "zh" / "en-US"
_I18N_KEY_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


def _validate_i18n_keys(d: dict[str, str], value_max_len: int) -> dict[str, str]:
    for k, v in d.items():
        if not _I18N_KEY_RE.match(k):
            raise ValueError(
                f"invalid i18n key {k!r}: must match ISO 639-1 (e.g. 'en', 'zh', 'en-US')"
            )
        if not isinstance(v, str) or len(v) < 1 or len(v) > value_max_len:
            raise ValueError(
                f"invalid i18n value for key {k!r}: length must be 1..{value_max_len}"
            )
    return d


class PopupButton(BaseModel):
    """升级弹窗 CTA 按钮（PRD 4.2.5.1）"""

    id: str = Field(max_length=32)
    type: Literal["browser", "playstore", "inapp_apk", "deeplink", "none"]
    text_i18n: dict[str, str] = Field(min_length=1)
    url_i18n: dict[str, str] | None = None
    style: Literal["primary", "secondary", "danger"] | None = None
    target: dict[str, str] | None = None

    @field_validator("text_i18n")
    @classmethod
    def _validate_text_i18n(cls, v: dict[str, str]) -> dict[str, str]:
        return _validate_i18n_keys(v, value_max_len=200)

    @field_validator("url_i18n")
    @classmethod
    def _validate_url_i18n(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if v is None:
            return v
        return _validate_i18n_keys(v, value_max_len=500)

    @model_validator(mode="after")
    def _validate_url_required_for_non_none_type(self) -> "PopupButton":
        if self.type != "none" and not self.url_i18n:
            raise ValueError("url_i18n is required when type is not 'none'")
        return self


# ============== App (租户) ==============


class AppCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    package_name: str = Field(min_length=3, max_length=255)
    owner_admin_user_id: int | None = None  # super_admin 可指定，否则用当前 admin


class AppUpdate(BaseModel):
    name: str | None = None
    package_name: str | None = None
    status: Literal["active", "suspended"] | None = None


class AppOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_uuid: str
    name: str
    package_name: str
    owner_admin_user_id: int
    status: str
    created_at: datetime


class AppCreateResponse(BaseModel):
    """创建租户唯一一次返回明文 api_key + hmac_secret，丢失后只能 regenerate"""

    app: AppOut
    api_key: str
    hmac_secret: str


class AppRegenerateResponse(BaseModel):
    api_key: str
    hmac_secret: str


# ============== Channel ==============


class ChannelCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=128)
    is_play_store: bool = False
    signing_strategy: Literal["walle", "none", "play_signed"] = "walle"
    enabled: bool = True
    priority: int = 10


class ChannelUpdate(BaseModel):
    name: str | None = None
    is_play_store: bool | None = None
    signing_strategy: Literal["walle", "none", "play_signed"] | None = None
    enabled: bool | None = None
    priority: int | None = None


class ChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    app_id: int
    code: str
    name: str
    is_play_store: bool
    signing_strategy: str
    enabled: bool
    priority: int


# ============== Version ==============


class VersionMetadata(BaseModel):
    version_code: int = Field(gt=0)
    version_name: str = Field(min_length=1, max_length=32)
    min_supported_version_code: int = 0
    changelog_i18n: dict[str, str] = Field(default_factory=dict)


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    app_id: int
    version_code: int
    version_name: str
    master_apk_sha256: str
    master_apk_size: int
    min_supported_version_code: int
    changelog_i18n: dict[str, str]
    status: str
    uploaded_at: datetime
    released_at: datetime | None


# ============== Rule ==============


class RuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    enabled: bool = True
    version_code_min: int = Field(ge=0)
    version_code_max: int = Field(ge=0)
    channel_codes: list[str] = Field(default_factory=list)
    country_codes: list[str] = Field(default_factory=list)
    device_id_hash_mod_min: int = Field(ge=0, le=99, default=0)
    device_id_hash_mod_max: int = Field(ge=0, le=99, default=99)
    target_version_code: int = Field(gt=0)
    is_force: bool = False
    can_skip: bool = True
    popup_strategy: POPUP_STRATEGIES = "once_per_session"
    popup_interval_hours: int | None = None
    popup_title_i18n: dict[str, str] = Field(default_factory=dict)
    popup_content_i18n: dict[str, str] = Field(default_factory=dict)
    confirm_text_i18n: dict[str, str] = Field(default_factory=dict)
    cancel_text_i18n: dict[str, str] = Field(default_factory=dict)
    popup_buttons: list[PopupButton] = Field(default_factory=list, max_length=5)
    priority: int = 10
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class RuleUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    version_code_min: int | None = None
    version_code_max: int | None = None
    channel_codes: list[str] | None = None
    country_codes: list[str] | None = None
    device_id_hash_mod_min: int | None = None
    device_id_hash_mod_max: int | None = None
    target_version_code: int | None = None
    is_force: bool | None = None
    can_skip: bool | None = None
    popup_strategy: POPUP_STRATEGIES | None = None
    popup_interval_hours: int | None = None
    popup_title_i18n: dict[str, str] | None = None
    popup_content_i18n: dict[str, str] | None = None
    confirm_text_i18n: dict[str, str] | None = None
    cancel_text_i18n: dict[str, str] | None = None
    popup_buttons: list[PopupButton] | None = Field(default=None, max_length=5)
    priority: int | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    app_id: int
    name: str
    enabled: bool
    version_code_min: int
    version_code_max: int
    channel_codes: list[str]
    country_codes: list[str]
    device_id_hash_mod_min: int
    device_id_hash_mod_max: int
    target_version_code: int
    is_force: bool
    can_skip: bool
    popup_strategy: str
    popup_interval_hours: int | None
    popup_title_i18n: dict[str, str]
    popup_content_i18n: dict[str, str]
    confirm_text_i18n: dict[str, str]
    cancel_text_i18n: dict[str, str]
    popup_buttons: list[PopupButton] = Field(default_factory=list)
    priority: int
    effective_from: datetime | None
    effective_to: datetime | None
    created_at: datetime


class RulePreviewRequest(BaseModel):
    version_code: int
    channel: str
    country: str = ""
    device_id: str


class RulePreviewResponse(BaseModel):
    has_update: bool
    matched_rule_id: int | None = None
    matched_rule_name: str | None = None
    target_version_code: int | None = None
    is_force: bool | None = None
    debug_steps: list[str] = Field(default_factory=list)


# ============== Signing Job ==============


class SigningJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    app_id: int
    version_code: int
    channel_code: str
    status: str
    output_oss_key: str
    output_sha256: str
    output_size: int
    attempts: int
    last_error: str
    started_at: datetime | None
    finished_at: datetime | None


# ============== Public /upgrade/check ==============


class UpgradeCheckResponse(BaseModel):
    has_update: bool
    target_version_code: int | None = None
    target_version_name: str | None = None
    is_force: bool | None = None
    can_skip: bool | None = None
    popup_strategy: str | None = None
    popup_interval_hours: int | None = None
    popup_title: str | None = None
    popup_content: str | None = None
    confirm_text: str | None = None
    cancel_text: str | None = None
    download_url: str | None = None
    sha256: str | None = None
    size: int | None = None


# ============== List wrapper ==============


class PaginatedListInt(BaseModel):
    """通用分页响应（用 generic 嫌烦，每种 items 都列）"""

    pass


class AppList(BaseModel):
    items: list[AppOut]
    total: int


class ChannelList(BaseModel):
    items: list[ChannelOut]
    total: int


class VersionList(BaseModel):
    items: list[VersionOut]
    total: int


class RuleList(BaseModel):
    items: list[RuleOut]
    total: int


class SigningJobList(BaseModel):
    items: list[SigningJobOut]
    total: int
