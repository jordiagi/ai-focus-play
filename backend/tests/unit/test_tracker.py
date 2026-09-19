import pytest
from backend.src.services.pipeline.tracker import SoccerTracker

def test_tracker_identity_stability_and_crossing():
    """Two players walking past each other maintain distinct, stable IDs throughout."""
    tracker = SoccerTracker(max_match_distance=4.0, max_misses=6)

    # Player 1 moves from (20, 30) to (50, 30) at ~3 m/s
    # Player 2 moves from (50, 30) to (20, 30) at ~3 m/s
    dt = 0.5
    frames = 11

    p1_ids = []
    p2_ids = []

    for i in range(frames):
        x1 = 20.0 + i * 3.0
        y1 = 30.0
        x2 = 50.0 - i * 3.0
        y2 = 30.0

        detections = [
            {"x": x1, "y": y1, "team": "home", "jersey": "10"},
            {"x": x2, "y": y2, "team": "away", "jersey": "4"}
        ]

        players = tracker.update(detections, dt=dt)
        if i == 0:
            assert players == []
            continue

        # Find player closest to x1 and x2 after two-hit confirmation.
        p1 = min(players, key=lambda p: abs(p.x - x1) + abs(p.y - y1))
        p2 = min(players, key=lambda p: abs(p.x - x2) + abs(p.y - y2))

        p1_ids.append(p1.id)
        p2_ids.append(p2.id)

    # Initial IDs after confirmation
    confirmed_p1_id = p1_ids[0]
    confirmed_p2_id = p2_ids[0]

    assert confirmed_p1_id != confirmed_p2_id
    # Assert ID maintained after crossing at frame 5 (x1 ~ x2 ~ 35)
    assert p1_ids[-1] == confirmed_p1_id
    assert p2_ids[-1] == confirmed_p2_id

def test_tracker_removes_dead_tracks():
    tracker = SoccerTracker(max_match_distance=4.0, max_misses=3)
    # Detect 1 player for 2 frames
    tracker.update([{"x": 10.0, "y": 10.0, "team": "home"}], dt=0.5)
    players = tracker.update([{"x": 11.0, "y": 10.0, "team": "home"}], dt=0.5)
    assert len(players) == 1

    # 4 frames of no detections -> track should die
    for _ in range(4):
        players = tracker.update([], dt=0.5)

    assert len(players) == 0
