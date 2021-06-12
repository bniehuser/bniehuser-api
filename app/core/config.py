import secrets
from typing import Optional

from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "bniehuser.com API"
    database_url: str
    SECRET_KEY: str = secrets.token_urlsafe(32)
    BACKEND_CORS_ORIGINS: Optional[str] = 'localhost:*'
    FIRST_SUPERUSER: str = 'barry@bniehuser.com'
    FIRST_SUPERUSER_USERNAME: str = 'barry'
    FIRST_SUPERUSER_PASSWORD: str = 'test'
    USERS_OPEN_REGISTRATION: bool = True
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    RAPIDAPI_KEY: Optional[str] = None

    class Config:
        env_file = ".env"


settings = Settings()
