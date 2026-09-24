"""Unit tests for Baltimore Armor match assets, Veo ground-truth parity, and MatchPipeline execution."""

import json
from pathlib import Path
import pytest

from backend.src.domain.models.match import Match
from backend.src.services.pipeline.pipeline_runner import MatchPipeline
from backend.src.services.pipeline.veo_calibrator import VeoCameraModel
from backend.src.services.pipeline.stats_benchmark import load_live_veo_benchmark, compare_stats_table
from backend.src.storage.repository import MatchRepository

REPO = Path(__file__).resolve().parents[3]
BALTIMORE_CALIB_PATH = REPO / "benchmarks" / "raw" / "baltimore_armor_camera_alignment.veo"
BALTIMORE_STATS_PATH = REPO / "benchmarks" / "raw" / "baltimore_armor_stats.json"
BALTIMORE_VIDEO_PATH = REPO / "backend" / ".local" / "media" / "baltimore_armor_sample_30s.mp4"


def test_baltimore_armor_assets_exist():
    """Verify raw calibration, live stats, and video sample assets exist."""
    assert BALTIMORE_CALIB_PATH.exists(), f"Missing calibration file at {BALTIMORE_CALIB_PATH}"
    assert BALTIMORE_STATS_PATH.exists(), f"Missing stats file at {BALTIMORE_STATS_PATH}"
    assert BALTIMORE_VIDEO_PATH.exists(), f"Missing video sample at {BALTIMORE_VIDEO_PATH}"
    assert BALTIMORE_VIDEO_PATH.stat().st_size > 1_000_000, "Sample video should be > 1MB"


def test_baltimore_armor_camera_calibration():
    """Verify VeoCameraModel parses the Baltimore Armor .veo alignment accurately."""
    model = VeoCameraModel.from_veo_file(str(BALTIMORE_CALIB_PATH))

    # Camera height should be around 4.22 meters (standard amateur Veo pole setup)
    assert 3.5 <= model.camera_height <= 6.5
    assert abs(model.camera_height - 4.22) < 0.1

    # Pitch dimensions from camera alignment
    assert model.field_length == 105.0
    assert 65.0 <= model.field_width <= 70.0


def test_baltimore_armor_stats_table_mathematical_consistency():
    """Verify mathematical consistency of Baltimore Armor Veo stats table."""
    data = json.loads(BALTIMORE_STATS_PATH.read_text())
    stats = data["stats_table"]["rows"]

    # Check attempt arithmetic
    assert stats["total_attempts"]["own"] == stats["goal"]["own"] + stats["shot"]["own"]
    assert stats["total_attempts"]["opponent"] == stats["goal"]["opponent"] + stats["shot"]["opponent"]
    assert stats["total_attempts"]["own"] == 17
    assert stats["total_attempts"]["opponent"] == 4

    # Check possession percentages sum to 100
    assert stats["possession_percent"]["own"] + stats["possession_percent"]["opponent"] == 100
    assert stats["possession_percent"]["own"] == 71
    assert stats["possession_percent"]["opponent"] == 29

    # Check score consistency
    assert stats["goal"]["own"] == data["match"]["final_result"]["own"]
    assert stats["goal"]["opponent"] == data["match"]["final_result"]["opponent"]


def test_baltimore_armor_pass_and_possession_locations():
    """Verify pass and possession locations sum to 100% for each team."""
    data = json.loads(BALTIMORE_STATS_PATH.read_text())

    for loc_key in ["pass_location", "possession_location"]:
        loc_data = data[loc_key]
        for side in ["own", "opponent"]:
            d = loc_data[side]
            total = d["defensive_pct"] + d["middle_pct"] + d["attacking_pct"]
            assert abs(total - 100) <= 1, f"{loc_key} for {side} sums to {total}, expected 100"


def test_baltimore_armor_benchmark_loader_and_comparison():
    """Verify load_live_veo_benchmark accurately selects Baltimore benchmark by identifier."""
    gt = load_live_veo_benchmark("baltimore-armor-20260906 Arlington SA vs Baltimore Armor")
    assert gt["match"]["uuid"] == "e64649b4-c5f9-40b3-b650-4c55340dd59f"
    assert gt["match"]["final_result"]["own"] == 3
    assert gt["match"]["final_result"]["opponent"] == 0

    # Compare mock model stats against Baltimore ground truth
    comp = compare_stats_table(
        {"goals": 3, "shots": 14, "attempts": 17, "possession_percent": 71},
        {"goals": 0, "shots": 4, "attempts": 4, "possession_percent": 29},
        gt_benchmark=gt,
    )
    assert comp["exact_match_count"] >= 8
    assert comp["metrics"]["goal"]["exact_match"] is True
    assert comp["metrics"]["shot"]["exact_match"] is True
    assert comp["metrics"]["possession_percent"]["exact_match"] is True


def test_baltimore_armor_match_pipeline_ml_execution():
    """Verify MatchPipeline runs successfully with Baltimore Armor calibration."""
    repo = MatchRepository()
    test_match_id = "test-baltimore-pipeline-ml"

    match = Match(
        id=test_match_id,
        title="Arlington SA vs Baltimore Armor (Test ML)",
        home_team="Arlington SA U16B ECNL",
        away_team="Baltimore Armor",
        date="2026-09-06",
        video_url="/media/baltimore_armor_sample_30s.mp4",
        duration_seconds=30.0,
        status="processing",
    )
    repo.save_match(match)

    try:
        pipeline = MatchPipeline(
            match_id=test_match_id,
            mode="ml",
            calib_file=BALTIMORE_CALIB_PATH,
            repo=repo,
        )

        res = pipeline.run()

        assert res["mode"] == "ml"
        assert res["match_id"] == test_match_id
        assert res["verified"] is True
        assert res["events_ingested"] == res["events_stored"]
        assert res["radar_frames_stored"] > 0
        assert res["capabilities_count"] == 16
        assert res["analytics_provenance"] == "ml"

        updated = repo.get_match(test_match_id)
        assert updated.status == "ready"
        assert updated.analysis_mode == "ml"
        assert len(updated.event_capabilities) == 16
    finally:
        repo.delete_match(test_match_id)


def test_baltimore_armor_match_pipeline_demo_execution():
    """Verify MatchPipeline runs demo mode fallback cleanly on Baltimore Armor video sample."""
    repo = MatchRepository()
    test_match_id = "test-baltimore-pipeline-demo"

    match = Match(
        id=test_match_id,
        title="Arlington SA vs Baltimore Armor (Test Demo)",
        home_team="Arlington SA U16B ECNL",
        away_team="Baltimore Armor",
        date="2026-09-06",
        video_url="/media/baltimore_armor_sample_30s.mp4",
        duration_seconds=30.0,
        status="processing",
    )
    repo.save_match(match)

    try:
        pipeline = MatchPipeline(
            match_id=test_match_id,
            mode="demo",
            calib_file=BALTIMORE_CALIB_PATH,
            repo=repo,
        )

        res = pipeline.run()

        assert res["mode"] == "demo"
        assert res["match_id"] == test_match_id
        assert res["radar_frames_count"] >= 0
        assert res["events_count"] >= 0

        updated = repo.get_match(test_match_id)
        assert updated.status == "ready"
        assert updated.analysis_mode == "demo"
    finally:
        repo.delete_match(test_match_id)
