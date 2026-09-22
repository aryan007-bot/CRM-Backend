"""unique_user_email

Login resolves a user by email alone (no organization selector), so two users in
different organizations sharing an email made authentication ambiguous and could
authenticate a user into the wrong organization. Replace the per-organization
uniqueness constraint with a global unique index on users.email.

Revision ID: b41c9a7f2e10
Revises: d9ff7e3d8d6c
Create Date: 2026-09-22 15:05:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b41c9a7f2e10"
down_revision: Union[str, Sequence[str], None] = "d9ff7e3d8d6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_legacy_constraint() -> None:
    """Drop `uq_user_org_email` on any backend.

    PostgreSQL can alter constraints in place; SQLite cannot, so there the
    constraint is dropped by rebuilding the table (Alembic batch mode). Batch
    mode needs a live connection, which is why the offline SQL path keeps the
    plain ALTER statement.
    """
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_constraint("uq_user_org_email", type_="unique")
    else:
        op.drop_constraint("uq_user_org_email", "users", type_="unique")


def upgrade() -> None:
    """Enforce globally unique user emails."""
    _drop_legacy_constraint()
    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    """Restore per-organization email uniqueness."""
    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("users") as batch_op:
            batch_op.create_unique_constraint(
                "uq_user_org_email", ["organization_id", "email"]
            )
    else:
        op.create_unique_constraint("uq_user_org_email", "users", ["organization_id", "email"])
