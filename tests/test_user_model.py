import asyncio
from uuid import uuid4

from app.crud import user as crud_user


async def test_create_user(session):
    email = f"create-{uuid4().hex[:8]}@x.test"
    user = await crud_user.create(session, email=email, username="alice", password="pw123")
    assert user.id is not None
    assert user.email == email
    assert user.hashed_password != "pw123"
    assert user.created_at is not None
    assert user.updated_at is not None
    assert user.last_login is None


async def test_authenticate_success_bumps_last_login(session):
    email = f"auth-ok-{uuid4().hex[:8]}@x.test"
    created = await crud_user.create(session, email=email, username="bob", password="pw")
    assert created.last_login is None

    out = await crud_user.authenticate(session, email=email, password="pw")
    assert out is not None
    assert out.id == created.id
    assert out.last_login is not None


async def test_authenticate_failure_no_bump(session):
    email = f"auth-fail-{uuid4().hex[:8]}@x.test"
    await crud_user.create(session, email=email, username="eve", password="correct")

    out = await crud_user.authenticate(session, email=email, password="wrong")
    assert out is None

    refetched = await crud_user.get_by_email(session, email=email)
    assert refetched is not None
    assert refetched.last_login is None


async def test_updated_at_auto_bumps(session):
    email = f"upd-{uuid4().hex[:8]}@x.test"
    user = await crud_user.create(session, email=email, username="carl", password="x")
    first_updated = user.updated_at
    assert first_updated is not None

    await asyncio.sleep(0.05)
    user.username = "carl-renamed"
    session.add(user)
    await session.commit()
    await session.refresh(user)

    assert user.updated_at is not None
    assert user.updated_at > first_updated
