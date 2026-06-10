from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from structlog.testing import capture_logs

from app.crud import user as crud_user
from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


async def test_openapi_is_3_0_2(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/openapi.json")
    assert resp.status_code == 200
    doc = resp.json()
    assert doc["openapi"].startswith("3.0")
    for path in doc["paths"]:
        assert path.startswith("/api/v1/"), f"route {path} missing prefix"


async def test_auth_login_success(client: AsyncClient, session) -> None:
    email = f"login-{uuid4().hex[:8]}@example.com"
    await crud_user.create(session, email=email, username="u", password="pw123")
    resp = await client.post(
        "/api/v1/login/access-token",
        data={"username": email, "password": "pw123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_auth_login_wrong_password(client: AsyncClient, session) -> None:
    email = f"login-fail-{uuid4().hex[:8]}@example.com"
    await crud_user.create(session, email=email, username="u", password="correct")
    resp = await client.post(
        "/api/v1/login/access-token",
        data={"username": email, "password": "wrong"},
    )
    assert resp.status_code == 400


async def test_users_me_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401


async def test_users_me_with_token(client: AsyncClient, session) -> None:
    email = f"me-{uuid4().hex[:8]}@example.com"
    await crud_user.create(session, email=email, username="meuser", password="pw")
    login = await client.post(
        "/api/v1/login/access-token",
        data={"username": email, "password": "pw"},
    )
    token = login.json()["access_token"]
    resp = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == email
    assert body["username"] == "meuser"


async def test_password_recovery_returns_501(client: AsyncClient, session) -> None:
    email = f"recover-{uuid4().hex[:8]}@example.com"
    await crud_user.create(session, email=email, username="u", password="pw")
    resp = await client.post(f"/api/v1/password-recovery/{email}")
    assert resp.status_code == 501


async def test_request_logging_emits_structured_line(client: AsyncClient) -> None:
    with capture_logs() as logs:
        await client.get("/api/v1/health")
    request_logs = [e for e in logs if e.get("event") == "request"]
    assert len(request_logs) == 1
    line = request_logs[0]
    assert line["path"] == "/api/v1/health"
    assert line["status"] == 200
    assert "latency_ms" in line
    assert "request_id" in line
