import structlog

from app.core.config import settings
from app.crud import user as crud_user
from app.db import async_session

log = structlog.get_logger()


async def create_superuser_if_missing() -> None:
    async with async_session() as session:
        existing = await crud_user.get_by_email(session, email=settings.BOOTSTRAP_USER_EMAIL)
        if existing is not None:
            log.info("bootstrap_user_exists", email=settings.BOOTSTRAP_USER_EMAIL)
            return
        await crud_user.create(
            session,
            email=settings.BOOTSTRAP_USER_EMAIL,
            username=settings.BOOTSTRAP_USER_EMAIL.split("@", 1)[0],
            password=settings.BOOTSTRAP_USER_PASSWORD,
            is_superuser=True,
        )
        log.info("bootstrap_user_created", email=settings.BOOTSTRAP_USER_EMAIL)
