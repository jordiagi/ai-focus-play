import pytest
from backend.src.services.pipeline.cv_engine import SoccerCVEngine
from backend.src.domain.models.match import RadarFrame, RadarPlayer, RadarBall, Event

def test_analytics_matches_emitted_events():
    engine = SoccerCVEngine()

    # Create synthetic events
    events = [
        Event(match_id="test", timestamp=10.0, period=1, event_type="Kickoff", team="home", description="Kickoff", pitch_x=52.5, pitch_y=34.0),
        Event(match_id="test", timestamp=20.0, period=1, event_type="Goal", team="home", description="Goal 1", pitch_x=98.0, pitch_y=32.0),
        Event(match_id="test", timestamp=35.0, period=1, event_type="Shot", team="home", description="Shot 1", pitch_x=88.0, pitch_y=30.0),
        Event(match_id="test", timestamp=50.0, period=2, event_type="Goal", team="away", description="Goal 2", pitch_x=12.0, pitch_y=34.0),
        Event(match_id="test", timestamp=65.0, period=2, event_type="Shot", team="away", description="Shot 2", pitch_x=15.0, pitch_y=28.0),
    ]

    # Create dummy radar frames
    radar_frames = []
    for t in range(0, 80, 5):
        radar_frames.append(RadarFrame(
            timestamp=float(t),
            players=[
                RadarPlayer(id=1, team="home", x=50.0, y=30.0, speed=2.0),
                RadarPlayer(id=2, team="away", x=55.0, y=30.0, speed=2.0),
            ],
            ball=RadarBall(x=50.5, y=30.0, z=0.0, detected=True)
        ))

    home_positions = [(50.0, 30.0)] * 10
    away_positions = [(55.0, 30.0)] * 10

    analytics = engine._calculate_analytics(radar_frames, events, home_positions, away_positions, sample_fps=0.2)

    # 1. Goals match exactly
    assert analytics.home_stats.goals == 1
    assert analytics.away_stats.goals == 1

    # 2. Shots match exactly (Shots + Goals)
    assert analytics.home_stats.shots == 2
    assert analytics.away_stats.shots == 2

    # 3. Shot map length equals count of shot and goal events
    assert len(analytics.shot_map) == 4
    for shot in analytics.shot_map:
        assert shot.timestamp <= 80.0

    # 4. Unmeasured stats are None, not invented numbers (P1-4)
    assert analytics.home_stats.tackles is None
    assert analytics.home_stats.passes_completed is None
    assert analytics.home_stats.fouls is None
