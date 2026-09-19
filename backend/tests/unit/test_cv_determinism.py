from pathlib import Path

import cv2
import numpy as np

from backend.src.services.pipeline.cv_engine import SoccerCVEngine
from backend.src.services.pipeline.tracker import SoccerTracker


class _SyntheticCapture:
    def __init__(self, frames):
        self._frames = [frame.copy() for frame in frames]
        self._index = 0

    def isOpened(self):
        return self._index < len(self._frames)

    def read(self):
        if not self.isOpened():
            return False, None
        frame = self._frames[self._index]
        self._index += 1
        return True, frame

    def get(self, prop):
        if prop == cv2.CAP_PROP_FPS:
            return 2.0
        if prop == cv2.CAP_PROP_FRAME_COUNT:
            return float(len(self._frames))
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return float(self._frames[0].shape[1])
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return float(self._frames[0].shape[0])
        return 0.0

    def release(self):
        pass


def _match_frames(left_color, right_color):
    frames = []
    for _ in range(18):
        frame = np.full((360, 640, 3), (45, 120, 45), dtype=np.uint8)
        cv2.rectangle(frame, (145, 135), (175, 255), left_color, -1)
        cv2.rectangle(frame, (465, 135), (495, 255), right_color, -1)
        frames.append(frame)
    return frames


def _labels(engine, monkeypatch, frames):
    monkeypatch.setattr(cv2, "VideoCapture", lambda _path: _SyntheticCapture(frames))
    radar_frames, _, _, _ = engine.process_video(Path("synthetic.mp4"))
    return [[player.team for player in frame.players] for frame in radar_frames]


def test_same_input_has_identical_team_labels_across_five_runs(monkeypatch):
    frames = _match_frames((20, 20, 220), (220, 40, 20))
    engine = SoccerCVEngine()

    runs = [_labels(engine, monkeypatch, frames) for _ in range(5)]

    assert sorted(runs[0][-1]) == ["away", "home"]
    assert all(run == runs[0] for run in runs[1:])


def test_second_match_is_independent_of_first_match(monkeypatch):
    first = _match_frames((20, 20, 220), (220, 40, 20))
    second = _match_frames((0, 255, 255), (255, 0, 255))

    shared_engine = SoccerCVEngine()
    _labels(shared_engine, monkeypatch, first)
    first_centers = shared_engine.team_centers.copy()
    after_first = _labels(shared_engine, monkeypatch, second)
    second_centers = shared_engine.team_centers.copy()
    alone = _labels(SoccerCVEngine(), monkeypatch, second)

    assert not np.array_equal(first_centers, second_centers)
    assert sorted(after_first[-1]) == ["away", "home"]
    assert after_first == alone


def test_lime_and_yellow_torsos_survive_grass_mask():
    engine = SoccerCVEngine()
    grass = np.full((100, 100, 3), (45, 120, 45), dtype=np.uint8)

    for kit_color in ((0, 255, 128), (0, 255, 255)):
        patch = grass.copy()
        patch[20:80, 20:80] = kit_color
        assert engine._extract_torso_chroma(patch, 20, 20, 60, 60) is not None

    grass_hsv = cv2.cvtColor(grass, cv2.COLOR_BGR2HSV)
    assert np.all(engine._grass_mask(grass_hsv) == 255)


def test_fresh_noise_never_renders_beside_persistent_player():
    tracker = SoccerTracker(max_match_distance=2.0, max_misses=2)

    for frame_index in range(6):
        detections = [
            {"x": 20.0 + frame_index * 0.2, "y": 30.0, "team": "home"},
            {"x": 60.0 + frame_index * 7.0, "y": 10.0, "team": "away"},
        ]
        players = tracker.update(detections, dt=0.5)
        if frame_index >= 2:
            assert len(players) == 1
            assert players[0].team == "home"


def test_coasted_ball_coordinates_are_bounded_and_not_detected(monkeypatch):
    frames = _match_frames((20, 20, 220), (220, 40, 20))
    cv2.circle(frames[0], (320, 200), 8, (255, 255, 255), -1)

    class _OutOfBoundsKalman:
        def predict(self):
            return np.array([[130.1], [-4.2], [0.0], [0.0]], dtype=np.float32)

        def correct(self, _measurement):
            pass

    engine = SoccerCVEngine()
    monkeypatch.setattr(engine, "_setup_ball_kalman", lambda: _OutOfBoundsKalman())
    radar_frames = _labels_with_frames(engine, monkeypatch, frames)

    assert radar_frames[0].ball.detected is True
    assert radar_frames[1].ball.detected is False
    assert all(0.0 <= frame.ball.x <= 105.0 for frame in radar_frames)
    assert all(0.0 <= frame.ball.y <= 68.0 for frame in radar_frames)


def _labels_with_frames(engine, monkeypatch, frames):
    monkeypatch.setattr(cv2, "VideoCapture", lambda _path: _SyntheticCapture(frames))
    radar_frames, _, _, _ = engine.process_video(Path("synthetic.mp4"))
    return radar_frames
