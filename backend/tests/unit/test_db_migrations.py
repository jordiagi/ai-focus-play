import sqlite3

import pytest
from sqlalchemy import create_engine, text

import backend.src.storage.database as dbmod
from backend.src.storage.database import Base


def _build_legacy_db(db_path):
    """Create a database the way an old version of the app would have left it:
    all tables present, but the radar index missing (it only ever gets created
    when the table is first created)."""
    legacy = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=legacy)
    with legacy.begin() as conn:
        conn.execute(text("DROP INDEX ix_radar_match_time"))
    legacy.dispose()


@pytest.fixture
def legacy_engine(monkeypatch, tmp_path):
    db_path = tmp_path / "legacy.db"
    _build_legacy_db(str(db_path))
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    monkeypatch.setattr(dbmod, "engine", engine)
    yield engine
    engine.dispose()


def _index_names(db_path, table, conn=None):
    close = False
    if conn is None:
        conn = sqlite3.connect(str(db_path))
        close = True
    try:
        rows = conn.execute(
            f"PRAGMA index_list({table})"
        ).fetchall()
        return {row[1] for row in rows}
    finally:
        if close:
            conn.close()


def test_init_db_creates_missing_declared_index(legacy_engine):
    db_path = legacy_engine.url.database
    names_before = _index_names(db_path, "radar_frames")
    assert "ix_radar_match_time" not in names_before

    dbmod.init_db()

    names_after = _index_names(db_path, "radar_frames")
    assert "ix_radar_match_time" in names_after

    c = sqlite3.connect(str(db_path))
    plan = " ".join(
        str(x)
        for row in c.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM radar_frames WHERE match_id=? "
            "AND timestamp BETWEEN ? AND ? ORDER BY timestamp",
            ("m1", 0, 10),
        )
        for x in row
    )
    c.close()
    assert "ix_radar_match_time" in plan
    assert "USE TEMP B-TREE" not in plan


def test_init_db_reconciles_every_declared_index(legacy_engine):
    db_path = legacy_engine.url.database
    with legacy_engine.begin() as conn:
        conn.execute(text("DROP INDEX ix_events_match_id"))
    assert "ix_events_match_id" not in _index_names(db_path, "events")

    dbmod.init_db()

    assert "ix_events_match_id" in _index_names(db_path, "events")
    assert "ix_radar_match_time" in _index_names(db_path, "radar_frames")


def test_init_db_is_idempotent(legacy_engine):
    db_path = legacy_engine.url.database
    dbmod.init_db()
    dbmod.init_db()  # second run must not error
    assert "ix_radar_match_time" in _index_names(db_path, "radar_frames")
