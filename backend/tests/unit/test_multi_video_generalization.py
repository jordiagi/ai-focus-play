from pathlib import Path
import pytest
from backend.src.services.pipeline.cv_engine import SoccerCVEngine
from backend.src.services.pipeline.veo_calibrator import VeoCameraModel

REPO = Path(__file__).resolve().parents[3]
SAMPLE_PATH = REPO / "backend" / ".local" / "media" / "baltimore_armor_sample_30s.mp4"
BALTIMORE_VEO = REPO / "benchmarks" / "raw" / "baltimore_armor_camera_alignment.veo"


def test_baltimore_armor_sample_exists():
    assert SAMPLE_PATH.exists(), f"Missing Baltimore Armor test clip at {SAMPLE_PATH}"


def test_cv_engine_generalization_on_baltimore_armor():
    """Verify CV pipeline processes a second independent match footage without crash or data leakage."""
    engine = SoccerCVEngine()
    radar_frames, events, highlights, analytics = engine.process_video(
        video_path=SAMPLE_PATH,
        home_team="Arlington SA U16B ECNL",
        away_team="Baltimore Armor",
    )

    assert len(radar_frames) >= 30, f"Expected at least 30 radar frames, got {len(radar_frames)}"
    assert analytics is not None

    # Check radar frame structure
    for frame in radar_frames[:10]:
        assert 0.0 <= frame.ball.x <= 105.0
        assert 0.0 <= frame.ball.y <= 68.0
        for p in frame.players:
            assert 0.0 <= p.x <= 105.0
            assert 0.0 <= p.y <= 68.0
            assert p.team in ["home", "away"]


def test_baltimore_armor_camera_projection():
    """Verify VeoCameraModel projections on Baltimore Armor camera parameters."""
    model = VeoCameraModel.from_veo_file(BALTIMORE_VEO)
    assert abs(model.camera_height - 4.223) < 0.05
    assert abs(model.field_width - 67.72) < 0.1

    # Centre spot projection test
    ray_centre = model.ground_to_camera_ray(0.0, 0.0)
    ground_pt = model.camera_ray_to_ground(ray_centre)
    assert ground_pt is not None
    assert abs(ground_pt[0]) < 1e-4 and abs(ground_pt[1]) < 1e-4
