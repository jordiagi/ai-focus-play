"""Unit tests for Foot-Contact Association and Tier B spatial masking."""

import numpy as np
import pytest

from backend.src.services.pipeline.gpu_job.mosaic.gate_association_fps import (
    fit_and_score,
    route_foot_contact,
    route_last_contact,
)


def test_foot_contact_rejects_airborne_ball():
    """Verify that a ball passing at player head/chest level is ignored by foot_contact.

    Whole-body 2D containment (route_last_contact) falsely attributes it, while
    route_foot_contact correctly rejects it as airborne transit.
    """
    # Player bounding box: [x1=100, y1=200, x2=150, y2=400] -> height=200px
    # Upper chest/head level: y=230px
    # Feet level: y=380..400px
    pl = {
        10.0: {
            "boxes": [
                {
                    "box": [100.0, 200.0, 150.0, 400.0],
                    "shirt": {"lab": [90.0, 128.0, 128.0]},
                }
            ]
        }
    }

    # Case 1: Airborne ball at chest level (y=230)
    ball_airborne = {10.0: {"c": [[125.0, 230.0, 10.0, 0.9]]}}
    # Whole-body accepts it (conflating 3D height)
    assert route_last_contact(10.0, pl, ball_airborne, [10.0], pad=0.1) == 90.0
    # Foot-contact rejects it (recognizing no turf contact)
    assert route_foot_contact(10.0, pl, ball_airborne, [10.0], foot_pct=0.15) is None

    # Case 2: Grounded ball at feet level (y=390)
    ball_ground = {10.0: {"c": [[125.0, 390.0, 10.0, 0.9]]}}
    assert route_foot_contact(10.0, pl, ball_ground, [10.0], foot_pct=0.15) == 90.0


def test_foot_contact_gate_evaluation():
    """Verify fit_and_score evaluation semantics with majority and balanced baselines."""
    # Synthetic dataset with realistic spread: Own ~80-95, Opponent ~160-175
    p1_rec = [{"team": "Own", "L": l, "p": 1} for l in [80.0, 85.0, 90.0, 82.0, 88.0, 92.0, 84.0, 86.0]] + \
             [{"team": "Opponent", "L": l, "p": 1} for l in [160.0, 165.0, 170.0, 162.0, 168.0, 172.0, 164.0, 166.0]]
    p2_rec = [{"team": "Own", "L": l, "p": 2} for l in [81.0, 86.0, 91.0, 83.0, 89.0, 93.0, 85.0, 87.0]] + \
             [{"team": "Opponent", "L": l, "p": 2} for l in [161.0, 166.0, 171.0, 163.0, 169.0, 173.0, 165.0, 167.0]]
    rec = p1_rec + p2_rec

    sc = fit_and_score(rec)
    assert sc is not None
    assert sc["period1_acc"] == 1.0
    assert sc["period2_acc"] == 1.0
    assert sc["beats_majority"] is True
    assert sc["beats_balanced_floor"] is True
    assert sc["PASSES_GATE"] is True
