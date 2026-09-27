"""Unit tests for Federation Acta Ingestion, Filename Inference, and Roster OCR Reinforcement."""

import pytest
from backend.src.domain.models.match import Match, Event
from backend.src.services.pipeline.federation_acta import acta_service, MatchSheet
from backend.src.services.pipeline.filename_infer import filename_parser
from backend.src.services.pipeline.jersey_ocr import JerseyVoteAggregator
from backend.src.services.social_generator import SocialRecapGenerator
from backend.src.storage.repository import match_repo


def test_acta_fixtures_loaded():
    """Verify official acta fixtures are parsed and loaded."""
    assert len(acta_service._cached_sheets) >= 2
    sheet = acta_service.resolve_acta_for_match("UA Horta", "CCD Turó de la Peira")
    assert sheet is not None
    assert sheet.federation == "FCF"
    assert sheet.home_score == 2
    assert sheet.away_score == 0
    assert len(sheet.home_lineup) >= 11
    assert len(sheet.away_lineup) >= 11
    assert len(sheet.goals) == 2
    assert len(sheet.cards) == 3


def test_acta_player_lookup():
    """Verify player lookup by side and jersey number."""
    sheet = acta_service.resolve_acta_for_match("UA Horta", "CCD Turó de la Peira")
    assert sheet is not None

    p9 = sheet.get_player("home", "9")
    assert p9 is not None
    assert p9.name == "Álex Montalbán"

    p7_home = sheet.get_player("home", "7")
    assert p7_home is not None
    assert p7_home.name == "Jordi Montesinos"

    p7_away = sheet.get_player("away", "7")
    assert p7_away is not None
    assert "Anthony Ventura" in p7_away.name or "Antonio" in p7_away.name


def test_acta_option_a_reconciliation():
    """Verify Option A strict reconciliation updates match score, lineups, and incident events."""
    sheet = acta_service.resolve_acta_for_match("UA Horta", "CCD Turó de la Peira")
    assert sheet is not None

    match = Match(
        id="test-reconcile-match",
        title="Sample Friendly",
        home_team="UA Horta",
        away_team="CCD Turó de la Peira",
        home_score=0,
        away_score=0,
        date="2026-09-20",
        video_url="/media/test.mp4",
        duration_seconds=5400.0,
    )

    reconciled_match, events, highlights = acta_service.reconcile_match(match, sheet)

    assert reconciled_match.home_score == 2
    assert reconciled_match.away_score == 0
    assert len(reconciled_match.lineup) >= 22

    # Verify goals generated
    goals = [e for e in events if e.event_type.lower() == "goal"]
    assert len(goals) == 2
    assert any(g.player_name == "Álex Montalbán" and g.player_jersey == "9" for g in goals)
    assert any(g.player_name == "Jordi Montesinos" and g.player_jersey == "7" for g in goals)

    # Verify yellow cards generated
    cards = [e for e in events if "yellow" in e.event_type.lower()]
    assert len(cards) == 3
    assert any(c.player_name == "Gerard Nieto" for c in cards)

    # Verify substitutions generated
    subs = [e for e in events if "sub" in e.event_type.lower()]
    assert len(subs) == 4
    assert any("Pol Ibáñez" in s.description for s in subs)


def test_filename_inference_hyphenated_and_underscored():
    """Verify filename inference across standard formats."""
    # 1. Standard hyphenated format without underscores
    m1 = filename_parser.parse_filename("2026-09-20-horta-vs-turo-peira-26leg1j01.mp4")
    assert m1.date == "2026-09-20"
    assert "Horta" in m1.home_team
    assert "Turó" in m1.away_team or "Turo" in m1.away_team
    assert m1.competition_code == "26leg1j01"
    assert m1.team_id is not None

    # 2. Underscored format
    m2 = filename_parser.parse_filename("2026_09_20_horta_vs_turo_peira_26leg1j01.mp4")
    assert m2.date == "2026-09-20"
    assert "Horta" in m2.home_team
    assert "Turó" in m2.away_team or "Turo" in m2.away_team

    # 3. Compact date at end
    m3 = filename_parser.parse_filename("arlington-vs-skyline-20260912.mp4")
    assert m3.date == "2026-09-12"
    assert "Arlington" in m3.home_team
    assert "Skyline" in m3.away_team


def test_jersey_ocr_with_roster_prior():
    """Verify JerseyVoteAggregator uses roster prior to suppress false digits and map names."""
    agg = JerseyVoteAggregator(
        min_votes=2,
        min_confidence=0.60,
        roster_whitelist=["7", "9", "10"],
        player_names={"7": "Anthony Ventura", "9": "Hugo Saban", "10": "Biel"},
    )

    # Add observations for legitimate #7
    agg.add_observation(track_id=1, jersey="7", confidence=0.70)
    agg.add_observation(track_id=1, jersey="7", confidence=0.75)

    # Add sporadic noise observation for #88 (not in roster)
    agg.add_observation(track_id=1, jersey="88", confidence=0.65)

    consensus = agg.get_consensus(track_id=1)
    assert consensus == "7"
    assert agg.get_player_name(consensus) == "Anthony Ventura"


def test_team_federation_url_crud():
    """Verify team creation and update with federation_url."""
    team = match_repo.create_team(
        name="Test FCF Juvenil",
        club_name="CCD Turó de la Peira",
        federation_url="https://www.fcf.cat/club/2425/turo-peira-ccd"
    )
    assert team.federation_url == "https://www.fcf.cat/club/2425/turo-peira-ccd"

    # Update federation URL
    updated = match_repo.update_team(
        team_id=team.id,
        federation_url="https://www.fcf.cat/equip/2627/1cat/turo-peira-ccd-a"
    )
    assert updated is not None
    assert updated.federation_url == "https://www.fcf.cat/equip/2627/1cat/turo-peira-ccd-a"

    # Clean up
    match_repo.delete_team(team.id)


def test_social_generator_with_acta():
    """Verify social recap generator incorporates official goalscorers and FCF tags."""
    sheet = acta_service.resolve_acta_for_match("UA Horta", "CCD Turó de la Peira")
    match = Match(
        id="test-social-match",
        title="UA Horta vs. CCD Turó de la Peira",
        home_team="UA Horta",
        away_team="CCD Turó de la Peira",
        home_score=2,
        away_score=0,
        date="2026-09-20",
        video_url="/media/turo.mp4",
    )

    recaps = SocialRecapGenerator.generate(match, benchmark={"acta": sheet})

    assert "short" in recaps
    assert "medium" in recaps
    assert "long" in recaps

    # Goalscorers should appear in text
    assert "Álex Montalbán" in recaps["medium"] or "Álex Montalbán" in recaps["short"]
    assert "Jordi Montesinos" in recaps["medium"] or "Jordi Montesinos" in recaps["short"]

    # FCF Catalan league tags
    assert "#FCF" in recaps["short"] or "#LligaElit" in recaps["short"]
    assert "Lliga Elit" in recaps["long"]
