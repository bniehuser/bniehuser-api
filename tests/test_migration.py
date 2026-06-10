from sqlalchemy import inspect


async def test_user_table_has_expected_columns():
    from app.db import engine

    async with engine.connect() as conn:
        cols = await conn.run_sync(
            lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("user")}
        )

    assert cols == {
        "id",
        "username",
        "email",
        "hashed_password",
        "is_active",
        "is_superuser",
        "created_at",
        "updated_at",
        "last_login",
    }
