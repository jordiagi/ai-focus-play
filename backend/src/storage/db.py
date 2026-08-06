from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


_MIGRATION_PATTERN = re.compile(r"^(\d+)(?:[_-].*)?\.sql$")


def create_connection(path: Path) -> sqlite3.Connection:
    """Open one consistently configured application database connection."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


class Database:
    def __init__(
        self,
        path: Path,
        *,
        schema_path: Path | None = None,
        migrations_dir: Path | None = None,
    ) -> None:
        self.path = Path(path)
        storage_dir = Path(__file__).parent
        self.schema_path = schema_path or storage_dir / "schema.sql"
        self.migrations_dir = migrations_dir or storage_dir / "migrations"
        self.migrate()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = create_connection(self.path)
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        connection = create_connection(self.path)
        try:
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        with self.connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            applied = {
                row["version"]
                for row in connection.execute("SELECT version FROM schema_migrations")
            }
            if 1 not in applied:
                connection.executescript(self.schema_path.read_text())
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (1)"
                )
                applied.add(1)

            if not self.migrations_dir.exists():
                return
            migrations: list[tuple[int, Path]] = []
            for path in self.migrations_dir.glob("*.sql"):
                match = _MIGRATION_PATTERN.match(path.name)
                if match:
                    migrations.append((int(match.group(1)), path))
            for version, path in sorted(migrations):
                if version <= 1 or version in applied:
                    continue
                connection.executescript(path.read_text())
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (?)", (version,)
                )
                applied.add(version)
