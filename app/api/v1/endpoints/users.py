from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import EmailStr
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_superuser, get_current_active_user
from app.core.config import settings
from app.core.security import hash_password
from app.crud import user as crud_user
from app.db import get_session
from app.models.user import User
from app.schemas.user import UserCreate, UserRead

router = APIRouter()


@router.get("/", response_model=list[UserRead])
async def read_users(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_active_superuser)],
    skip: int = 0,
    limit: int = 100,
) -> list[User]:
    return await crud_user.get_multi(session, skip=skip, limit=limit)


@router.post("/", response_model=UserRead)
async def create_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_active_superuser)],
    user_in: UserCreate,
) -> User:
    if await crud_user.get_by_email(session, email=user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered.")
    return await crud_user.create(
        session,
        email=user_in.email,
        username=user_in.username,
        password=user_in.password,
        is_superuser=user_in.is_superuser,
    )


@router.put("/me", response_model=UserRead)
async def update_user_me(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    password: Annotated[str | None, Body()] = None,
    username: Annotated[str | None, Body()] = None,
    email: Annotated[EmailStr | None, Body()] = None,
) -> User:
    if password is not None:
        current_user.hashed_password = hash_password(password)
    if username is not None:
        current_user.username = username
    if email is not None:
        current_user.email = email
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    return current_user


@router.get("/me", response_model=UserRead)
async def read_user_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    return current_user


@router.post("/open", response_model=UserRead)
async def create_user_open(
    session: Annotated[AsyncSession, Depends(get_session)],
    password: Annotated[str, Body(...)],
    email: Annotated[EmailStr, Body(...)],
    username: Annotated[str | None, Body()] = None,
) -> User:
    if not settings.USERS_OPEN_REGISTRATION:
        raise HTTPException(
            status_code=403,
            detail="Open user registration is forbidden on this server",
        )
    if await crud_user.get_by_email(session, email=email):
        raise HTTPException(status_code=400, detail="Email already registered.")
    return await crud_user.create(
        session,
        email=email,
        username=username or email.split("@", 1)[0],
        password=password,
    )


@router.get("/{user_id}", response_model=UserRead)
async def read_user_by_id(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    user = await crud_user.get(session, id=user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id != current_user.id and not crud_user.is_superuser(current_user):
        raise HTTPException(status_code=400, detail="The user doesn't have enough privileges")
    return user
