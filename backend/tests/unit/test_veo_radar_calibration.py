"""Unit tests for Veo Camera Calibration and 2D Pitch Radar projection."""

import numpy as np
import pytest

from backend.src.domain.models.match import RadarBall, RadarFrame, RadarPlayer
from backend.src.services.pipeline.radar_calibrator import CalibratedPitchRadar
from backend.src.services.pipeline.veo_calibrator import VeoCameraModel


@pytest.fixture
def sample_camera_model():
    """Rigid 3D camera model matching Skyline / Veo Cam 2 specs."""
    # Camera at X=2.97m, Y=-5.63m (5.63m high), Z=-37.08m (4.16m behind touchline)
    # Looking down at pitch center with identity/near-identity rotation
    c2w = np.eye(4, dtype=np.float64)
    c2w[0, 3] = 2.9667
    c2w[1, 3] = -5.6284
    c2w[2, 3] = -37.0847
    return VeoCameraModel(
        camera2world=c2w,
        field_length=105.0,
        field_width=65.8535,
    )


@pytest.fixture
def sample_calibrator(sample_camera_model):
    """Instantiate CalibratedPitchRadar with synthetic camera keyframes and ball track."""
    cameras = [
        {
            "t": 10.0,
            "focal": 1000.0,
            "ppx": 640.0,
            "ppy": 360.0,
            "aspect": 1.0,
            "R": np.eye(3).tolist(),
        },
        {
            "t": 20.0,
            "focal": 1200.0,
            "ppx": 640.0,
            "ppy": 360.0,
            "aspect": 1.0,
            "R": np.eye(3).tolist(),
        },
    ]
    ball_track = [
        {"t": 10.0, "u": 2104.1, "v": 507.5, "conf": 0.8},
        {"t": 10.5, "u": 2150.0, "v": 510.0, "conf": 0.85},
    ]
    return CalibratedPitchRadar(
        camera_model=sample_camera_model,
        cameras=cameras,
        scale=1139.0,
        origin=(-1915.0, 1480.0),
        ball_track=ball_track,
        team_lightness_threshold=120.0,
    )


def test_veo_camera_model_center_spot_and_radar(sample_camera_model):
    """Verify origin (0, 0) maps to center spot (52.5, 34.0) on radar."""
    rx, ry = sample_camera_model.ground_to_radar(0.0, 0.0)
    assert pytest.approx(rx, abs=0.01) == 52.5
    assert pytest.approx(ry, abs=0.01) == 34.0


def test_veo_camera_model_sky_ray_rejection(sample_camera_model):
    """A ray pointing upward toward the sky must return None, not a bogus position."""
    sky_ray = np.array([0.0, -1.0, 0.5])  # Negative Y points up into sky
    sky_ray /= np.linalg.norm(sky_ray)
    pt = sample_camera_model.camera_ray_to_ground(sky_ray)
    assert pt is None


def test_veo_camera_model_frame_pixel_to_radar(sample_camera_model):
    """Verify projecting a ground-directed pixel produces valid radar bounds."""
    K = np.array([[1000.0, 0.0, 640.0], [0.0, 1000.0, 360.0], [0.0, 0.0, 1.0]])
    R = np.eye(3)
    # Bottom center pixel looking at turf
    radar_pt = sample_camera_model.frame_pixel_to_radar(640.0, 700.0, K, R)
    assert radar_pt is not None
    rx, ry = radar_pt
    assert 0.0 <= rx <= 105.0
    assert 0.0 <= ry <= 68.0


def test_calibrator_camera_lookup(sample_calibrator):
    """Verify finding nearest camera keyframe."""
    cam1 = sample_calibrator.get_camera_at(11.0)
    assert cam1["t"] == 10.0

    cam2 = sample_calibrator.get_camera_at(18.5)
    assert cam2["t"] == 20.0


def test_calibrator_team_classification(sample_calibrator):
    """Verify CIELAB L* separation: L > 120 is away, L <= 120 is home."""
    dark_shirt = {"lab": [85.0, 130.0, 120.0]}
    light_shirt = {"lab": [180.0, 128.0, 128.0]}

    assert sample_calibrator.classify_team(dark_shirt) == "home"
    assert sample_calibrator.classify_team(light_shirt) == "away"
    # Null shirt defaults safely to home
    assert sample_calibrator.classify_team(None) == "home"


def test_calibrator_ball_honesty_rule(sample_calibrator):
    """When ball is present, detected=True; when absent, detected=False without asserting a lie."""
    # Near t=10.0: ball exists
    b_found = sample_calibrator.get_ball_at(10.0, max_dt=0.3)
    assert b_found.detected is True
    assert 0.0 <= b_found.x <= 105.0
    assert 0.0 <= b_found.y <= 68.0

    # At t=999.0: no ball was tracked, must assert detected=False
    b_missing = sample_calibrator.get_ball_at(999.0, max_dt=0.3)
    assert b_missing.detected is False


def test_calibrator_calibrate_frame_pipeline(sample_calibrator):
    """Verify full frame conversion into a valid RadarFrame."""
    frame_det = {
        "t": 10.0,
        "w": 1280,
        "h": 720,
        "boxes": [
            {
                "box": [600.0, 400.0, 640.0, 480.0],
                "conf": 0.88,
                "shirt": {"lab": [90.0, 120.0, 130.0]},
            },
            {
                "box": [700.0, 410.0, 740.0, 490.0],
                "conf": 0.85,
                "shirt": {"lab": [185.0, 128.0, 128.0]},
            },
            {
                # Very low confidence box should be filtered out
                "box": [100.0, 100.0, 120.0, 140.0],
                "conf": 0.2,
                "shirt": {"lab": [100.0, 128.0, 128.0]},
            },
        ],
    }

    rf = sample_calibrator.calibrate_frame(frame_det, min_conf=0.4)
    assert rf is not None
    assert isinstance(rf, RadarFrame)
    assert rf.timestamp == 10.0
    # Two high-confidence players kept
    assert len(rf.players) == 2
    assert rf.players[0].team == "home"
    assert rf.players[1].team == "away"
    for p in rf.players:
        assert 0.0 <= p.x <= 105.0
        assert 0.0 <= p.y <= 68.0

    # Ball is tracked at t=10.0
    assert rf.ball.detected is True
