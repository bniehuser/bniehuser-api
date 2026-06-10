from datetime import UTC, datetime

import bcrypt
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import User


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


async def get_by_email(session: AsyncSession, *, email: str) -> User | None:
    result = await session.exec(select(User).where(User.email == email))
    return result.first()


async def create(
    session: AsyncSession,
    *,
    email: str,
    username: str,
    password: str,
    is_superuser: bool = False,
) -> User:
    user = User(
        email=email,
        username=username,
        hashed_password=_hash_password(password),
        is_superuser=is_superuser,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User | None:
    user = await get_by_email(session, email=email)
    if user is None or not _verify_password(password, user.hashed_password):
        return None
    user.last_login = datetime.now(UTC)
    await session.commit()
    await session.refresh(user)
    return user


def is_superuser(user: User) -> bool:
    return user.is_superuser
