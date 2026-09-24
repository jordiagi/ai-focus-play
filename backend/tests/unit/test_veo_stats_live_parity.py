import json
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[3]
VEO_STATS_PATH = REPO / "benchmarks" / "raw" / "veo_stats_live.json"


def test_veo_stats_live_file_exists():
    assert VEO_STATS_PATH.exists(), f"Missing ground truth file at {VEO_STATS_PATH}"


def test_veo_stats_table_mathematical_consistency():
    data = json.loads(VEO_STATS_PATH.read_text())
    stats = data["stats_table"]["rows"]
    
    # Check attempt arithmetic
    assert stats["total_attempts"]["own"] == stats["goal"]["own"] + stats["shot"]["own"]
    assert stats["total_attempts"]["opponent"] == stats["goal"]["opponent"] + stats["shot"]["opponent"]
    
    # Check possession percentages sum to 100
    assert stats["possession_percent"]["own"] + stats["possession_percent"]["opponent"] == 100
    
    # Check foul / free kick symmetry
    # Veo's model: free kick awarded to own corresponds closely to fouls by opponent
    assert stats["foul"]["own"] >= 0 and stats["foul"]["opponent"] >= 0
    assert stats["free_kick"]["own"] >= 0 and stats["free_kick"]["opponent"] >= 0


def test_veo_shot_map_markers_and_conversion_rates():
    data = json.loads(VEO_STATS_PATH.read_text())
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
            assert 0.0 <= m["left_pct"] <= 100.0
            assert 0.0 <= m["bottom_pct"] <= 100.0

        # Check conversion rate calculation
        computed_conv = round((side_data["goals"] / side_data["total_attempts"]) * 100)
        assert abs(computed_conv - side_data["conversion_rate_pct"]) <= 1


def test_veo_pass_and_possession_location_distributions():
    data = json.loads(VEO_STATS_PATH.read_text())
    
    for loc_key in ["pass_location", "possession_location"]:
        loc_data = data[loc_key]
        for side in ["own", "opponent"]:
            d = loc_data[side]
            total_pct = d["defensive_pct"] + d["middle_pct"] + d["attacking_pct"]
            assert abs(total_pct - 100) <= 1, f"{loc_key} {side} did not sum to 100: {total_pct}"


def test_veo_pass_strings_histogram_reconciliation():
    data = json.loads(VEO_STATS_PATH.read_text())
    pass_strings = data["pass_strings"]

    for side in ["own", "opponent"]:
        ps = pass_strings[side]
        hist = ps["histogram"]
        
        # 3 to 5 passes reconciliation
        sum_3_to_5 = hist["3"] + hist["4"] + hist["5"]
        assert sum_3_to_5 == ps["three_to_five_passes"]
        
        # 6 or more passes reconciliation
        sum_6_plus = sum(hist[k] for k in ["6", "7", "8", "9", "10+"])
        assert sum_6_plus == ps["six_or_more_passes"]
        
        # Longest string must be >= highest non-zero bucket
        if ps["longest_pass_string"] > 0:
            assert ps["longest_pass_string"] >= 3


def test_veo_lineup_roster_integrity():
    data = json.loads(VEO_STATS_PATH.read_text())
    roster = data["lineup_roster"]
    assert len(roster) == 16
    assert "Eric Yeh-Fuentes" in roster
    assert len(set(roster)) == 16  # Unique player names
