from datetime import UTC, datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User


async def get(session: AsyncSession, *, id: int) -> User | None:
    return await session.get(User, id)


async def get_by_email(session: AsyncSession, *, email: str) -> User | None:
    result = await session.exec(select(User).where(User.email == email))
    return result.first()


async def get_multi(session: AsyncSession, *, skip: int = 0, limit: int = 100) -> list[User]:
    result = await session.exec(select(User).offset(skip).limit(limit))
    return list(result.all())


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
        hashed_password=hash_password(password),
        is_superuser=is_superuser,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User | None:
    user = await get_by_email(session, email=email)
    if user is None or not verify_password(password, user.hashed_password):
        return None
    user.last_login = datetime.now(UTC)
    await session.commit()
    await session.refresh(user)
    return user


async def update_password(session: AsyncSession, *, user: User, new_password: str) -> User:
    user.hashed_password = hash_password(new_password)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def is_active(user: User) -> bool:
    return user.is_active


def is_superuser(user: User) -> bool:
    return user.is_superuser
