from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "bniehuser.com API"

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

    SECRET_KEY: str = "dev-insecure-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    FORWARD_HMAC_SECRET: str = "dev-hmac-change-me"
    BOT_API_TOKEN: str = "dev-bot-token-change-me"
    # Cross-tenant URL of the discord-bot service; catalog wires this to
    # http://python:8001 (shared-container name, see infra sites.yaml).
    DISCORD_BOT_URL: str = "http://python:8001"

    BOOTSTRAP_USER_EMAIL: str = "barry@bniehuser.com"
    BOOTSTRAP_USER_PASSWORD: str = "change-me"

    FINNHUB_API_KEY: str | None = None
    TWELVEDATA_API_KEY: str | None = None
    SPOONACULAR_API_KEY: str | None = None

    USERS_OPEN_REGISTRATION: bool = True

    BACKEND_CORS_ORIGINS: list[AnyHttpUrl] = []
    BACKEND_CORS_ORIGIN_REGEX: str = r"^http://localhost:51(7[3-9]|80)$"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("["):
                return v
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


settings = Settings()
