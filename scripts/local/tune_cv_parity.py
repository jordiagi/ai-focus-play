#!/usr/bin/env python3
"""Autonomous Computer Vision Parity Benchmarking & Calibration Engine.

Evaluates local CV models (PitchHomography, TrackletTracker, TurfPossessionEngine,
and PhysicsShotDetector) blindly on video footage WITHOUT external Veo API exports.
Then measures prediction accuracy against live Veo ground-truth benchmarks across:
1. Possession % and possession minutes.
2. Completed passes and pass strings distributions.
3. Physics-based shot detection and team attribution.
4. Field location thirds breakdowns (defensive, middle, attacking).

Training Match: Arlington vs. Skyline (447-event reference)
Validation Match: Arlington vs. Fairfax Union (Held-out 98-minute 1080p recording)
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from backend.src.services.pipeline.pitch_homography import PitchHomography
from backend.src.services.pipeline.tracklet_tracker import TrackletTracker
from backend.src.services.pipeline.turf_possession import TurfPossessionEngine
from backend.src.services.pipeline.physics_shot_detector import PhysicsShotDetector
from backend.src.services.pipeline.radar_calibrator import CalibratedPitchRadar

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CVParity")


def run_blind_pipeline(
    match_id: str,
    artifacts_dir: Path,
    match_duration_s: float,
    calib_file: Optional[Path] = None,
    control_radius_m: float = 3.4,
) -> Dict[str, Any]:
    """Execute the computer vision pipeline blindly on video detection artifacts."""
    logger.info(f"Running blind CV evaluation on match: {match_id}")

    # 1. Load player detections
    players_file = artifacts_dir / "players_colour.json"
    if not players_file.exists():
        players_file = artifacts_dir / "players_ko.json"

    if not players_file.exists():
        raise FileNotFoundError(f"No player detections found in {artifacts_dir}")

    p_raw = json.loads(players_file.read_text())
    p_data = p_raw.get("detections", []) if isinstance(p_raw, dict) else p_raw

    # 2. Load ball detections
    ball_file = artifacts_dir / "ball_candidates.json"
    if not ball_file.exists():
        ball_file = artifacts_dir / "ball_track.json"

    if not ball_file.exists():
        raise FileNotFoundError(f"No ball detections found in {artifacts_dir}")

    b_raw = json.loads(ball_file.read_text())
    if isinstance(b_raw, dict):
        b_frames = b_raw.get("detections", [])
    elif isinstance(b_raw, list):
        b_frames = [
            {"t": item.get("t", 0.0), "c": [[item.get("u", 0.0), item.get("v", 0.0), 10.0, 0.9]]}
            for item in b_raw
        ]

    # 3. Form Tracklets & Cluster Kits
    homography = PitchHomography.canonical_broadcast_prior()
    tracker = TrackletTracker(homography=homography)
    tracklets = tracker.process_frames(p_data)

    logger.info(f"Formed {len(tracklets)} tracklets across {len(p_data)} frames.")

    # 4. Turf Possession & Pass Analytics
    possession_engine = TurfPossessionEngine(homography=homography, control_radius_m=control_radius_m)
    turf_res = possession_engine.compute_analytics(tracklets, b_frames, match_duration_s=match_duration_s)

    # 5. Physics Shot Detection
    shot_detector = PhysicsShotDetector(
        min_speed_mps=8.0,
        max_speed_mps=38.0,
        max_goal_dist_m=32.0,
        min_cone_cos=0.85,
        nms_window_s=8.0,
    )

    shot_cands = []
    ball_track_file = artifacts_dir / "ball_track.json"
    if calib_file and calib_file.exists() and ball_track_file.exists():
        radar = CalibratedPitchRadar.from_artifacts(
            veo_calib_path=calib_file,
            cameras_path=artifacts_dir / "cameras.json" if (artifacts_dir / "cameras.json").exists() else None,
            ball_track_path=ball_track_file,
        )
        if radar.ball_track and len(radar.ball_track) > 1:
            shot_cands = shot_detector.detect_from_calibrated_radar(radar)
    elif b_frames and len(b_frames) > 1:
        metric_pts = []
        for item in b_frames:
            t = float(item.get("t", 0.0))
            c_list = item.get("c", [])
            if c_list:
                best_cand = max(c_list, key=lambda c: c[3] if len(c) > 3 else 0.5)
                turf_pt = homography.project_point(best_cand[0], best_cand[1])
                if turf_pt:
                    metric_pts.append((t, turf_pt[0], turf_pt[1]))
        if len(metric_pts) > 1:
            shot_cands = shot_detector.detect_from_metric_track(
                metric_pts,
                p1_bounds=(0.0, match_duration_s / 2.0),
                p2_bounds=(match_duration_s / 2.0, match_duration_s),
            )

    home_shots = sum(1 for c in shot_cands if getattr(c, "team", None) == "home")
    away_shots = sum(1 for c in shot_cands if getattr(c, "team", None) == "away")

    return {
        "match_id": match_id,
        "tracklets_count": len(tracklets),
        "possession_percent": turf_res["possession_percent"],
        "possession_minutes": turf_res["possession_minutes"],
        "passes_completed": turf_res["passes_completed"],
        "pass_strings": turf_res["pass_strings"],
        "possession_locations": turf_res["possession_locations"],
        "pass_locations": turf_res["pass_locations"],
        "shots": {"home": home_shots, "away": away_shots, "total": len(shot_cands)},
        "shot_candidates": [
            {
                "t": c.timestamp,
                "period": c.period,
                "team": c.team,
                "speed": c.speed_mps,
                "dist": c.dist_to_goal_m,
                "cos": c.goal_alignment_cos,
            }
            for c in shot_cands
        ],
    }


def compare_metrics(predicted: Dict[str, Any], ground_truth: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate absolute and percentage errors between blind predictions and ground truth."""
    pred_poss = predicted["possession_percent"]
    gt_poss = ground_truth.get("top_cards", {}).get("possession_percent", {}).get("value")
    if gt_poss is None:
        gt_poss = ground_truth.get("stats_table", {}).get("rows", {}).get("possession_percent", {}).get("own", 50.0)

    gt_poss_away = 100.0 - float(gt_poss)
    poss_error = abs(float(pred_poss["home"]) - float(gt_poss))

    # Passes
    pred_passes = predicted["passes_completed"]
    gt_passes_home = ground_truth.get("stats_table", {}).get("rows", {}).get("passes_completed", {}).get("own", 0)
    gt_passes_away = ground_truth.get("stats_table", {}).get("rows", {}).get("passes_completed", {}).get("opponent", 0)
    pass_error_home = abs(pred_passes["home"] - gt_passes_home)
    pass_error_away = abs(pred_passes["away"] - gt_passes_away)

    # Shots
    pred_shots = predicted["shots"]
    gt_shots_home = ground_truth.get("stats_table", {}).get("rows", {}).get("shot", {}).get("own", 0)
    gt_shots_away = ground_truth.get("stats_table", {}).get("rows", {}).get("shot", {}).get("opponent", 0)
    shot_error_home = abs(pred_shots["home"] - gt_shots_home)
    shot_error_away = abs(pred_shots["away"] - gt_shots_away)

    return {
        "possession": {
            "predicted_home": pred_poss["home"],
            "predicted_away": pred_poss["away"],
            "ground_truth_home": float(gt_poss),
            "ground_truth_away": gt_poss_away,
            "error_pct": round(poss_error, 2),
        },
        "possession_minutes": {
            "predicted_home": predicted["possession_minutes"]["home"],
            "predicted_away": predicted["possession_minutes"]["away"],
            "ground_truth_home": ground_truth.get("stats_table", {}).get("rows", {}).get("possession_minutes", {}).get("own", 0),
            "ground_truth_away": ground_truth.get("stats_table", {}).get("rows", {}).get("possession_minutes", {}).get("opponent", 0),
        },
        "passes_completed": {
            "predicted_home": pred_passes["home"],
            "predicted_away": pred_passes["away"],
            "ground_truth_home": gt_passes_home,
            "ground_truth_away": gt_passes_away,
            "error_home": pass_error_home,
            "error_away": pass_error_away,
        },
        "shots": {
            "predicted_home": pred_shots["home"],
            "predicted_away": pred_shots["away"],
            "predicted_total": pred_shots["total"],
            "ground_truth_home": gt_shots_home,
            "ground_truth_away": gt_shots_away,
            "ground_truth_total": gt_shots_home + gt_shots_away,
            "error_home": shot_error_home,
            "error_away": shot_error_away,
        },
    }


def main():
    print("=" * 80)
    print("AUTONOMOUS CV MODEL PARITY BENCHMARK & CALIBRATION ENGINE")
    print("=" * 80)

    # 1. Training Set: Arlington SA vs. Skyline U16B ECNL
    skyline_art = REPO / "backend/.local/artifacts/mosaic"
    skyline_calib = REPO / "benchmarks/raw/skyline_camera_alignment.veo"
    skyline_gt_file = REPO / "benchmarks/raw/veo_stats_live.json"
    with open(skyline_gt_file) as f:
        skyline_gt = json.load(f)

    logger.info("Executing Blind Evaluation on Training Match (Arlington vs. Skyline)...")
    skyline_pred = run_blind_pipeline(
        match_id="arlington_vs_skyline",
        artifacts_dir=skyline_art,
        match_duration_s=5400.0,
        calib_file=skyline_calib,
        control_radius_m=3.4,
    )
    skyline_comp = compare_metrics(skyline_pred, skyline_gt)

    # 2. Validation Set: Arlington SA vs. Fairfax Union (Held-Out)
    fairfax_art = REPO / "backend/.local/artifacts/fairfax-union-20260920"
    fairfax_calib = REPO / "benchmarks/raw/fairfax_union_camera_alignment.veo"
    fairfax_gt_file = REPO / "benchmarks/raw/fairfax_union_stats.json"
    with open(fairfax_gt_file) as f:
        fairfax_gt = json.load(f)

    logger.info("Executing Blind Evaluation on Validation Match (Arlington vs. Fairfax Union)...")
    fairfax_pred = run_blind_pipeline(
        match_id="arlington_vs_fairfax",
        artifacts_dir=fairfax_art,
        match_duration_s=5843.0,
        calib_file=fairfax_calib if fairfax_calib.exists() else None,
        control_radius_m=3.4,
    )
    fairfax_comp = compare_metrics(fairfax_pred, fairfax_gt)

    # 3. Test Set: Arlington SA vs. Baltimore Armor (3rd Match)
    baltimore_art = REPO / "backend/.local/artifacts/baltimore-armor-20260906"
    baltimore_calib = REPO / "benchmarks/raw/baltimore_armor_camera_alignment.veo"
    baltimore_gt_file = REPO / "benchmarks/raw/baltimore_armor_stats.json"
    with open(baltimore_gt_file) as f:
        baltimore_gt = json.load(f)

    logger.info("Executing Blind Evaluation on Test Match (Arlington vs. Baltimore Armor)...")
    baltimore_pred = run_blind_pipeline(
        match_id="arlington_vs_baltimore",
        artifacts_dir=baltimore_art,
        match_duration_s=6988.0,
        calib_file=baltimore_calib if baltimore_calib.exists() else None,
        control_radius_m=3.4,
    )
    baltimore_comp = compare_metrics(baltimore_pred, baltimore_gt)

    # 4. Print Quantitative Parity Report
    print("\n" + "=" * 80)
    print("MATCH 1 (TRAINING): Arlington vs. Skyline (447-Event Reference)")
    print("=" * 80)
    p_sky = skyline_comp["possession"]
    print(f"Possession %:       Predicted {p_sky['predicted_home']}% vs {p_sky['predicted_away']}%  |  "
          f"Veo GT {p_sky['ground_truth_home']}% vs {p_sky['ground_truth_away']}%  "
          f"(Error: {p_sky['error_pct']}%)")
    m_sky = skyline_comp["possession_minutes"]
    print(f"Possession Mins:    Predicted {m_sky['predicted_home']}m vs {m_sky['predicted_away']}m  |  "
          f"Veo GT {m_sky['ground_truth_home']}m vs {m_sky['ground_truth_away']}m")
    pa_sky = skyline_comp["passes_completed"]
    print(f"Passes Completed:   Predicted {pa_sky['predicted_home']} vs {pa_sky['predicted_away']}  |  "
          f"Veo GT {pa_sky['ground_truth_home']} vs {pa_sky['ground_truth_away']}  "
          f"(Home err: {pa_sky['error_home']}, Away err: {pa_sky['error_away']})")
    sh_sky = skyline_comp["shots"]
    print(f"Shots Detected:     Predicted {sh_sky['predicted_home']} vs {sh_sky['predicted_away']} (Tot: {sh_sky['predicted_total']})  |  "
          f"Veo GT {sh_sky['ground_truth_home']} vs {sh_sky['ground_truth_away']} (Tot: {sh_sky['ground_truth_total']})")

    print("\n" + "=" * 80)
    print("MATCH 2 (VALIDATION): Arlington vs. Fairfax Union (Held-Out 98m)")
    print("=" * 80)
    p_ff = fairfax_comp["possession"]
    print(f"Possession %:       Predicted {p_ff['predicted_home']}% vs {p_ff['predicted_away']}%  |  "
          f"Veo GT {p_ff['ground_truth_home']}% vs {p_ff['ground_truth_away']}%  "
          f"(Error: {p_ff['error_pct']}%)")
    m_ff = fairfax_comp["possession_minutes"]
    print(f"Possession Mins:    Predicted {m_ff['predicted_home']}m vs {m_ff['predicted_away']}m  |  "
          f"Veo GT {m_ff['ground_truth_home']}m vs {m_ff['ground_truth_away']}m")
    pa_ff = fairfax_comp["passes_completed"]
    print(f"Passes Completed:   Predicted {pa_ff['predicted_home']} vs {pa_ff['predicted_away']}  |  "
          f"Veo GT {pa_ff['ground_truth_home']} vs {pa_ff['ground_truth_away']}  "
          f"(Home err: {pa_ff['error_home']}, Away err: {pa_ff['error_away']})")
    sh_ff = fairfax_comp["shots"]
    print(f"Shots Detected:     Predicted {sh_ff['predicted_home']} vs {sh_ff['predicted_away']} (Tot: {sh_ff['predicted_total']})  |  "
          f"Veo GT {sh_ff['ground_truth_home']} vs {sh_ff['ground_truth_away']} (Tot: {sh_ff['ground_truth_total']})")

    print("\n" + "=" * 80)
    print("MATCH 3 (TEST SET): Arlington vs. Baltimore Armor (Full 116.5m 1080p)")
    print("=" * 80)
    p_ba = baltimore_comp["possession"]
    print(f"Possession %:       Predicted {p_ba['predicted_home']}% vs {p_ba['predicted_away']}%  |  "
          f"Veo GT {p_ba['ground_truth_home']}% vs {p_ba['ground_truth_away']}%  "
          f"(Error: {p_ba['error_pct']}%)")
    m_ba = baltimore_comp["possession_minutes"]
    print(f"Possession Mins:    Predicted {m_ba['predicted_home']}m vs {m_ba['predicted_away']}m  |  "
          f"Veo GT {m_ba['ground_truth_home']}m vs {m_ba['ground_truth_away']}m")
    pa_ba = baltimore_comp["passes_completed"]
    print(f"Passes Completed:   Predicted {pa_ba['predicted_home']} vs {pa_ba['predicted_away']}  |  "
          f"Veo GT {pa_ba['ground_truth_home']} vs {pa_ba['ground_truth_away']}  "
          f"(Home err: {pa_ba['error_home']}, Away err: {pa_ba['error_away']})")
    sh_ba = baltimore_comp["shots"]
    print(f"Shots Detected:     Predicted {sh_ba['predicted_home']} vs {sh_ba['predicted_away']} (Tot: {sh_ba['predicted_total']})  |  "
          f"Veo GT {sh_ba['ground_truth_home']} vs {sh_ba['ground_truth_away']} (Tot: {sh_ba['ground_truth_total']})")

    # Consolidated 3-match artifact
    all_p_errs = [p_sky["error_pct"], p_ff["error_pct"], p_ba["error_pct"]]
    all_pa_errs = [
        pa_sky["error_home"], pa_sky["error_away"],
        pa_ff["error_home"], pa_ff["error_away"],
        pa_ba["error_home"], pa_ba["error_away"],
    ]
    all_sh_errs = [
        sh_sky["error_home"], sh_sky["error_away"],
        sh_ff["error_home"], sh_ff["error_away"],
        sh_ba["error_home"], sh_ba["error_away"],
    ]

    benchmark_report = {
        "training_skyline": {
            "prediction": skyline_pred,
            "comparison": skyline_comp,
        },
        "validation_fairfax": {
            "prediction": fairfax_pred,
            "comparison": fairfax_comp,
        },
        "test_baltimore": {
            "prediction": baltimore_pred,
            "comparison": baltimore_comp,
        },
        "summary": {
            "possession_mae": round(sum(all_p_errs) / len(all_p_errs), 2),
            "passes_mae": round(sum(all_pa_errs) / len(all_pa_errs), 1),
            "shots_mae": round(sum(all_sh_errs) / len(all_sh_errs), 1),
            "matches_evaluated": 3,
        },
    }

    out_json = REPO / "backend/.local/artifacts/cv_parity_benchmark.json"
    out_json.write_text(json.dumps(benchmark_report, indent=2))
    print("\n" + "=" * 80)
    print(f"Saved benchmark artifact to: {out_json}")
    print(f"Overall 3-Match Possession MAE: {benchmark_report['summary']['possession_mae']}%")
    print(f"Overall 3-Match Passes MAE:     {benchmark_report['summary']['passes_mae']}")
    print(f"Overall 3-Match Shots MAE:      {benchmark_report['summary']['shots_mae']}")
    print("=" * 80)


if __name__ == "__main__":
    main()
