from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Read real env vars first (compose injects them); fall back to a .env in the
    # backend dir or one level up at the repo root (local dev).
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # Postgres
    postgres_user: str = "mneme"
    postgres_password: str = "change_me_strong"
    postgres_db: str = "mnemosyne"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Auth
    secret_key: str = "dev-insecure-change-me"
    access_token_expire_minutes: int = 600
    algorithm: str = "HS256"
    cookie_secure: bool = False
    cookie_name: str = "mneme_session"
    allow_insecure_secret: bool = False

    # Storage
    blob_dir: str = "/data/blobs"
    max_upload_mb: int = 50

    # CORS
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Admin bootstrap
    admin_email: str = "admin@mnemosyne.local"
    admin_username: str = "admin"
    admin_password: str = "change_me_admin"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
