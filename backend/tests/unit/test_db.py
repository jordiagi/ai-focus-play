from __future__ import annotations

import sqlite3
from pathlib import Path

from src.storage.db import Database


EXPECTED_TABLES = {
    "schema_migrations",
    "projects",
    "source_videos",
    "pipeline_jobs",
    "tracklets",
    "detections",
    "tracklet_crops",
    "tracklet_embeddings",
    "identity_clusters",
    "jersey_votes",
    "user_clicks",
    "appearance_segments",
    "reel_outputs",
}

EXPECTED_INDEXES = {
    "idx_jobs_project",
    "idx_tracklets_source",
    "idx_tracklets_cluster",
    "idx_detections_source_ts",
    "idx_detections_tracklet",
    "idx_crops_tracklet",
    "idx_votes_tracklet",
    "idx_clicks_project",
    "idx_segments_project",
}


def test_database_enables_wal_foreign_keys_and_named_rows(tmp_path: Path) -> None:
    database = Database(tmp_path / "app.db")

    with database.connect() as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        row = connection.execute("SELECT 42 AS answer").fetchone()

    assert isinstance(row, sqlite3.Row)
    assert row["answer"] == 42


def test_initial_migration_creates_all_tables_and_indexes(tmp_path: Path) -> None:
    database = Database(tmp_path / "app.db")

    with database.connect() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        indexes = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        versions = [
            row["version"]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        ]

    assert EXPECTED_TABLES <= tables
    assert EXPECTED_INDEXES <= indexes
    assert versions == [1]


def test_migrations_are_idempotent_and_numbered_files_apply_once(tmp_path: Path) -> None:
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "002_add_probe_note.sql").write_text(
        "ALTER TABLE source_videos ADD COLUMN probe_note TEXT;"
    )
    database = Database(tmp_path / "app.db", migrations_dir=migrations_dir)

    database.migrate()
    database.migrate()

    with database.connect() as connection:
        versions = [
            row["version"]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        ]
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(source_videos)")
        }

    assert versions == [1, 2]
    assert "probe_note" in columns
