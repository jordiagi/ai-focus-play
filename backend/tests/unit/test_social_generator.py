"""Unit tests for SocialRecapGenerator across short, medium, and long formats."""

from backend.src.domain.models.match import Match, AnalyticsData, TeamStats
from backend.src.services.social_generator import SocialRecapGenerator


def test_social_generator_short_length_constraint():
    """Verify Short recap strictly satisfies X/Twitter 280-character boundary."""
    match = Match(
        id="test-match",
        title="Arlington SA U16B ECNL vs. Baltimore Armor",
        home_team="Arlington SA U16B ECNL",
        away_team="Baltimore Armor",
        home_score=3,
        away_score=0,
        date="Sep 6, 2026",
        video_url="/media/demo_match.mp4",
    )
    recaps = SocialRecapGenerator.generate(match)

    assert recaps["match_id"] == "test-match"
    assert recaps["char_count_short"] <= 280
    assert len(recaps["short"]) <= 280
    assert "3 - 0" in recaps["short"]
    assert "#ArlingtonSaU16b" in recaps["short"]


def test_social_generator_medium_and_long_structure():
    """Verify Medium and Long recaps contain narrative, stats, and markdown structure."""
    match = Match(
        id="test-draw",
        title="Arlington SA vs. Skyline U16B ECNL",
        home_team="Arlington SA U16B ECNL",
        away_team="Skyline U16B ECNL",
        home_score=3,
        away_score=3,
        date="Sep 13, 2026",
        video_url="/media/demo_match.mp4",
    )
    analytics = AnalyticsData(
        match_id="test-draw",
        home_stats=TeamStats(possession_percent=62.0, shots=12, goals=3, passes_completed=283, tackles=43),
        away_stats=TeamStats(possession_percent=38.0, shots=13, goals=3, passes_completed=203, tackles=41),
    )
    recaps = SocialRecapGenerator.generate(match, analytics=analytics)

    # Medium format assertions
    assert "HARD-FOUGHT DRAW" in recaps["medium"]
    assert "62% vs 38%" in recaps["medium"] or "62.0% vs 38.0%" in recaps["medium"]
    assert "#SkylineU16bEcnl" in recaps["medium"]

    # Long format assertions
    assert "# MATCH REPORT" in recaps["long"]
    assert "### Executive Summary" in recaps["long"]
    assert "### Tactical Phase Breakdown" in recaps["long"]
    assert "### Statistical Box Score" in recaps["long"]
    assert "| **Goals** | **3** | **3** |" in recaps["long"]
    assert "### Coaching Takeaway" in recaps["long"]


def test_social_generator_empty_match_graceful():
    """Verify generator handles minimal/unseeded match without crashing."""
    match = Match(
        id="minimal",
        title="Team A vs Team B",
        home_team="Team A",
        away_team="Team B",
        date="2026-09-24",
        video_url="/media/demo_match.mp4",
    )
    recaps = SocialRecapGenerator.generate(match)

    assert recaps["match_id"] == "minimal"
    assert len(recaps["short"]) <= 280
    assert len(recaps["medium"]) > 50
    assert len(recaps["long"]) > 100
