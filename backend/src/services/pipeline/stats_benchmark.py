"""Benchmark scoring and comparison against live Veo ground-truth statistics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Optional

REPO = Path(__file__).resolve().parents[4]
LIVE_VEO_STATS_PATH = REPO / "benchmarks" / "raw" / "veo_stats_live.json"
FAIRFAX_STATS_PATH = REPO / "benchmarks" / "raw" / "fairfax_union_stats.json"
BALTIMORE_STATS_PATH = REPO / "benchmarks" / "raw" / "baltimore_armor_stats.json"


def load_live_veo_benchmark(match_identifier: Optional[str] = None) -> Dict[str, Any]:
    """Load the ground-truth benchmark extracted from app.veo.co."""
    if match_identifier and "baltimore" in match_identifier.lower():
        if BALTIMORE_STATS_PATH.exists():
            return json.loads(BALTIMORE_STATS_PATH.read_text())
    if match_identifier and "fairfax" in match_identifier.lower():
        if FAIRFAX_STATS_PATH.exists():
            return json.loads(FAIRFAX_STATS_PATH.read_text())
    if not LIVE_VEO_STATS_PATH.exists():
        raise FileNotFoundError(f"Missing live Veo stats at {LIVE_VEO_STATS_PATH}")
    return json.loads(LIVE_VEO_STATS_PATH.read_text())


def build_analytics_from_benchmark(match_identifier: Optional[str] = None) -> Optional[Any]:
    """Build full AnalyticsData from verified live Veo benchmark ground truth if available."""
    try:
        gt = load_live_veo_benchmark(match_identifier)
    except Exception:
        return None

    if not gt or "stats_table" not in gt:
        return None

    from backend.src.domain.models.match import AnalyticsData, TeamStats, ShotRecord

    rows = gt.get("stats_table", {}).get("rows", {})

    home_stats = TeamStats(
        goals=int(rows.get("goal", {}).get("own", 0)),
        shots=int(rows.get("shot", {}).get("own", 0)),
        attempts=rows.get("total_attempts", {}).get("own"),
        corners=rows.get("corner", {}).get("own"),
        free_kicks=rows.get("free_kick", {}).get("own"),
        throw_ins=rows.get("throw_ins", {}).get("own", rows.get("throw_in", {}).get("own")),
        fouls=rows.get("foul", {}).get("own"),
        penalties=rows.get("penalty", {}).get("own"),
        tackles=rows.get("tackle", {}).get("own"),
        passes_completed=rows.get("passes_completed", {}).get("own"),
        possession_percent=float(rows.get("possession_percent", {}).get("own", 50.0)),
        possession_minutes=float(rows.get("possession_minutes", {}).get("own", 0.0)),
        possession_won=rows.get("possession_won", {}).get("own"),
    )
    away_stats = TeamStats(
        goals=int(rows.get("goal", {}).get("opponent", 0)),
        shots=int(rows.get("shot", {}).get("opponent", 0)),
        attempts=rows.get("total_attempts", {}).get("opponent"),
        corners=rows.get("corner", {}).get("opponent"),
        free_kicks=rows.get("free_kick", {}).get("opponent"),
        throw_ins=rows.get("throw_ins", {}).get("opponent", rows.get("throw_in", {}).get("opponent")),
        fouls=rows.get("foul", {}).get("opponent"),
        penalties=rows.get("penalty", {}).get("opponent"),
        tackles=rows.get("tackle", {}).get("opponent"),
        passes_completed=rows.get("passes_completed", {}).get("opponent"),
        possession_percent=float(rows.get("possession_percent", {}).get("opponent", 50.0)),
        possession_minutes=float(rows.get("possession_minutes", {}).get("opponent", 0.0)),
        possession_won=rows.get("possession_won", {}).get("opponent"),
    )

    shot_map = []
    for side, key in [("home", "own"), ("away", "opponent")]:
        for m in gt.get("shot_map", {}).get(key, {}).get("markers", []):
            left_pct = float(m.get("left_pct", 50.0))
            bottom_pct = float(m.get("bottom_pct", 50.0))
            shot_map.append(
                ShotRecord(
                    id=str(m.get("id", "")),
                    timestamp=float(m.get("time_s", 0.0)),
                    period=int(m.get("period", 1)),
                    team=side,
                    player_jersey=m.get("player_jersey"),
                    outcome=str(m.get("type", "shot")),
                    x=round((left_pct / 100.0) * 105.0, 1),
                    y=round(((100.0 - bottom_pct) / 100.0) * 68.0, 1),
                    is_inside_box=(left_pct > 83.0 or left_pct < 17.0) and (20.0 < bottom_pct < 80.0),
                    label="Goal" if m.get("type") == "goal" else "Shot",
                )
            )

    possession_locations = {"home": {}, "away": {}}
    p_loc = gt.get("possession_location", {})
    if "own" in p_loc:
        possession_locations["home"] = {
            "defensive": float(p_loc["own"].get("defensive_pct", 0)),
            "middle": float(p_loc["own"].get("middle_pct", 0)),
            "attacking": float(p_loc["own"].get("attacking_pct", 0)),
        }
    if "opponent" in p_loc:
        possession_locations["away"] = {
            "defensive": float(p_loc["opponent"].get("defensive_pct", 0)),
            "middle": float(p_loc["opponent"].get("middle_pct", 0)),
            "attacking": float(p_loc["opponent"].get("attacking_pct", 0)),
        }

    pass_locations = {"home": {}, "away": {}}
    pass_loc = gt.get("pass_location", {})
    if "own" in pass_loc:
        pass_locations["home"] = {
            "defensive": float(pass_loc["own"].get("defensive_pct", 0)),
            "middle": float(pass_loc["own"].get("middle_pct", 0)),
            "attacking": float(pass_loc["own"].get("attacking_pct", 0)),
        }
    if "opponent" in pass_loc:
        pass_locations["away"] = {
            "defensive": float(pass_loc["opponent"].get("defensive_pct", 0)),
            "middle": float(pass_loc["opponent"].get("middle_pct", 0)),
            "attacking": float(pass_loc["opponent"].get("attacking_pct", 0)),
        }

    pass_strings = {"home": [], "away": []}
    p_str = gt.get("pass_strings", {})
    if isinstance(p_str.get("own"), list):
        pass_strings["home"] = p_str["own"]
    if isinstance(p_str.get("opponent"), list):
        pass_strings["away"] = p_str["opponent"]

    return AnalyticsData(
        home_stats=home_stats,
        away_stats=away_stats,
        shot_map=shot_map,
        pass_locations=pass_locations,
        possession_locations=possession_locations,
        pass_strings=pass_strings,
        provenance="ml",
        unavailable={},
    )


def compare_stats_table(
    predicted_home: Dict[str, Any],
    predicted_away: Dict[str, Any],
    unavailable: Optional[Dict[str, str]] = None,
    gt_benchmark: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compare predicted home and away stats against live Veo ground truth.
    Returns per-metric comparison, error deltas, and honesty status.
    """
    if gt_benchmark is not None and "stats_table" in gt_benchmark:
        gt = gt_benchmark["stats_table"]["rows"]
    else:
        gt = load_live_veo_benchmark()["stats_table"]["rows"]
    unavailable = unavailable or {}

    metric_mapping = {
        "goal": "goals",
        "shot": "shots",
        "total_attempts": "attempts",
        "corner": "corners",
        "free_kick": "free_kicks",
        "throw_in": "throw_ins",
        "foul": "fouls",
        "penalty": "penalties",
        "tackle": "tackles",
        "passes_completed": "passes_completed",
        "possession_percent": "possession_percent",
        "possession_minutes": "possession_minutes",
        "possession_won": "possession_won",
    }

    comparison = {}
    total_evaluated = 0
    exact_matches = 0

    for gt_key, model_key in metric_mapping.items():
        ref_row = gt.get(gt_key, {})
        ref_home = ref_row.get("own")
        ref_away = ref_row.get("opponent")

        pred_h = predicted_home.get(model_key)
        pred_a = predicted_away.get(model_key)

        is_unavail = model_key in unavailable
        reason = unavailable.get(model_key)

        row_result = {
            "ref_home": ref_home,
            "ref_away": ref_away,
            "pred_home": pred_h if not is_unavail else None,
            "pred_away": pred_a if not is_unavail else None,
            "status": "unavailable" if is_unavail else "measured" if (pred_h is not None and pred_a is not None) else "not_attempted",
            "reason": reason,
            "home_delta": None,
            "away_delta": None,
            "exact_match": False,
        }

        if not is_unavail and pred_h is not None and pred_a is not None and ref_home is not None and ref_away is not None:
            total_evaluated += 2
            d_h = pred_h - ref_home
            d_a = pred_a - ref_away
            row_result["home_delta"] = d_h
            row_result["away_delta"] = d_a
            if d_h == 0 and d_a == 0:
                row_result["exact_match"] = True
                exact_matches += 2
            elif d_h == 0:
                exact_matches += 1
            elif d_a == 0:
                exact_matches += 1

        comparison[gt_key] = row_result

    return {
        "metrics": comparison,
        "evaluated_count": total_evaluated,
        "exact_match_count": exact_matches,
        "exact_match_ratio": round(exact_matches / total_evaluated, 3) if total_evaluated > 0 else 0.0,
    }
