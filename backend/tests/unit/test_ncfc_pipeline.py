"""Unit tests for NCFC match assets, Veo ground-truth parity, and MatchPipeline execution."""

import json
from pathlib import Path
import pytest

from backend.src.domain.models.match import Match
from backend.src.services.pipeline.ncfc_seeder import seed_ncfc_match
from backend.src.services.pipeline.physics_shot_detector import PhysicsShotDetector
from backend.src.services.pipeline.pipeline_runner import MatchPipeline
from backend.src.services.pipeline.stats_benchmark import load_live_veo_benchmark, compare_stats_table
from backend.src.services.pipeline.veo_calibrator import VeoCameraModel
from backend.src.storage.repository import MatchRepository

REPO = Path(__file__).resolve().parents[3]
NCFC_CALIB_PATH = REPO / "benchmarks" / "raw" / "ncfc_camera_alignment.veo"
NCFC_STATS_PATH = REPO / "benchmarks" / "raw" / "ncfc_stats.json"
NCFC_VIDEO_PATH = REPO / "backend" / ".local" / "media" / "ncfc_full.mp4"


def test_ncfc_assets_exist():
    """Verify raw calibration, live stats, and video assets exist."""
    assert NCFC_CALIB_PATH.exists(), f"Missing calibration file at {NCFC_CALIB_PATH}"
    assert NCFC_STATS_PATH.exists(), f"Missing stats file at {NCFC_STATS_PATH}"
    assert NCFC_VIDEO_PATH.exists(), f"Missing video link at {NCFC_VIDEO_PATH}"
    assert NCFC_VIDEO_PATH.stat().st_size > 1_000_000_000, "Full match video should be > 1GB"


def test_ncfc_camera_calibration():
    """Verify VeoCameraModel parses the NCFC .veo alignment accurately."""
    model = VeoCameraModel.from_veo_file(str(NCFC_CALIB_PATH))

    # Camera height should be around 4.9m (standard high pole setup)
    assert 3.5 <= model.camera_height <= 6.5
    assert abs(model.camera_height - 4.94) < 0.2

    # Pitch dimensions from camera alignment
    assert model.field_length == 105.0
    assert 65.0 <= model.field_width <= 70.0


def test_ncfc_stats_table_mathematical_consistency():
    """Verify mathematical consistency of NCFC Veo stats table."""
    data = json.loads(NCFC_STATS_PATH.read_text())
    stats = data["stats_table"]["rows"]

    # Check attempt arithmetic
    assert stats["total_attempts"]["own"] == stats["goal"]["own"] + stats["shot"]["own"]
    assert stats["total_attempts"]["opponent"] == stats["goal"]["opponent"] + stats["shot"]["opponent"]
    assert stats["total_attempts"]["own"] == 3
    assert stats["total_attempts"]["opponent"] == 15

    # Check possession percentages sum to 100
    assert stats["possession_percent"]["own"] + stats["possession_percent"]["opponent"] == 100
    assert stats["possession_percent"]["own"] == 56
    assert stats["possession_percent"]["opponent"] == 44

    # Check score consistency
    assert stats["goal"]["own"] == data["match"]["final_result"]["own"]
    assert stats["goal"]["opponent"] == data["match"]["final_result"]["opponent"]
    assert stats["goal"]["own"] == 1
    assert stats["goal"]["opponent"] == 3


def test_ncfc_seeder_and_repository():
    """Verify seed_ncfc_match properly registers match, lineup, highlights, and analytics."""
    repo = MatchRepository()
    media_dir = REPO / "backend" / ".local" / "media"
    match = seed_ncfc_match(repo, media_dir)

    assert match.id == "ncfc-20260926"
    assert match.home_score == 1
    assert match.away_score == 3
    assert match.duration_seconds == 6440.0

    # Lineup checks
    lineup = repo.get_lineup("ncfc-20260926")
    assert len(lineup) >= 21
    jerseys = [p.jersey for p in lineup]
    assert "8" in jerseys   # Eric Yeh-Fuentes
    assert "7" in jerseys   # Anthony Ventura-Garcia (Captain)
    captain = next(p for p in lineup if p.jersey == "7")
    assert captain.is_captain is True

    # Highlights
    highlights = repo.get_highlights("ncfc-20260926")
    assert len(highlights) == 22

    # Events
    events = repo.get_events("ncfc-20260926")
    assert len(events) >= 6
    event_types = [e.event_type for e in events]
    assert "Kickoff" in event_types
    assert "Goal" in event_types

    # Analytics
    analytics = repo.get_analytics("ncfc-20260926")
    assert analytics is not None
    assert analytics.home_stats.goals == 1
    assert analytics.away_stats.goals == 3
    assert analytics.home_stats.possession_percent == 56.0
    assert analytics.away_stats.possession_percent == 44.0


def test_ncfc_benchmark_comparison():
    """Verify live benchmark comparison utility against NCFC ground truth."""
    gt = load_live_veo_benchmark("ncfc-20260926")
    assert gt["match"]["title"] == "Arlington SA U16B ECNL (26-27) vs. NCFC"

    pred_home = {"goals": 1, "shots": 2, "possession_percent": 56.0}
    pred_away = {"goals": 3, "shots": 12, "possession_percent": 44.0}
    comp = compare_stats_table(pred_home, pred_away, unavailable={}, gt_benchmark=gt)

    assert comp["metrics"]["goal"]["exact_match"] is True
    assert comp["metrics"]["shot"]["exact_match"] is True
    assert comp["metrics"]["possession_percent"]["exact_match"] is True
