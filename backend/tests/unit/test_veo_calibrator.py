from pathlib import Path
import pytest
import numpy as np
from backend.src.services.pipeline.veo_calibrator import VeoCameraModel

REPO = Path(__file__).resolve().parents[3]
SKYLINE_VEO = REPO / "benchmarks" / "raw" / "skyline_camera_alignment.veo"
BALTIMORE_VEO = REPO / "benchmarks" / "raw" / "baltimore_armor_camera_alignment.veo"


def test_load_skyline_camera_model():
    model = VeoCameraModel.from_veo_file(SKYLINE_VEO)
    # Pole height is 5.63m
    assert abs(model.camera_height - 5.628) < 0.05
    # Standoff behind sideline is ~4.16m
    assert abs(model.touchline_standoff - 4.158) < 0.05
    assert model.field_length == 105.0
    assert abs(model.field_width - 65.85) < 0.1


def test_load_baltimore_armor_camera_model():
    model = VeoCameraModel.from_veo_file(BALTIMORE_VEO)
    # Baltimore Armor camera height is 4.22m
    assert abs(model.camera_height - 4.223) < 0.05
    assert model.field_length == 105.0
    assert abs(model.field_width - 67.72) < 0.1


def test_ground_ray_ground_round_trip():
    model = VeoCameraModel.from_veo_file(SKYLINE_VEO)
    
    # Test various ground points on the pitch
    test_points = [
        (0.0, 0.0),       # Centre spot
        (25.0, 10.0),     # Midfield right
        (-40.0, -15.0),   # Defensive left
        (52.5, 32.9),     # Far corner
        (-52.5, -32.9),   # Near corner
    ]
    
    for x_m, z_m in test_points:
        ray = model.ground_to_camera_ray(x_m, z_m)
        assert abs(np.linalg.norm(ray) - 1.0) < 1e-6
        
        proj = model.camera_ray_to_ground(ray)
        assert proj is not None
        proj_x, proj_z = proj
        assert abs(proj_x - x_m) < 1e-4, f"Mismatch on X: {proj_x} vs {x_m}"
        assert abs(proj_z - z_m) < 1e-4, f"Mismatch on Z: {proj_z} vs {z_m}"


def test_normalized_coordinate_conversion():
    model = VeoCameraModel.from_veo_file(SKYLINE_VEO)
    
    # Centre spot (0.5, 0.5) should be (0.0m, 0.0m)
    x_m, z_m = model.normalized_to_metric(0.5, 0.5)
    assert abs(x_m) < 1e-6 and abs(z_m) < 1e-6
    
    x_norm, z_norm = model.metric_to_normalized(0.0, 0.0)
    assert abs(x_norm - 0.5) < 1e-6 and abs(z_norm - 0.5) < 1e-6
    
    # Boundary points
    top_right_m = (105.0 / 2, 65.85356 / 2)
    xn, zn = model.metric_to_normalized(*top_right_m)
    assert abs(xn - 1.0) < 1e-4 and abs(zn - 1.0) < 1e-4


def test_ray_above_horizon_returns_none():
    model = VeoCameraModel.from_veo_file(SKYLINE_VEO)
    # A ray pointing away from the turf plane (negative Y in world) will never hit Y=0 with t > 0
    d_world_away = np.array([0.0, -1.0, 0.0])
    d_cam = model.R_w2c @ d_world_away
    assert model.camera_ray_to_ground(d_cam) is None
