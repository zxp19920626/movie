from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # ===== DB / 基础 =====
    database_url: str = "sqlite:///./dev.db"

    # ===== JWT =====
    jwt_secret: str = "dev-secret-please-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15  # admin
    refresh_token_days: int = 30  # admin
    user_access_token_minutes: int = 15  # C 端用户
    user_refresh_token_days: int = 30  # C 端用户

    # ===== Seed admin =====
    seed_admin_email: str = "admin@movie.local"
    seed_admin_password: str = "admin123"

    # ===== CORS =====
    cors_allow_origins: str = "http://localhost:5174"

    # ===== Google OAuth（dev 路线：未设则 mock）=====
    google_client_id: str = ""

    # ===== Cloudflare Turnstile（dev 路线：未设则 mock）=====
    turnstile_secret: str = ""

    # ===== OTP =====
    otp_ttl_minutes: int = 5
    otp_max_attempts: int = 5
    otp_rate_limit_per_phone_seconds: int = 60
    otp_rate_limit_per_ip_per_5min: int = 5
    otp_rate_limit_per_device_per_day: int = 10
    # 目标区域号段白名单（PROMPT.md C1+C3）
    allowed_phone_country_codes: str = (
        "+62,+84,+63,+66,+855,+95,+966,+971,+20,+966,+962,+961,+963,"  # SEA + 中东
        "+234,+27,+254,+251,+255,"  # 非洲
        "+55,+52,+54,+56,+57,+51,+58"  # 拉美
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [s.strip() for s in self.cors_allow_origins.split(",") if s.strip()]

    @property
    def allowed_phone_prefixes(self) -> list[str]:
        return [s.strip() for s in self.allowed_phone_country_codes.split(",") if s.strip()]


settings = Settings()
