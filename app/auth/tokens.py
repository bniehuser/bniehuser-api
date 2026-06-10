from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def generate_password_reset_token(email: str) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(hours=settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS)
    payload = {"exp": expire, "nbf": now, "sub": email}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_password_reset_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None
