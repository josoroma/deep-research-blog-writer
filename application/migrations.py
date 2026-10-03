"""Versioned SQL migrations for the server database.

Migrations are ordered, checksummed and applied exactly once, recorded in a
``schema_migrations`` table. The queue schema is plain SQL so it can be reviewed
and applied with ``psql`` if needed; an ORM is deliberately not a prerequisite.

The SQL lives in ``ops/api/migrations/`` for operators. When the project runs
from an installed wheel that directory is not present, so the build copies the
same files next to this module and :func:`discover` falls back to them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import psycopg

from schemas.config import ApiSettings
from schemas.errors import UnavailableError
from services.checkpoints import prepare_postgres_checkpointer
from services.postgres_jobs import CONNECT_TIMEOUT_SECONDS

_REPO_MIGRATIONS = Path(__file__).resolve().parents[1] / "ops" / "api" / "migrations"
_PACKAGED_MIGRATIONS = Path(__file__).resolve().parent / "_migrations"
TRACKING_TABLE = "schema_migrations"


def migrations_dir() -> Path:
    """The migration directory available to this installation."""
    if _REPO_MIGRATIONS.is_dir():
        return _REPO_MIGRATIONS
    return _PACKAGED_MIGRATIONS


MIGRATIONS_DIR = migrations_dir()


class MigrationError(UnavailableError):
    """A migration failed, drifted, or could not be recorded."""

    code = "migration_failed"


@dataclass(frozen=True)
class Migration:
    """One SQL file: its numeric version, location, text, and content hash."""

    version: str
    path: Path
    sql: str
    checksum: str


def discover(directory: Path | None = None) -> list[Migration]:
    """Load migrations in version order.

    Raises:
        MigrationError: When the directory is missing, a file has no numeric
            version prefix, or two files share a version.
    """
    root = directory if directory is not None else migrations_dir()
    if not root.is_dir():
        raise MigrationError(f"Migration directory does not exist: {root}")
    migrations: list[Migration] = []
    versions: set[str] = set()
    for path in sorted(root.glob("*.sql")):
        version = path.stem.split("_", 1)[0]
        if not version.isdigit():
            raise MigrationError(f"Migration file has no numeric version: {path.name}")
        if version in versions:
            raise MigrationError(f"Duplicate migration version: {version}")
        versions.add(version)
        text = path.read_text(encoding="utf-8")
        migrations.append(
            Migration(
                version=version,
                path=path,
                sql=text,
                checksum=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
        )
    return migrations


def ensure_tracking(connection: object) -> None:
    """Create the migration tracking table if it does not exist yet."""
    cursor = connection.cursor()  # type: ignore[attr-defined]
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TRACKING_TABLE} (
            version TEXT PRIMARY KEY,
            checksum TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def _split_statements(sql: str) -> list[str]:
    """Split a migration file into individual statements.

    psycopg's extended protocol rejects multiple statements in one ``execute``, so
    each statement is sent separately, in file order. Line comments are removed
    first so a semicolon inside a comment cannot split a statement.
    """
    without_comments = "\n".join(line.split("--", 1)[0] for line in sql.splitlines())
    return [statement.strip() for statement in without_comments.split(";") if statement.strip()]


def applied_versions(connection: object) -> dict[str, str]:
    """Return ``{version: checksum}`` for every migration already applied."""
    ensure_tracking(connection)
    cursor = connection.cursor()  # type: ignore[attr-defined]
    cursor.execute(f"SELECT version, checksum FROM {TRACKING_TABLE}")  # noqa: S608 - constant
    return {row[0]: row[1] for row in cursor.fetchall()}


def apply_migrations(connection: object, *, directory: Path | None = None) -> list[str]:
    """Apply pending migrations in one transaction each; return applied versions.

    A recorded migration whose checksum no longer matches fails loudly: editing an
    applied file is drift, not an upgrade.
    """
    migrations = discover(directory)
    already = applied_versions(connection)
    for migration in migrations:
        if migration.version in already and already[migration.version] != migration.checksum:
            raise MigrationError(f"Migration {migration.version} changed after it was applied")
    applied: list[str] = []
    for migration in migrations:
        if migration.version in already:
            continue
        cursor = connection.cursor()  # type: ignore[attr-defined]
        try:
            for statement in _split_statements(migration.sql):
                cursor.execute(statement)
            cursor.execute(
                f"INSERT INTO {TRACKING_TABLE} (version, checksum) VALUES (%s, %s)",  # noqa: S608
                (migration.version, migration.checksum),
            )
            connection.commit()  # type: ignore[attr-defined]
        except Exception as error:
            # Any driver error must roll back before it is re-raised as drift-safe.
            connection.rollback()  # type: ignore[attr-defined]
            raise MigrationError(f"Migration {migration.version} failed: {error}") from error
        applied.append(migration.version)
    return applied


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - operator entry point
    """Apply pending SQL migrations and the LangGraph checkpoint schema."""
    parser = argparse.ArgumentParser(prog="application.migrations", description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print applied versions as JSON.")
    args = parser.parse_args(argv)

    api = ApiSettings()
    if api.uses_memory_store():
        print("Fixture profile with no API_DATABASE uses memory; no migrations are needed.")
        return 0
    dsn = api.database_dsn()
    if dsn is None:
        print("API_DATABASE is required unless API_RUN_PROFILE=fixture")
        return 2
    try:
        with psycopg.connect(dsn, connect_timeout=CONNECT_TIMEOUT_SECONDS) as connection:
            applied = apply_migrations(connection)
    except psycopg.OperationalError:
        # The DSN can carry a password, so only the fix is printed.
        print("PostgreSQL is unreachable at API_DATABASE; start it with `make api-up`")
        return 2
    prepare_postgres_checkpointer(dsn)
    if args.json:
        print(json.dumps({"applied": applied}))
    else:
        print(f"Applied {len(applied)} migration(s); checkpoint schema is ready.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
