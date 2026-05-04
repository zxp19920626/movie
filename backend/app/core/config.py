from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    database_url: str = "sqlite:///./dev.db"
    jwt_secret: str = "dev-secret-please-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    seed_admin_email: str = "admin@movie.local"
    seed_admin_password: str = "admin123"

    cors_allow_origins: str = "http://localhost:5174"

    @property
    def cors_origins_list(self) -> list[str]:
        return [s.strip() for s in self.cors_allow_origins.split(",") if s.strip()]


settings = Settings()
