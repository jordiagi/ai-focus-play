"""Unit tests for Phase 2 Autonomous CV Pipeline modules (WPs G9, G10, G11)."""

import pytest
import numpy as np

from backend.src.services.pipeline.pitch_homography import PitchHomography, DynamicHomographyTracker
from backend.src.services.pipeline.tracklet_tracker import TrackletTracker, Tracklet, PlayerDetection
from backend.src.services.pipeline.turf_possession import TurfPossessionEngine
from backend.src.services.pipeline.jersey_ocr import JerseyDigitOCR, JerseyVoteAggregator


def test_pitch_homography_canonical_prior():
    """Verify canonical broadcast homography maps frame pixels to valid turf coordinates."""
    homography = PitchHomography.canonical_broadcast_prior(1920, 1080)
    assert homography.H is not None

    # Test center of frame
    turf_pt = homography.project_point(960.0, 540.0)
    assert turf_pt is not None
    x, y = turf_pt
    assert 0.0 <= x <= 105.0
    assert 0.0 <= y <= 68.0

    # Test player bbox projection
    bbox = [940.0, 500.0, 980.0, 600.0, 0.9]
    foot_turf = homography.project_player_bbox(bbox)
    assert foot_turf is not None
    assert 0.0 <= foot_turf[0] <= 105.0
    assert 0.0 <= foot_turf[1] <= 68.0


def test_dynamic_homography_tracker():
    """Verify interpolation between camera anchors."""
    tracker = DynamicHomographyTracker()
    h1 = PitchHomography.canonical_broadcast_prior()
    h2 = PitchHomography.canonical_broadcast_prior()
    tracker.add_anchor(100.0, h1)
    tracker.add_anchor(200.0, h2)

    interp_h = tracker.get_homography_at(150.0)
    assert interp_h is not None
    pt = interp_h.project_point(960.0, 540.0)
    assert pt is not None


def test_dynamic_homography_tracker_from_registration():
    """Verify initialization from registration artifact greedy anchors."""
    reg_data = {
        "greedy_anchors": {
            "curve": [
                {"anchors": 1, "anchor_t": 4888.0, "covered": 56},
                {"anchors": 2, "anchor_t": 1048.0, "covered": 58},
                {"anchors": 3, "anchor_t": 808.0, "covered": 59},
            ]
        }
    }
    tracker = DynamicHomographyTracker.from_registration(reg_data)
    assert len(tracker.anchors) == 3
    assert 808.0 in tracker.anchors
    assert 1048.0 in tracker.anchors
    assert 4888.0 in tracker.anchors

    h_at = tracker.get_homography_at(900.0)
    assert h_at is not None
    assert h_at.project_point(960.0, 540.0) is not None


def test_tracklet_tracker():
    """Verify multi-frame player tracking and roster building."""
    tracker = TrackletTracker()

    # Create synthetic sequence: 2 players moving across 5 frames
    frames = []
    for i in range(5):
        t = float(i)
        # Player 1 (home side) moves slightly
        b1 = [400.0 + i * 2.0, 600.0, 440.0 + i * 2.0, 700.0, 0.9]
        # Player 2 (away side) moves slightly
        b2 = [1400.0 - i * 2.0, 600.0, 1440.0 - i * 2.0, 700.0, 0.9]
        frames.append({"t": t, "boxes": [b1, b2]})

    tracks = tracker.process_frames(frames)
    assert len(tracks) >= 2

    home_roster, away_roster = tracker.build_rosters("Home FC", "Away FC")
    assert len(home_roster) == 11
    assert len(away_roster) == 11
    # Ensure U-2 honesty policy naming
    for p in home_roster + away_roster:
        assert p.name.startswith("Player ")
        assert p.jersey is not None


def test_turf_possession_analytics():
    """Verify possession and pass computation from turf-projected positions."""
    engine = TurfPossessionEngine()

    # Synthetic tracklets: 1 home player, 1 away player
    tlet_home = Tracklet(
        track_id=1,
        team="home",
        jersey_number="10",
        detections=[
            PlayerDetection(bbox=[500, 500, 540, 600, 0.9], timestamp=t, turf_pos=(50.0, 34.0))
            for t in [1.0, 2.0, 3.0, 4.0, 5.0]
        ]
    )
    tlet_away = Tracklet(
        track_id=2,
        team="away",
        jersey_number="9",
        detections=[
            PlayerDetection(bbox=[1200, 500, 1240, 600, 0.9], timestamp=t, turf_pos=(80.0, 34.0))
            for t in [6.0, 7.0, 8.0, 9.0, 10.0]
        ]
    )

    # Ball candidates near home player at t=1..5, near away player at t=6..10
    ball_frames = []
    homography = PitchHomography.canonical_broadcast_prior()
    for t in [1.0, 2.0, 3.0, 4.0, 5.0]:
        ball_frames.append({"t": t, "c": [[960.0, 700.0, 10.0, 0.8]]})
    for t in [6.0, 7.0, 8.0, 9.0, 10.0]:
        ball_frames.append({"t": t, "c": [[1400.0, 700.0, 10.0, 0.8]]})

    analytics = engine.compute_analytics([tlet_home, tlet_away], ball_frames)
    assert "possession_percent" in analytics
    hp = analytics["possession_percent"]["home"]
    ap = analytics["possession_percent"]["away"]
    assert round(hp + ap, 1) == 100.0
    assert len(analytics["pass_strings"]["home"]) == 8
    assert "defensive" in analytics["possession_locations"]["home"]


def test_jersey_digit_ocr_recognition_and_voting():
    """Verify back-of-shirt digit OCR recognition and multi-frame tracklet voting (WP G10 / P2)."""
    import cv2
    ocr = JerseyDigitOCR()

    # Create synthetic torso crops with digit 7 and digit 10
    crop7 = np.zeros((50, 40), dtype=np.uint8)
    cv2.putText(crop7, "7", (10, 38), cv2.FONT_HERSHEY_SIMPLEX, 1.1, 255, 3, cv2.LINE_AA)
    digit7, conf7 = ocr.recognize_crop(crop7)
    assert digit7 == "7"
    assert conf7 >= 0.70

    crop10 = np.zeros((50, 70), dtype=np.uint8)
    cv2.putText(crop10, "10", (8, 38), cv2.FONT_HERSHEY_SIMPLEX, 1.1, 255, 3, cv2.LINE_AA)
    digit10, conf10 = ocr.recognize_crop(crop10)
    assert digit10 == "10"
    assert conf10 >= 0.70

    # Test vote aggregator
    aggregator = JerseyVoteAggregator(min_votes=3, min_confidence=0.65)
    for _ in range(4):
        aggregator.add_observation(track_id=1, jersey="10", confidence=0.85)
    # Stray noise observation
    aggregator.add_observation(track_id=1, jersey="1", confidence=0.70)

    consensus = aggregator.get_consensus(track_id=1)
    assert consensus == "10"

    # Test TrackletTracker with OCR observation
    tracker = TrackletTracker(ocr_engine=ocr)
    frames = [
        {"t": float(i), "boxes": [[400.0, 600.0, 440.0, 700.0, 0.9], [1400.0, 600.0, 1440.0, 700.0, 0.9]]}
        for i in range(5)
    ]
    tracks = tracker.process_frames(frames)
    # Register OCR consensus for track 1
    tracker.add_ocr_observation(track_id=1, jersey="7", confidence=0.90)
    tracker.add_ocr_observation(track_id=1, jersey="7", confidence=0.90)
    tracker.add_ocr_observation(track_id=1, jersey="7", confidence=0.90)
    tracker._assign_jersey_numbers()

    t1 = next(t for t in tracker.completed_tracks if t.track_id == 1)
    assert t1.jersey_number == "7"


def test_autonomous_clip_extractor(tmp_path):
    """Verify autonomous highlight extraction and deduplication (WP G12 / P1)."""
    from backend.src.domain.models.match import Match, Event
    from backend.src.services.pipeline.clip_extractor import AutonomousClipExtractor

    match = Match(
        id="probe-clip-match",
        title="Test Match",
        home_team="Home FC",
        away_team="Away FC",
        date="2026-09-26",
        video_url="/media/test.mp4",
        duration_seconds=500.0,
    )
    events = [
        Event(match_id=match.id, timestamp=50.0, period=1, event_type="Kickoff", team="home", description="Kickoff"),
        Event(match_id=match.id, timestamp=100.0, period=1, event_type="Goal", team="home", confidence=1.0, description="Goal 1"),
        Event(match_id=match.id, timestamp=105.0, period=1, event_type="Goal", team="home", confidence=0.8, description="Goal 2"),  # Within 12s NMS window
        Event(match_id=match.id, timestamp=250.0, period=1, event_type="Shot", team="away", confidence=0.9, description="Shot 1"),
    ]

    extractor = AutonomousClipExtractor(media_dir=tmp_path)
    highlights = extractor.extract_highlight_clips(match, events, max_clips=5)
    assert len(highlights) == 3
    # Check deduplication occurred
    ts_list = [h.start_time for h in highlights]
    assert len(ts_list) == len(set(ts_list))
    # Verify types
    assert any(h.event_type == "goal" for h in highlights)
    assert any(h.event_type == "shot" for h in highlights)
    assert any(h.event_type == "kickoff" for h in highlights)


