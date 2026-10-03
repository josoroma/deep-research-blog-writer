"""Versioned SQL migrations for the server database.

Migrations are ordered, checksummed and applied exactly once, recorded in a
``schema_migrations`` table. The queue schema is plain SQL so it can be reviewed
and applied with ``psql`` if needed; an ORM is deliberately not a prerequisite.

The SQL lives in ``ops/api/migrations/`` for operators. When the project runs
from an installed wheel that directory is not present, so the build copies the
same files next to this module and :func:`discover` falls back to them.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

_REPO_MIGRATIONS = Path(__file__).resolve().parents[1] / "ops" / "api" / "migrations"
_PACKAGED_MIGRATIONS = Path(__file__).resolve().parent / "_migrations"
TRACKING_TABLE = "schema_migrations"


def migrations_dir() -> Path:
    """The migration directory available to this installation."""
    if _REPO_MIGRATIONS.is_dir():
        return _REPO_MIGRATIONS
    return _PACKAGED_MIGRATIONS


MIGRATIONS_DIR = migrations_dir()


class MigrationError(RuntimeError):
    """A migration failed, drifted, or could not be recorded."""


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path
    sql: str
    checksum: str


def discover(directory: Path | None = None) -> list[Migration]:
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
    ensure_tracking(connection)
    cursor = connection.cursor()  # type: ignore[attr-defined]
    cursor.execute(f"SELECT version, checksum FROM {TRACKING_TABLE}")
    return {row[0]: row[1] for row in cursor.fetchall()}


def apply_migrations(connection: object, *, directory: Path | None = None) -> list[str]:
    """Apply pending migrations in one transaction each; return applied versions.

    A recorded migration whose checksum no longer matches fails loudly: editing an
    applied file is drift, not an upgrade.
    """
    migrations = discover(directory)
    already = applied_versions(connection)
    for migration in migrations:
        if migration.version in already:
            if already[migration.version] != migration.checksum:
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
                f"INSERT INTO {TRACKING_TABLE} (version, checksum) VALUES (%s, %s)",
                (migration.version, migration.checksum),
            )
            connection.commit()  # type: ignore[attr-defined]
        except Exception as error:  # noqa: BLE001
            connection.rollback()  # type: ignore[attr-defined]
            raise MigrationError(f"Migration {migration.version} failed: {error}") from error
        applied.append(migration.version)
    return applied


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - operator entry point
    """Apply pending SQL migrations and the LangGraph checkpoint schema."""
    import argparse

    import psycopg

    from schemas.config import ApiSettings
    from services.checkpoints import prepare_postgres_checkpointer

    parser = argparse.ArgumentParser(prog="application.migrations", description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print applied versions as JSON.")
    args = parser.parse_args(argv)

    api = ApiSettings()
    if api.run_profile == "fixture":
        print("Fixture profile uses an in-memory store; no migrations are needed.")
        return 0
    dsn = api.database_dsn()
    if dsn is None:
        print("API_DATABASE is required unless API_RUN_PROFILE=fixture")
        return 2
    with psycopg.connect(dsn) as connection:
        applied = apply_migrations(connection)
    prepare_postgres_checkpointer(dsn)
    if args.json:
        import json

        print(json.dumps({"applied": applied}))
    else:
        print(f"Applied {len(applied)} migration(s); checkpoint schema is ready.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
