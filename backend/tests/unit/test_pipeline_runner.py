"""Unit tests for Unified MatchPipeline DAG Runner."""

import json
import tempfile
import time
from pathlib import Path
import pytest

from backend.src.domain.models.match import Match
from backend.src.services.pipeline.pipeline_runner import MatchPipeline
from backend.src.storage.repository import MatchRepository


@pytest.fixture
def test_repo():
    """Repository instance with cleanup."""
    repo = MatchRepository()
    yield repo
    # Clean up probe match if created
    repo.delete_match("probe-pipeline-match")


@pytest.fixture
def probe_match(test_repo):
    """Seed a test match in the repository."""
    match = Match(
        id="probe-pipeline-match",
        title="Probe vs Pipeline",
        home_team="Probe FC",
        away_team="Pipeline City",
        date="2026-09-24",
        video_url="/media/test.mp4",
        duration_seconds=120.0,
        status="processing",
        created_at=time.time(),
    )
    test_repo.save_match(match)
    return match


def test_pipeline_runner_ml_mode(test_repo, probe_match, tmp_path):
    """Verify MatchPipeline runs ML mode hermetically using sample fixtures."""
    fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures" / "ml"

    pipeline = MatchPipeline(
        match_id=probe_match.id,
        mode="ml",
        artifacts_dir=fixtures_dir,
        calib_file=tmp_path / "non_existent.veo",
        repo=test_repo,
    )

    result = pipeline.run()

    assert result["mode"] == "ml"
    assert result["match_id"] == probe_match.id
    assert result["verified"] is True
    assert result["events_ingested"] == result["events_stored"]
    assert result["analytics_provenance"] == "ml"

    # Verify updated database match object
    updated_match = test_repo.get_match(probe_match.id)
    assert updated_match.analysis_mode == "ml"
    assert updated_match.status == "ready"
    assert updated_match.event_capabilities is not None
    assert len(updated_match.event_capabilities) > 0


def test_pipeline_runner_invalid_match(test_repo):
    """Verify MatchPipeline raises error for non-existent match."""
    pipeline = MatchPipeline(
        match_id="non-existent-match",
        mode="ml",
        repo=test_repo,
    )
    with pytest.raises(ValueError, match="not found in database"):
        pipeline.run()


def test_pipeline_runner_unknown_mode(test_repo, probe_match):
    """Verify MatchPipeline rejects unsupported analysis modes."""
    pipeline = MatchPipeline(
        match_id=probe_match.id,
        mode="unsupported_mode",
        repo=test_repo,
    )
    with pytest.raises(ValueError, match="Unknown analysis mode"):
        pipeline.run()
