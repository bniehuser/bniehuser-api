import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # libpq env vars — the deployed runtime injects these directly; local
    # `.env` mirrors the same shape. `database_url` is composed below.
    PGHOST: str = "localhost"
    PGPORT: int = 5432
    PGUSER: str = "postgres"
    PGPASSWORD: str = ""
    PGDATABASE: str = "bniehuser"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.PGUSER}:{self.PGPASSWORD}"
            f"@{self.PGHOST}:{self.PGPORT}/{self.PGDATABASE}"
        )

    app_name: str = "bniehuser.com API"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    BACKEND_CORS_ORIGINS: str | None = "localhost:*"
    FIRST_SUPERUSER: str = "barry@bniehuser.com"
    FIRST_SUPERUSER_USERNAME: str = "barry"
    FIRST_SUPERUSER_PASSWORD: str = "test"
    USERS_OPEN_REGISTRATION: bool = True
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    RAPIDAPI_KEY: str | None = None


settings = Settings()
