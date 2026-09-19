"""Regression tests for WP-5 (defects 5 and 7).

These spawn a real subprocess against a fresh, isolated database -- config.py reads
AIFP_DATA_DIR/AIFP_DB_PATH at import time, so mutating env vars inside an
already-running pytest process (which may have already imported
backend.src.storage.repository via another test module) would prove nothing.
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from backend.src.services.pipeline.cv_engine import SoccerCVEngine
from backend.src.domain.models.match import RadarFrame, RadarPlayer, RadarBall, Event

REPO = Path(__file__).resolve().parents[3]
_VENV_PY = REPO / "backend" / ".venv" / "bin" / "python"
PYTHON = str(_VENV_PY) if _VENV_PY.exists() else sys.executable


def test_analytics_matches_emitted_events():
    """Pre-existing coverage of SoccerCVEngine._calculate_analytics itself (not the
    seed) -- unaffected by the WP-5 seed fix below, kept alongside it."""
    engine = SoccerCVEngine()

    events = [
        Event(match_id="test", timestamp=10.0, period=1, event_type="Kickoff", team="home", description="Kickoff", pitch_x=52.5, pitch_y=34.0),
        Event(match_id="test", timestamp=20.0, period=1, event_type="Goal", team="home", description="Goal 1", pitch_x=98.0, pitch_y=32.0),
        Event(match_id="test", timestamp=35.0, period=1, event_type="Shot", team="home", description="Shot 1", pitch_x=88.0, pitch_y=30.0),
        Event(match_id="test", timestamp=50.0, period=2, event_type="Goal", team="away", description="Goal 2", pitch_x=12.0, pitch_y=34.0),
        Event(match_id="test", timestamp=65.0, period=2, event_type="Shot", team="away", description="Shot 2", pitch_x=15.0, pitch_y=28.0),
    ]

    radar_frames = []
    for t in range(0, 80, 5):
        radar_frames.append(RadarFrame(
            timestamp=float(t),
            players=[
                RadarPlayer(id=1, team="home", x=50.0, y=30.0, speed=2.0),
                RadarPlayer(id=2, team="away", x=55.0, y=30.0, speed=2.0),
            ],
            ball=RadarBall(x=50.5, y=30.0, z=0.0, detected=True)
        ))

    home_positions = [(50.0, 30.0)] * 10
    away_positions = [(55.0, 30.0)] * 10

    analytics = engine._calculate_analytics(radar_frames, events, home_positions, away_positions, sample_fps=0.2)

    assert analytics.home_stats.goals == 1
    assert analytics.away_stats.goals == 1

    assert analytics.home_stats.shots == 2
    assert analytics.away_stats.shots == 2

    assert len(analytics.shot_map) == 4
    for shot in analytics.shot_map:
        assert shot.timestamp <= 80.0

    assert analytics.home_stats.tackles is None
    assert analytics.home_stats.passes_completed is None
    assert analytics.home_stats.fouls is None


def _seed_fresh_db(tmpdir: str) -> str:
    db_path = os.path.join(tmpdir, "v.db")
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO),
        "AIFP_DATA_DIR": tmpdir,
        "AIFP_DB_PATH": db_path,
        "AIFP_MEDIA_DIR": os.path.join(tmpdir, "media"),
    }
    result = subprocess.run(
        [PYTHON, "-c", "from backend.src.storage.repository import match_repo"],
        cwd=str(REPO), env=env, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, f"seeding a fresh db failed: {result.stderr}"
    return db_path


def test_seed_analytics_matches_seeded_events():
    """The demo seed's analytics must be derived from its own seeded events, not
    fabricated literals -- see MatchRepository._seed_if_empty."""
    tmpdir = tempfile.mkdtemp()
    try:
        db_path = _seed_fresh_db(tmpdir)
        conn = sqlite3.connect(db_path)
        goals, shots_or_goals = {}, {}
        for team, etype in conn.execute("SELECT team, event_type FROM events"):
            if etype.lower() in ("shot", "goal"):
                shots_or_goals[team] = shots_or_goals.get(team, 0) + 1
            if etype.lower() == "goal":
                goals[team] = goals.get(team, 0) + 1
        row = conn.execute("SELECT data FROM analytics LIMIT 1").fetchone()
        conn.close()

        assert row is not None, "no analytics row was seeded"
        data = json.loads(row[0])
        home_stats, away_stats = data["home_stats"], data["away_stats"]

        # Goals and shots must equal what the seeded events actually contain.
        assert home_stats["goals"] == goals.get("home", 0)
        assert away_stats["goals"] == goals.get("away", 0)
        assert home_stats["shots"] == shots_or_goals.get("home", 0)
        assert away_stats["shots"] == shots_or_goals.get("away", 0)

        # Quantities no part of this codebase ever actually computes must be
        # None, not a plausible-looking invented number.
        for stats in (home_stats, away_stats):
            for field in ("tackles", "passes_completed", "attempts", "corners",
                          "free_kicks", "throw_ins", "fouls", "penalties", "possession_won"):
                assert stats[field] is None, f"{field} is fabricated (never computed)"

        # The shot map must reflect exactly the seeded events with a known
        # outcome (goals) -- not an unrelated, larger, invented count.
        shot_map = data["shot_map"]
        assert len(shot_map) == sum(goals.values())
        for shot in shot_map:
            assert shot["outcome"] == "goal"

        # No pass-sequencing detection exists; the series must be empty, not a
        # fabricated decreasing-looking literal.
        assert data["pass_strings"] == {"home": [], "away": []}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_stale_running_job_is_reclaimed_on_startup():
    """jobs.status documents an 'interrupted' state that nothing used to set. A
    job left 'running' by a process that died must be reclaimed the next time the
    repository starts up -- see MatchRepository._recover_interrupted_jobs."""
    tmpdir = tempfile.mkdtemp()
    try:
        db_path = _seed_fresh_db(tmpdir)

        conn = sqlite3.connect(db_path)
        match_id = conn.execute("SELECT id FROM matches LIMIT 1").fetchone()[0]
        conn.execute(
            "INSERT INTO jobs (id, match_id, kind, status, progress, step, started_at, attempts) "
            "VALUES (?,?,?,?,?,?,?,?)",
            ("stale-job", match_id, "cv_analysis", "running", 0.0, "Initializing analysis...", 0.0, 0),
        )
        conn.commit()
        conn.close()

        env = {
            **os.environ,
            "PYTHONPATH": str(REPO),
            "AIFP_DATA_DIR": tmpdir,
            "AIFP_DB_PATH": db_path,
            "AIFP_MEDIA_DIR": os.path.join(tmpdir, "media"),
        }
        result = subprocess.run(
            [PYTHON, "-c", "from backend.src.storage.repository import match_repo"],
            cwd=str(REPO), env=env, capture_output=True, text=True, timeout=180,
        )
        assert result.returncode == 0, f"repository failed to start: {result.stderr}"

        conn = sqlite3.connect(db_path)
        status, error = conn.execute(
            "SELECT status, error FROM jobs WHERE id='stale-job'"
        ).fetchone()
        conn.close()

        assert status == "interrupted"
        assert error
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_seed_contains_no_invented_player_names():
    """Assert no fabricated player names exist in the seeded roster, highlights,
    or events (U-2 contract: jersey numbers only, never invented names)."""
    tmpdir = tempfile.mkdtemp()
    try:
        db_path = _seed_fresh_db(tmpdir)
        conn = sqlite3.connect(db_path)

        # Roster: verify no fabricated names and conforms to Veo convention (Player <jersey> or Player )
        roster = conn.execute("SELECT jersey, name, position FROM lineup_players").fetchall()
        assert len(roster) > 0, "No players seeded in roster"
        forbidden = ["Eric Jordi", "Diego Morales", "Julian Vance", "Alex Reed", "Carlos Mendez"]
        for jersey, name, pos in roster:
            for bad in forbidden:
                assert bad.lower() not in name.lower(), f"Invented name '{bad}' in roster: {name}"
            expected = f"Player {jersey}" if jersey else "Player "
            assert name == expected, f"Roster name must be '{expected}', got '{name}'"

        # Highlights: verify player_name is not populated with fiction and title has no invented names
        highlights = conn.execute("SELECT title, player_name FROM highlights").fetchall()
        assert len(highlights) > 0, "No highlights seeded"
        for title, pname in highlights:
            assert pname is None or pname == "", f"Highlight player_name must not be populated with fiction: {pname}"
            for bad in forbidden:
                assert bad.lower() not in title.lower(), f"Invented name '{bad}' in highlight title: {title}"

        # Events: verify player_name is None and description has no invented names
        events = conn.execute("SELECT description, player_name FROM events").fetchall()
        assert len(events) > 0, "No events seeded"
        for desc, pname in events:
            assert pname is None or pname == "", f"Event player_name must not be populated with fiction: {pname}"
            for bad in forbidden:
                assert bad.lower() not in desc.lower(), f"Invented name '{bad}' in event description: {desc}"

        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

