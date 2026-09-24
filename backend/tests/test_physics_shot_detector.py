"""Unit tests for PhysicsShotDetector."""

import pytest
from backend.src.services.pipeline.physics_shot_detector import PhysicsShotDetector, ShotCandidate


def test_shot_detector_empty_track():
    detector = PhysicsShotDetector()
    cands = detector.detect_from_metric_track([])
    assert cands == []


def test_shot_detector_detects_goal_directed_shot():
    detector = PhysicsShotDetector(min_speed_mps=8.0, max_goal_dist_m=32.0, min_cone_cos=0.85)

    # Ball travelling fast toward left goal (0, 34) in Period 1
    # Starting at (20m, 34m) -> (18m, 34m) in 0.1s => speed = 20 m/s toward left
    track = [
        (600.0, 20.0, 34.0),
        (600.1, 18.0, 34.0),
        (600.2, 16.0, 34.0),
    ]
    cands = detector.detect_from_metric_track(track)
    assert len(cands) == 1
    shot = cands[0]
    assert shot.period == 1
    assert shot.target_goal == "left"
    assert shot.speed_mps >= 15.0
    assert shot.goal_alignment_cos > 0.99


def test_shot_detector_rejects_clearance_away_from_goal():
    detector = PhysicsShotDetector(min_speed_mps=8.0, max_goal_dist_m=32.0, min_cone_cos=0.85)

    # Ball travelling AWAY from left goal: starting at (16m, 34m) -> (20m, 34m)
    track = [
        (600.0, 16.0, 34.0),
        (600.1, 18.0, 34.0),
        (600.2, 20.0, 34.0),
    ]
    cands = detector.detect_from_metric_track(track)
    # Target goal (0, 34) has velocity pointing opposite: rejected
    # Right goal (105, 34) is > 32m away: rejected
    assert len(cands) == 0


def test_shot_detector_gate_evaluation():
    detector = PhysicsShotDetector()
    p1_c = [ShotCandidate(600.0, 1, 15.0, 18.0, 0.95, "right", 0.9)]
    p2_c = [ShotCandidate(3700.0, 2, 16.0, 15.0, 0.98, "left", 0.95)]

    p1_r = [{"video_s": 602.0}]
    p2_r = [{"video_s": 3701.0}]

    gate_eval = detector.evaluate_gate(
        p1_candidates=p1_c,
        p2_candidates=p2_c,
        p1_references=p1_r,
        p2_references=p2_r,
        oop_proxy_f1=0.149,
        chance_mean_f1=0.0666,
    )
    assert gate_eval["gate"]["verdict"] == "PASS"
    assert gate_eval["gate"]["S1_f1_ge_0_25"] is True
    assert gate_eval["period2_heldout"]["f1"] == 1.0
