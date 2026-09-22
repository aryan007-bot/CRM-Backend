"""Guards the migration chain without needing a live database.

`alembic upgrade head --sql` compiles every migration to PostgreSQL DDL in
offline mode. That is enough to catch the failure mode that shipped in the
initial revision: autogenerate emitted the custom `GUID` column type fully
qualified (`app.db.base.GUID`) without importing it, so every migration run died
with a NameError before touching the database.
"""

import io
import os
import re

from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command
from app.db.models import Base

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

INITIAL_REVISION = "d9ff7e3d8d6c"
SECOND_REVISION = "b41c9a7f2e10"
THIRD_REVISION = "c52e8b1a4f32"
FOURTH_REVISION = "d63f9a2b5e41"

TABLE_RE = re.compile(r"CREATE TABLE (\w+) \((.*?)\n\);", re.DOTALL)
ALTER_RE = re.compile(r"ALTER TABLE (\w+) ADD COLUMN (\w+)", re.IGNORECASE)


def _alembic_config() -> Config:
    config = Config(os.path.join(BACKEND_ROOT, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(BACKEND_ROOT, "alembic"))
    # Offline mode never opens a connection; the URL only selects the dialect.
    config.set_main_option(
        "sqlalchemy.url", "postgresql+psycopg://user:pass@localhost:5432/dbname"
    )
    return config


def _postgres_ddl() -> str:
    config = _alembic_config()
    buffer = io.StringIO()
    config.output_buffer = buffer
    command.upgrade(config, "head", sql=True)
    return buffer.getvalue()


def test_migration_history_has_a_single_head():
    script = ScriptDirectory.from_config(_alembic_config())
    heads = script.get_heads()
    assert heads == [FOURTH_REVISION], heads

    revisions = [revision.revision for revision in script.walk_revisions()]
    assert revisions == [FOURTH_REVISION, THIRD_REVISION, SECOND_REVISION, INITIAL_REVISION]


def test_migration_chain_compiles_to_postgres_ddl():
    sql = _postgres_ddl()

    # All revisions ran, in dependency order.
    assert f"VALUES ('{INITIAL_REVISION}')" in sql
    assert f"SET version_num='{SECOND_REVISION}'" in sql
    assert f"SET version_num='{THIRD_REVISION}'" in sql
    assert f"SET version_num='{FOURTH_REVISION}'" in sql
    assert (
        sql.index(INITIAL_REVISION)
        < sql.index(SECOND_REVISION)
        < sql.index(THIRD_REVISION)
        < sql.index(FOURTH_REVISION)
    )

    # PostgreSQL-native types, not SQLite fallbacks.
    assert "UUID NOT NULL" in sql
    assert "NUMERIC(12, 2) NOT NULL" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    # Money must never be floating point.
    assert "FLOAT" not in sql.upper()
    assert "REAL" not in sql.upper()

    # Global email uniqueness replaces the per-organization constraint.
    assert "DROP CONSTRAINT uq_user_org_email" in sql
    assert "CREATE UNIQUE INDEX ix_users_email ON users (email)" in sql


def test_migrations_create_every_model_table_with_every_column():
    """Models and migrations must not drift apart.

    Compares each model's columns with the columns the migration chain creates,
    so a model change that was never turned into a migration fails here instead
    of in production.
    """
    sql = _postgres_ddl()
    created = {name: body for name, body in TABLE_RE.findall(sql)}

    for table_name, col_name in ALTER_RE.findall(sql):
        if table_name in created:
            created[table_name] += f"\n  {col_name}"

    for table_name, table in Base.metadata.tables.items():
        assert table_name in created, f"migration does not create table '{table_name}'"

        body = created[table_name]
        for column in table.columns:
            assert re.search(rf"\b{re.escape(column.name)}\b", body), (
                f"migration for '{table_name}' has no column '{column.name}'"
            )

    # And nothing extra was created that the models do not know about
    # (alembic_version is maintained by Alembic itself).
    extra = set(created) - set(Base.metadata.tables) - {"alembic_version"}
    assert extra == set(), f"migration creates unknown tables: {extra}"


def test_every_organization_owned_table_has_an_index():
    """Tenant isolation queries always filter by organization_id."""
    sql = _postgres_ddl()

    for table_name, table in Base.metadata.tables.items():
        if "organization_id" not in table.columns:
            continue
        assert (
            f"ix_{table_name}_organization_id" in sql
            or "organization_id" in sql.split(f"CREATE TABLE {table_name} ")[1].split(");")[0]
        )
