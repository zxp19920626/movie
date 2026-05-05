"""user 模块 Pydantic schemas"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# ===== Email =====


class EmailRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = None
    country: str | None = None
    app_id: int | None = None  # cp_apps.id；可空


class EmailLoginRequest(BaseModel):
    email: str  # 与 admin login 一致，登录用 str 不严格校验
    password: str


# ===== Google =====


class GoogleLoginRequest(BaseModel):
    id_token: str
    country: str | None = None
    app_id: int | None = None


# ===== Phone OTP =====


class PhoneSendOtpRequest(BaseModel):
    phone: str = Field(pattern=r"^\+\d{6,15}$")
    turnstile_token: str | None = None
    device_id: str | None = None


class PhoneVerifyRequest(BaseModel):
    phone: str = Field(pattern=r"^\+\d{6,15}$")
    code: str = Field(min_length=4, max_length=8)
    display_name: str | None = None
    country: str | None = None
    app_id: int | None = None


# ===== Refresh =====


class RefreshRequest(BaseModel):
    refresh_token: str


# ===== Devices =====


class DeviceRegisterRequest(BaseModel):
    device_id: str = Field(min_length=4, max_length=128)
    platform: str = Field(default="android", max_length=16)
    app_version: str | None = Field(default=None, max_length=32)
    channel: str | None = Field(default=None, max_length=64)
    push_token: str | None = Field(default=None, max_length=256)
    country: str | None = Field(default=None, max_length=8)
    app_id: int | None = None


# ===== Out =====


class UserOut(BaseModel):
    id: str
    uuid: str
    email: str | None
    phone: str | None
    country_code: str | None
    display_name: str
    avatar_url: str | None
    status: str
    country: str | None
    preferred_language: str
    app_id: int | None
    registered_at: datetime | None
    last_active_at: datetime | None


class TokensOut(BaseModel):
    access_token: str
    refresh_token: str
    user: UserOut


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    device_id: str
    app_id: int | None
    platform: str
    app_version: str | None
    channel: str | None
    country: str | None
    last_seen_at: datetime
