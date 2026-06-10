import os
from collections.abc import AsyncGenerator

import pytest

# Ryuk (testcontainers' reaper) can fail to bind a port on Docker Desktop
# for Mac — set BEFORE importing testcontainers so it picks up the flag.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

from testcontainers.postgres import PostgresContainer  # noqa: E402

_pg: PostgresContainer | None = None


def pytest_configure(config: pytest.Config) -> None:
    global _pg
    container = PostgresContainer("postgres:16-alpine", driver="psycopg")
    container.start()
    os.environ["PGHOST"] = container.get_container_host_ip()
    os.environ["PGPORT"] = str(container.get_exposed_port(5432))
    os.environ["PGUSER"] = container.username
    os.environ["PGPASSWORD"] = container.password
    os.environ["PGDATABASE"] = container.dbname
    _pg = container


def pytest_unconfigure(config: pytest.Config) -> None:
    global _pg
    if _pg is not None:
        _pg.stop()
        _pg = None


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")


@pytest.fixture
async def session() -> AsyncGenerator:
    from app.db import async_session

    async with async_session() as s:
        yield s


@pytest.fixture(autouse=True)
async def _open_client_pool() -> AsyncGenerator[None, None]:
    from app.clients import pool

    await pool.open_all()
    yield
    await pool.close_all()
