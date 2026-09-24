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
