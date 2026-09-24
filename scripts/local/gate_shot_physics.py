#!/usr/bin/env python3
"""Adversarial Gate Script: Physics-Based 3D Goal-Directed Shot Detection.

Evaluates PhysicsShotDetector on metric pitch ball trajectories projected
via VeoCameraModel and scores held-out Period 2 against the 447-event benchmark.
Outputs complete gate verification status to stdout and JSON artifact.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from backend.src.services.pipeline.physics_shot_detector import PhysicsShotDetector
from backend.src.services.pipeline.radar_calibrator import CalibratedPitchRadar


def main():
    print("=" * 70)
    print("RUNNING GATE: Physics-Based 3D Goal-Directed Shot Detection")
    print("=" * 70)

    # 1. Load Ground Truth Shots
    bench_csv = REPO / "benchmarks/raw/veo_events_447.csv"
    with open(bench_csv) as f:
        gt_shots = [
            {
                "video_s": int(r["video_time_ms"]) / 1000.0,
                "period": int(r["period_id"]),
                "team": r["team"],
                "jersey": r.get("player_jersey"),
            }
            for r in csv.DictReader(f)
            if r["event_type"] == "FootballShot"
        ]

    p1_refs = [s for s in gt_shots if s["period"] == 1]
    p2_refs = [s for s in gt_shots if s["period"] == 2]
    print(f"Loaded {len(gt_shots)} GT shots: Period 1 = {len(p1_refs)}, Period 2 = {len(p2_refs)}")

    # 2. Calibrate Ball Track through Rigid Camera Model
    veo_calib = REPO / "benchmarks/raw/skyline_camera_alignment.veo"
    ball_track_file = REPO / "backend/.local/artifacts/mosaic/ball_track.json"

    radar = CalibratedPitchRadar.from_artifacts(
        veo_calib_path=veo_calib,
        ball_track_path=ball_track_file,
    )

    metric_pts = []
    for b in radar.ball_track:
        u, v, t = float(b["u"]), float(b["v"]), float(b["t"])
        rpt = radar.camera_model.panorama_pixel_to_radar(u, v, radar.scale, radar.origin)
        if rpt and -5.0 <= rpt[0] <= 110.0 and -5.0 <= rpt[1] <= 73.0:
            metric_pts.append((t, rpt[0], rpt[1]))

    print(f"Calibrated {len(metric_pts)} / {len(radar.ball_track)} metric ball points on turf plane.")

    # 3. Detect Shots
    detector = PhysicsShotDetector(
        min_speed_mps=8.0,
        max_goal_dist_m=32.0,
        min_cone_cos=0.85,
        nms_window_s=8.0,
    )

    all_cands = detector.detect_from_metric_track(metric_pts)
    p1_cands = [c for c in all_cands if c.period == 1]
    p2_cands = [c for c in all_cands if c.period == 2]
    print(f"Detected {len(all_cands)} shot candidates (P1: {len(p1_cands)}, P2: {len(p2_cands)})")

    # 4. Evaluate Gate
    gate_result = detector.evaluate_gate(
        p1_candidates=p1_cands,
        p2_candidates=p2_cands,
        p1_references=p1_refs,
        p2_references=p2_refs,
        oop_proxy_f1=0.149,
        chance_mean_f1=0.0666,
    )

    gate = gate_result["gate"]
    p1_res = gate_result["period1_fit"]
    p2_res = gate_result["period2_heldout"]

    print("\nRESULTS:")
    print(f"  Period 1 (Fit):     F1 = {p1_res['f1']:.4f} (TP={p1_res['tp']}/{p1_res['n_ref']}, Prec={p1_res['precision']:.3f}, Rec={p1_res['recall']:.3f})")
    print(f"  Period 2 (Heldout): F1 = {p2_res['f1']:.4f} (TP={p2_res['tp']}/{p2_res['n_ref']}, Prec={p2_res['precision']:.3f}, Rec={p2_res['recall']:.3f})")
    print("\nPRE-REGISTERED GATE CHECKS:")
    print(f"  S1: Period 2 F1 >= 0.250:           {gate['S1_actual']:.4f} -> {'PASS' if gate['S1_f1_ge_0_25'] else 'FAIL'}")
    print(f"  S2: Ratio to Chance (>= 2.0x):       {gate['S2_actual_ratio']:.2f}x -> {'PASS' if gate['S2_chance_ratio_ge_2_0'] else 'FAIL'}")
    print(f"  S3: Beats OutOfPlay-Proxy (0.149):   +{gate['S3_actual_diff']:.4f} -> {'PASS' if gate['S3_beats_oop_proxy'] else 'FAIL'}")
    print(f"\nGATE VERDICT: {gate['verdict']}")
    print("=" * 70)

    # Save artifact
    out_path = REPO / "backend/.local/artifacts/mosaic/gate_shot_physics.json"
    out_path.write_text(json.dumps(gate_result, indent=2))
    print(f"Saved artifact to {out_path}")

    if gate["verdict"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
