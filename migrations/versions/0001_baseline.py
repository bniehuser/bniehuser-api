"""baseline

Revision ID: 0001
Revises:
Create Date: 2026-06-10

"""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_username", "user", ["username"])
    op.create_index("ix_user_email", "user", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_user_email", "user")
    op.drop_index("ix_user_username", "user")
    op.drop_table("user")
