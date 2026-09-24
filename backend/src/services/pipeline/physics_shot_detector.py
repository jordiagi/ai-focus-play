"""Physics-Based 3D Goal-Directed Shot Detection Engine.

Replaces the falsified 1D panorama pixel detector (P1) by projecting ball trajectories
into metric pitch coordinates [0, 105]m x [0, 68]m via VeoCameraModel and evaluating:
1. Goal-directed trajectory cone (|theta| <= 31 deg, cos >= 0.85 toward target goal mouth).
2. Metric velocity threshold (v >= 8.0 m/s).
3. Attacking third spatial confinement (dist_to_goal <= 32.0m).
4. Non-maximum suppression over 8.0s window.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np


@dataclass
class ShotCandidate:
    timestamp: float
    period: int
    speed_mps: float
    dist_to_goal_m: float
    goal_alignment_cos: float
    target_goal: str  # 'left' or 'right'
    confidence: float


class PhysicsShotDetector:
    """Detects goal-directed shots using metric pitch kinematics."""

    def __init__(
        self,
        min_speed_mps: float = 8.0,
        max_goal_dist_m: float = 32.0,
        min_cone_cos: float = 0.85,
        nms_window_s: float = 8.0,
        pitch_length_m: float = 105.0,
        pitch_width_m: float = 68.0,
    ):
        self.min_speed_mps = float(min_speed_mps)
        self.max_goal_dist_m = float(max_goal_dist_m)
        self.min_cone_cos = float(min_cone_cos)
        self.nms_window_s = float(nms_window_s)
        self.pitch_length_m = float(pitch_length_m)
        self.pitch_width_m = float(pitch_width_m)
        self.goal_y_m = self.pitch_width_m / 2.0  # 34.0m

    def detect_from_metric_track(
        self,
        track_points: List[Tuple[float, float, float]],
        p1_bounds: Tuple[float, float] = (562.3, 2879.3),
        p2_bounds: Tuple[float, float] = (3674.4, 6132.1),
    ) -> List[ShotCandidate]:
        """Detect shots from a sequence of sorted (t_sec, x_m, y_m) points."""
        if len(track_points) < 2:
            return []

        pts = sorted(track_points, key=lambda p: p[0])
        raw_candidates: List[ShotCandidate] = []

        for i in range(1, len(pts)):
            t0, x0, y0 = pts[i - 1]
            t1, x1, y1 = pts[i]
            dt = t1 - t0

            # Velocity window gating: 50ms <= dt <= 600ms
            if dt < 0.05 or dt > 0.60:
                continue

            vx = (x1 - x0) / dt
            vy = (y1 - y0) / dt
            speed = math.sqrt(vx * vx + vy * vy)
            if speed < self.min_speed_mps:
                continue

            # Determine match period
            if p1_bounds[0] <= t0 <= p1_bounds[1]:
                period = 1
            elif p2_bounds[0] <= t0 <= p2_bounds[1]:
                period = 2
            else:
                continue

            # Evaluate trajectory against left (X=0) and right (X=105) goal mouths
            goals = [
                (0.0, self.goal_y_m, "left"),
                (self.pitch_length_m, self.goal_y_m, "right"),
            ]
            for gx, gy, label in goals:
                dx_g = gx - x0
                dy_g = gy - y0
                dist_g = math.sqrt(dx_g * dx_g + dy_g * dy_g)
                if dist_g > self.max_goal_dist_m:
                    continue

                dot = vx * dx_g + vy * dy_g
                cos_ang = dot / (speed * dist_g)
                if cos_ang >= self.min_cone_cos:
                    # Confidence heuristic: product of speed and directional alignment
                    conf = min(1.0, (speed / 15.0) * cos_ang)
                    raw_candidates.append(
                        ShotCandidate(
                            timestamp=round(t0, 2),
                            period=period,
                            speed_mps=round(speed, 2),
                            dist_to_goal_m=round(dist_g, 2),
                            goal_alignment_cos=round(cos_ang, 4),
                            target_goal=label,
                            confidence=round(conf, 4),
                        )
                    )

        # Non-maximum suppression over temporal window
        # Sort candidates descending by confidence / speed
        raw_candidates.sort(key=lambda c: -c.confidence)
        suppressed: List[ShotCandidate] = []
        for c in raw_candidates:
            if not any(abs(c.timestamp - s.timestamp) < self.nms_window_s for s in suppressed):
                suppressed.append(c)

        suppressed.sort(key=lambda c: c.timestamp)
        return suppressed

    @staticmethod
    def evaluate(
        candidates: List[ShotCandidate],
        references: List[Dict[str, Any]],
        tolerance_s: float = 15.0,
    ) -> Dict[str, Any]:
        """Evaluate predicted shot timestamps against ground-truth references."""
        tp = 0
        matched_refs = set()
        matched_preds = set()

        for i, c in enumerate(candidates):
            for j, r in enumerate(references):
                ref_t = float(r.get("video_s", r.get("time_s", 0.0)))
                if j not in matched_refs and abs(c.timestamp - ref_t) <= tolerance_s:
                    tp += 1
                    matched_refs.add(j)
                    matched_preds.add(i)
                    break

        n_pred = len(candidates)
        n_ref = len(references)
        prec = tp / n_pred if n_pred > 0 else 0.0
        rec = tp / n_ref if n_ref > 0 else 0.0
        f1 = (2.0 * prec * rec / (prec + rec)) if (prec + rec) > 0.0 else 0.0

        return {
            "n_pred": n_pred,
            "n_ref": n_ref,
            "tp": tp,
            "fp": n_pred - tp,
            "fn": n_ref - tp,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        }

    def evaluate_gate(
        self,
        p1_candidates: List[ShotCandidate],
        p2_candidates: List[ShotCandidate],
        p1_references: List[Dict[str, Any]],
        p2_references: List[Dict[str, Any]],
        oop_proxy_f1: float = 0.149,
        chance_mean_f1: float = 0.0666,
        s1_f1_floor: float = 0.25,
        s2_chance_ratio_floor: float = 2.0,
    ) -> Dict[str, Any]:
        """Verify the pre-registered requirements for FootballShot gate."""
        p1_score = self.evaluate(p1_candidates, p1_references)
        p2_score = self.evaluate(p2_candidates, p2_references)

        p2_f1 = p2_score["f1"]
        ratio_to_chance = p2_f1 / chance_mean_f1 if chance_mean_f1 > 0 else 0.0
        beats_oop = p2_f1 > oop_proxy_f1

        s1_passed = p2_f1 >= s1_f1_floor
        s2_passed = ratio_to_chance >= s2_chance_ratio_floor
        s3_passed = beats_oop

        passed_all = s1_passed and s2_passed and s3_passed

        return {
            "period1_fit": p1_score,
            "period2_heldout": p2_score,
            "gate": {
                "S1_f1_ge_0_25": s1_passed,
                "S1_actual": p2_f1,
                "S2_chance_ratio_ge_2_0": s2_passed,
                "S2_actual_ratio": round(ratio_to_chance, 2),
                "S3_beats_oop_proxy": s3_passed,
                "S3_actual_diff": round(p2_f1 - oop_proxy_f1, 4),
                "verdict": "PASS" if passed_all else "FAIL",
            },
        }
