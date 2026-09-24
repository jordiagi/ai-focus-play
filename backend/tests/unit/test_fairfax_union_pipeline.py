"""Unit tests for Fairfax Union match assets, Veo ground-truth parity, and MatchPipeline execution."""

import json
from pathlib import Path
import pytest

from backend.src.domain.models.match import Match
from backend.src.services.pipeline.pipeline_runner import MatchPipeline
from backend.src.services.pipeline.radar_calibrator import CalibratedPitchRadar
from backend.src.services.pipeline.veo_calibrator import VeoCameraModel
from backend.src.storage.repository import MatchRepository

REPO = Path(__file__).resolve().parents[3]
FAIRFAX_CALIB_PATH = REPO / "benchmarks" / "raw" / "fairfax_union_camera_alignment.veo"
FAIRFAX_STATS_PATH = REPO / "benchmarks" / "raw" / "fairfax_union_stats.json"
FAIRFAX_VIDEO_PATH = REPO / "backend" / ".local" / "media" / "fairfax_union_sample_30s.mp4"


def test_fairfax_union_assets_exist():
    """Verify raw calibration, live stats, and video sample assets exist."""
    assert FAIRFAX_CALIB_PATH.exists(), f"Missing calibration file at {FAIRFAX_CALIB_PATH}"
    assert FAIRFAX_STATS_PATH.exists(), f"Missing stats file at {FAIRFAX_STATS_PATH}"
    assert FAIRFAX_VIDEO_PATH.exists(), f"Missing video sample at {FAIRFAX_VIDEO_PATH}"
    assert FAIRFAX_VIDEO_PATH.stat().st_size > 1_000_000, "Sample video should be > 1MB"


def test_fairfax_union_camera_calibration():
    """Verify VeoCameraModel parses the Fairfax Union .veo alignment accurately."""
    model = VeoCameraModel.from_veo_file(str(FAIRFAX_CALIB_PATH))
    
    # Camera height should be around 4.17 meters (standard amateur Veo pole setup)
    assert 3.5 <= model.camera_height <= 6.5
    assert abs(model.camera_height - 4.17) < 0.1
    
    # Pitch dimensions from camera alignment
    assert model.field_length == 105.0
    assert 68.0 <= model.field_width <= 72.0


def test_fairfax_union_stats_table_mathematical_consistency():
    """Verify mathematical consistency of Fairfax Union Veo stats table."""
    data = json.loads(FAIRFAX_STATS_PATH.read_text())
    stats = data["stats_table"]["rows"]
    
    # Check attempt arithmetic
    assert stats["total_attempts"]["own"] == stats["goal"]["own"] + stats["shot"]["own"]
    assert stats["total_attempts"]["opponent"] == stats["goal"]["opponent"] + stats["shot"]["opponent"]
    assert stats["total_attempts"]["own"] == 18
    assert stats["total_attempts"]["opponent"] == 5
    
    # Check possession percentages sum to 100
    assert stats["possession_percent"]["own"] + stats["possession_percent"]["opponent"] == 100
    assert stats["possession_percent"]["own"] == 74
    assert stats["possession_percent"]["opponent"] == 26
    
    # Check score consistency
    assert stats["goal"]["own"] == data["match"]["final_result"]["own"]
    assert stats["goal"]["opponent"] == data["match"]["final_result"]["opponent"]


def test_fairfax_union_shot_map_parity():
    """Verify Shot Map coordinates and conversion rates against Veo live analysis."""
    data = json.loads(FAIRFAX_STATS_PATH.read_text())
    shot_map = data["shot_map"]

    for side in ["own", "opponent"]:
        side_data = shot_map[side]
        markers = side_data["markers"]
        assert len(markers) == side_data["total_attempts"]
        
        goal_markers = [m for m in markers if m["type"] == "goal"]
        shot_markers = [m for m in markers if m["type"] == "shot"]
        assert len(goal_markers) == side_data["goals"]
        assert len(shot_markers) == side_data["shots"]
        
        # Check all marker coordinates lie within pitch boundary (0-100%)
        for m in markers:
            if m["left_pct"] is not None:
                assert 0.0 <= m["left_pct"] <= 100.0
            if m["bottom_pct"] is not None:
                assert 0.0 <= m["bottom_pct"] <= 100.0

        # Check conversion rate calculation
        computed_conv = round((side_data["goals"] / side_data["total_attempts"]) * 100)
        assert abs(computed_conv - side_data["conversion_rate_pct"]) <= 1


def test_fairfax_union_pass_and_possession_locations():
    """Verify pass and possession locations sum to 100% for each team."""
    data = json.loads(FAIRFAX_STATS_PATH.read_text())
    
    for loc_key in ["pass_location", "possession_location"]:
        loc_data = data[loc_key]
        for side in ["own", "opponent"]:
            d = loc_data[side]
            total = d["defensive_pct"] + d["middle_pct"] + d["attacking_pct"]
            assert abs(total - 100) <= 1, f"{loc_key} for {side} sums to {total}, expected 100"


def test_fairfax_union_match_pipeline_ml_execution():
    """Verify MatchPipeline runs successfully with Fairfax Union calibration."""
    repo = MatchRepository()
    test_match_id = "test-fairfax-pipeline-ml"
    
    match = Match(
        id=test_match_id,
        title="Arlington SA vs Fairfax Union (Test ML)",
        home_team="Arlington SA U16B ECNL",
        away_team="Fairfax Union",
        date="2026-09-20",
        video_url="/media/fairfax_union_sample_30s.mp4",
        duration_seconds=30.0,
        status="processing",
    )
    repo.save_match(match)

    try:
        pipeline = MatchPipeline(
            match_id=test_match_id,
            mode="ml",
            calib_file=FAIRFAX_CALIB_PATH,
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


def test_fairfax_union_match_pipeline_demo_execution():
    """Verify MatchPipeline runs demo mode fallback cleanly on Fairfax Union video sample."""
    repo = MatchRepository()
    test_match_id = "test-fairfax-pipeline-demo"
    
    match = Match(
        id=test_match_id,
        title="Arlington SA vs Fairfax Union (Test Demo)",
        home_team="Arlington SA U16B ECNL",
        away_team="Fairfax Union",
        date="2026-09-20",
        video_url="/media/fairfax_union_sample_30s.mp4",
        duration_seconds=30.0,
        status="processing",
    )
    repo.save_match(match)

    try:
        pipeline = MatchPipeline(
            match_id=test_match_id,
            mode="demo",
            calib_file=FAIRFAX_CALIB_PATH,
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
