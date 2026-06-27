from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.tokens import generate_password_reset_token, verify_password_reset_token
from app.core.config import settings
from app.core.security import create_access_token
from app.crud import user as crud_user
from app.db import get_session
from app.schemas.auth import Msg, Token

router = APIRouter()


@router.post("/login/access-token", response_model=Token, operation_id="login")
async def login_access_token(
    session: Annotated[AsyncSession, Depends(get_session)],
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    user = await crud_user.authenticate(
        session, email=form_data.username, password=form_data.password
    )
    if user is None:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if not crud_user.is_active(user):
        raise HTTPException(status_code=400, detail="Inactive user")
    assert user.id is not None
    token = create_access_token(
        user.id, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return Token(access_token=token, token_type="bearer")


@router.post(
    "/password-recovery/{email}",
    response_model=Msg,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    operation_id="recoverPassword",
)
async def recover_password(
    email: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Msg:
    user = await crud_user.get_by_email(session, email=email)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    generate_password_reset_token(email=email)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Password reset email delivery is not yet configured.",
    )


@router.post("/reset-password/", response_model=Msg, operation_id="resetPassword")
async def reset_password(
    session: Annotated[AsyncSession, Depends(get_session)],
    token: Annotated[str, Body(...)],
    new_password: Annotated[str, Body(...)],
) -> Msg:
    email = verify_password_reset_token(token)
    if email is None:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = await crud_user.get_by_email(session, email=email)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if not crud_user.is_active(user):
        raise HTTPException(status_code=400, detail="Inactive user")
    await crud_user.update_password(session, user=user, new_password=new_password)
    return Msg(msg="Password updated successfully")
