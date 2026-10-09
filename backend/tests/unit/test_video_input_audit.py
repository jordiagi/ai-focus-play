"""Local inventory handles candidate frames, sparse tracking and absent labels."""
import importlib.util
import json
from pathlib import Path
import subprocess


SCRIPT = Path(__file__).resolve().parents[3] / "scripts/local/audit-video-inputs.py"
spec = importlib.util.spec_from_file_location("video_input_audit", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_artifact_cadence_counts_empty_candidates_and_duplicate_times(tmp_path):
    artifact = tmp_path / "ball_candidates.json"
    artifact.write_text(json.dumps({"frames": 4, "detections": [
        {"t": 0, "c": [[1, 2, 3, .9]]}, {"t": .1, "c": []},
        {"t": .1, "c": [[1, 2, 3, .8]]}, {"t": .2, "c": []},
    ]}))
    report = audit.summarize_artifact(artifact)
    assert report["timestamp_count"] == 4
    assert report["unique_timestamp_count"] == 3
    assert report["duplicate_timestamp_count"] == 1
    assert report["observation_count"] == 2
    assert report["rows_with_observations"] == 2
    assert report["median_cadence_fps"] == 10


def test_list_tracks_invalid_times_and_sparse_gaps(tmp_path):
    artifact = tmp_path / "ball_track.json"
    artifact.write_text(json.dumps([{"t": 1, "u": 2}, {"t": 11, "u": 2},
                                    {"t": "nan"}, {"t": None}, {"t": True}]))
    report = audit.summarize_artifact(artifact)
    assert report["invalid_timestamp_rows"] == 3
    assert report["median_gap_s"] == 10
    assert report["max_gap_s"] == 10
    assert report["median_cadence_fps"] == .1


def test_unlabeled_registry_and_corrupt_artifact_keep_report_usable(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "players_colour.json").write_text("broken JSON")
    registry = tmp_path / "matches.json"
    registry.write_text(json.dumps({"matches": [{"id": "unlabeled", "video": "missing.mp4",
        "artifacts": "artifacts", "stats": None, "events": None, "calib": None,
        "periods": None, "own_side_p1": None}]}))
    report = audit.audit_registry(registry, root=tmp_path)["matches"][0]
    assert not report["has_available_labels"]
    assert report["labels"]["stats"] == {"path": None, "available": False}
    assert not report["external_guidance"]["periods"]["present"]
    assert report["video"]["probe_status"] == "missing_or_invalid_video"
    assert "error" in report["artifacts"][0]


def test_ffprobe_is_local_metadata_only(tmp_path, monkeypatch):
    video = tmp_path / "match.mp4"
    video.write_bytes(b"placeholder")
    monkeypatch.setattr(audit.shutil, "which", lambda _: "/usr/bin/ffprobe")
    calls = []

    def probe(command, **kwargs):
        calls.append(command)
        assert kwargs["timeout"] == 30
        return subprocess.CompletedProcess(command, 0, '{"streams":[{"width":1920}],"format":{"duration":"60"}}')

    monkeypatch.setattr(audit.subprocess, "run", probe)
    report = audit.probe_video(str(video))
    assert report["metadata"]["streams"][0]["width"] == 1920
    assert calls[0][calls[0].index("-protocol_whitelist") + 1] == "file"
    assert audit.probe_video("https://example.com/video.mp4")["available"] is False
    assert len(calls) == 1


def test_guidance_availability_is_not_claimed_as_actual_usage(tmp_path):
    (tmp_path / "labels.json").write_text("{}")
    (tmp_path / "camera.veo").write_text("{}")
    report = audit.audit_match({"stats": "labels.json", "calib": "camera.veo",
                               "periods": [[0, 30]], "own_side_p1": "left"}, tmp_path)
    assert report["has_available_labels"]
    assert report["external_guidance"]["calibration"]["available"]
    assert report["external_guidance"]["periods"]["present"]
    assert report["guidance_usage"] == "availability_only_not_inference_usage"
