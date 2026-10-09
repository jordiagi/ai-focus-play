"""Video-only ingestion cannot consult evaluation labels or fixed pitch priors."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from backend.src.domain.models.match import Highlight, Match, PlayerRoster
from backend.src.services.pipeline.pipeline_runner import MatchPipeline
from backend.src.storage.repository import MatchRepository


@pytest.fixture
def video_match():
    repo = MatchRepository()
    match = Match(id="video-only-skyline-probe", title="Video only",
                  home_team="Team A", away_team="Team B", date="2026-10-09",
                  video_url="/media/video-only-probe.mp4", duration_seconds=120)
    repo.save_match(match)
    yield repo, match
    repo.delete_match(match.id)


@pytest.fixture
def forbidden_enrichment(monkeypatch):
    from backend.src.services.pipeline import stats_benchmark, federation_acta
    from backend.src.services.pipeline.pitch_homography import PitchHomography
    from backend.src.services.pipeline.radar_calibrator import CalibratedPitchRadar
    from backend.src.services.pipeline.veo_calibrator import VeoCameraModel

    def forbidden(*args, **kwargs):
        pytest.fail("video_only consulted a forbidden enrichment source")

    monkeypatch.setattr(stats_benchmark, "load_live_veo_benchmark", forbidden)
    monkeypatch.setattr(stats_benchmark, "build_analytics_from_benchmark", forbidden)
    monkeypatch.setattr(federation_acta.acta_service, "resolve_acta_for_match", forbidden)
    monkeypatch.setattr(federation_acta.acta_service, "reconcile_match", forbidden)
    monkeypatch.setattr(VeoCameraModel, "from_veo_file", forbidden)
    monkeypatch.setattr(CalibratedPitchRadar, "from_artifacts", forbidden)
    monkeypatch.setattr(PitchHomography, "canonical_broadcast_prior", forbidden)


def test_no_artifacts_means_no_inference(video_match, forbidden_enrichment, monkeypatch):
    repo, match = video_match

    def forbidden_read(*args, **kwargs):
        pytest.fail("No explicit artifacts must cause no file reads")

    monkeypatch.setattr(Path, "read_text", forbidden_read)
    pipeline = MatchPipeline(match.id, mode="video_only", repo=repo)
    assert pipeline.artifacts_dir is None
    assert pipeline.calib_file is None
    result = pipeline.run()
    assert result["events_ingested"] == 0
    assert result["input_artifacts"] == []
    assert result["evaluation_labels_used"] is False
    stored = repo.get_match(match.id)
    assert stored.analysis_mode == "video_only"
    assert all(cap.status == "not_attempted" for cap in stored.event_capabilities.values())
    assert repo.get_analytics(match.id).provenance == "video_only"


def test_explicit_predictions_ignore_scores_and_geometry(
    video_match, forbidden_enrichment, tmp_path, monkeypatch,
):
    repo, match = video_match
    pred = {"events": [{"event_type": "FootballGoal", "video_s": 10,
                        "team": "Own", "confidence": 0.7}]}
    (tmp_path / "pred_all.json").write_text(json.dumps(pred))
    (tmp_path / "manifest_all.json").write_text(json.dumps({
        "attempted": ["FootballGoal"],
        "input_provenance": {"mode": "video_only", "evaluation_labels_used": False,
                             "video_sha256": "a" * 64},
    }))
    # All of these must be ignored, even when present beside valid predictions.
    for name in ("score_all.json", "players_colour.json", "ball_track.json", "cameras.json"):
        (tmp_path / name).write_text("invalid JSON: forbidden input")
    read_text = Path.read_text
    read_names = []

    def audited_read(path, *args, **kwargs):
        assert path.name in {"pred_all.json", "manifest_all.json"}
        read_names.append(path.name)
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", audited_read)
    result = MatchPipeline(match.id, mode="video_only", artifacts_dir=tmp_path, repo=repo).run()
    assert result["verified"]
    assert result["video_sha256"] == "a" * 64
    assert result["input_provenance_assurance"] == "producer-attested; not independently certified"
    assert sorted(read_names) == ["manifest_all.json", "pred_all.json"]
    assert result["physics_shots_detected"] == result["radar_frames_stored"] == 0
    event, = repo.get_events(match.id)
    assert event.team == "unknown"
    assert event.pitch_x is None and event.pitch_y is None
    assert event.confidence == 0.7
    assert "F1" not in event.description
    caps = repo.get_match(match.id).event_capabilities
    assert caps["Goal"].count == 1
    assert caps["Shot"].status == "not_attempted"
    analytics = repo.get_analytics(match.id)
    assert {"shots", "goals", "passes_completed", "possession_percent"} <= set(analytics.unavailable)
    assert analytics.shot_map == []
    assert analytics.pass_strings == {"home": [], "away": []}


@pytest.mark.parametrize("provenance", [
    None,
    {"mode": "ml", "evaluation_labels_used": False, "video_sha256": "a" * 64},
    {"mode": "video_only", "evaluation_labels_used": True, "video_sha256": "a" * 64},
    {"mode": "video_only", "evaluation_labels_used": False, "video_sha256": "not-a-hash"},
])
def test_invalid_provenance_fails_before_writes(video_match, tmp_path, monkeypatch, provenance):
    repo, match = video_match
    (tmp_path / "pred_all.json").write_text(json.dumps({"events": []}))
    manifest = {"attempted": []}
    if provenance is not None:
        manifest["input_provenance"] = provenance
    (tmp_path / "manifest_all.json").write_text(json.dumps(manifest))

    def forbidden_write(*args, **kwargs):
        pytest.fail("Invalid artifact provenance must fail before repository writes")

    for method in ("save_radar_frames", "set_lineup", "set_highlights", "set_events",
                   "set_analytics", "save_match"):
        monkeypatch.setattr(repo, method, forbidden_write)
    with pytest.raises(ValueError, match="input_provenance"):
        MatchPipeline(match.id, mode="video_only", artifacts_dir=tmp_path, repo=repo).run()


def test_manual_highlights_survive_video_only_run(video_match):
    repo, match = video_match
    manual = Highlight(match_id=match.id, title="Coach annotation", event_type="custom",
                       start_time=1, end_time=3, is_ai_detected=False)
    automatic = Highlight(match_id=match.id, title="Previous prediction", event_type="goal",
                          start_time=5, end_time=7, is_ai_detected=True)
    repo.set_highlights(match.id, [manual, automatic], internal=True)
    MatchPipeline(match.id, mode="video_only", repo=repo).run()
    remaining = repo.get_highlights(match.id)
    assert [highlight.id for highlight in remaining] == [manual.id]


@pytest.mark.parametrize("files", [None, [], ["pred_all.json"], ["manifest_all.json"]])
def test_explicit_incomplete_artifacts_rejected_before_writes(video_match, tmp_path, monkeypatch, files):
    repo, match = video_match
    artifacts = tmp_path / "artifacts"
    if files is not None:
        artifacts.mkdir()
        for name in files:
            (artifacts / name).write_text("{}")

    def forbidden_write(*args, **kwargs):
        pytest.fail("Incomplete artifact inputs must fail before writes")

    monkeypatch.setattr(repo, "save_radar_frames", forbidden_write)
    with pytest.raises(ValueError, match="must contain both"):
        MatchPipeline(match.id, mode="video_only", artifacts_dir=artifacts, repo=repo).run()


@pytest.mark.parametrize("mode,home_score,away_score", [
    ("ml", 0, 0), ("demo", 0, 0), ("heuristic", 2, 0), ("video_only", 0, 1),
])
def test_enriched_or_scored_match_rejected_before_writes(video_match, monkeypatch, mode, home_score, away_score):
    repo, match = video_match
    match.analysis_mode, match.home_score, match.away_score = mode, home_score, away_score
    repo.save_match(match)

    def forbidden_write(*args, **kwargs):
        pytest.fail("Enriched match must fail before writes")

    monkeypatch.setattr(repo, "save_radar_frames", forbidden_write)
    with pytest.raises(ValueError, match="fresh pilot match ID"):
        MatchPipeline(match.id, mode="video_only", repo=repo).run()


def test_video_only_preserves_manual_lineup(video_match):
    repo, match = video_match
    lineup = [PlayerRoster(jersey="9", name="Human annotation", position="FWD")]
    repo.set_lineup(match.id, lineup)
    MatchPipeline(match.id, mode="video_only", repo=repo).run()
    assert repo.get_match(match.id).lineup == lineup


def test_experimental_cli_requires_explicit_database(monkeypatch):
    from backend.src.services.pipeline.pipeline_runner import main

    monkeypatch.delenv("AIFP_DB_PATH", raising=False)
    monkeypatch.setattr("sys.argv", ["pipeline_runner", "--match-id", "fresh-pilot", "--mode", "video_only"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


@pytest.mark.parametrize("arguments,returncode", [
    (["-c", "import sys; import backend.src.services.pipeline.pipeline_runner; "
      "assert 'backend.src.storage.repository' not in sys.modules"], 0),
    (["-m", "backend.src.services.pipeline.pipeline_runner", "--help"], 0),
    (["-m", "backend.src.services.pipeline.pipeline_runner", "--match-id", "fresh-pilot",
      "--mode", "video_only"], 2),
])
def test_import_help_and_rejected_cli_never_create_database(tmp_path, arguments, returncode):
    environment = os.environ.copy()
    environment.pop("AIFP_DB_PATH", None)
    environment.update(AIFP_DATA_DIR=str(tmp_path / "data"),
                       AIFP_MEDIA_DIR=str(tmp_path / "media"),
                       AIFP_CLOUD_EXPORT_DIR=str(tmp_path / "cloud"))
    completed = subprocess.run([sys.executable, *arguments], env=environment,
                               cwd=Path(__file__).resolve().parents[3],
                               capture_output=True, text=True, timeout=30)
    assert completed.returncode == returncode, completed.stderr
    assert not (tmp_path / "data" / "veo.db").exists()
    assert not list(tmp_path.rglob("*.db"))


@pytest.mark.parametrize("mode", ["video_only", "ml", "demo"])
def test_supplied_repository_never_calls_default_factory(monkeypatch, mode):
    import backend.src.services.pipeline.pipeline_runner as runner

    class SuppliedRepository:
        def __bool__(self):
            return False

    def forbidden():
        pytest.fail("Supplied repositories must avoid default repository initialization")

    supplied = SuppliedRepository()
    monkeypatch.setattr(runner, "_default_repository", forbidden)
    pipeline = runner.MatchPipeline("fresh-pilot", mode=mode, repo=supplied)
    assert pipeline.repo is supplied


def test_video_only_rejects_external_calibration(video_match, tmp_path):
    repo, match = video_match
    with pytest.raises(ValueError, match="external .veo calibration"):
        MatchPipeline(match.id, mode="video_only", calib_file=tmp_path / "camera.veo", repo=repo)


def test_video_only_does_not_seed_missing_reference_match(forbidden_enrichment, monkeypatch):
    import backend.src.services.pipeline.ncfc_seeder as seeder

    def forbidden(*args, **kwargs):
        pytest.fail("video_only seeded a reference match")

    monkeypatch.setattr(seeder, "seed_ncfc_match", forbidden)
    repo = MatchRepository()
    with pytest.raises(ValueError, match="not found in database"):
        MatchPipeline("missing-ncfc-video-only", mode="video_only", repo=repo).run()
