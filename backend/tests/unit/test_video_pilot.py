"""Pilot preparation records video provenance and cannot consume reference labels."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[3] / "scripts/local/prepare-video-pilot.py"
spec = importlib.util.spec_from_file_location("video_pilot", SCRIPT)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


@pytest.fixture
def local_source(tmp_path, monkeypatch):
    video = tmp_path / "source with spaces.mp4"
    video.write_bytes(b"local source bytes")
    monkeypatch.setattr(pilot.shutil, "which", lambda name: f"/usr/bin/{name}")
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if "ffprobe" in command[0]:
            return subprocess.CompletedProcess(command, 0, json.dumps({
                "format": {"duration": "100"}, "streams": [{"width": 1920, "height": 1080}]}))
        Path(command[-1]).write_bytes(b"sampled clip bytes")
        return subprocess.CompletedProcess(command, 0, "")

    monkeypatch.setattr(pilot.subprocess, "run", run)
    return video, calls


def test_preparation_records_hashes_metadata_and_cpu_command(tmp_path, local_source):
    video, calls = local_source
    manifest_path = pilot.prepare_pilot(video, 5, 20, 10, tmp_path / "pilot")
    manifest = json.loads(manifest_path.read_text())
    assert manifest["input_provenance"]["mode"] == "video_only"
    assert manifest["input_provenance"]["evaluation_labels_used"] is False
    assert manifest["input_provenance"]["video_sha256"] == hashlib.sha256(video.read_bytes()).hexdigest()
    assert manifest["clip"]["sha256"] == hashlib.sha256(b"sampled clip bytes").hexdigest()
    assert manifest["inference_performed"] is False
    assert manifest["source_metadata"]["streams"][0]["width"] == 1920
    command = calls[1]
    assert "-n" in command and "-y" not in command
    assert command[command.index("-c:v") + 1] == "libx264"
    assert command[command.index("-protocol_whitelist") + 1] == "file"
    assert "1280" in command[command.index("-vf") + 1]
    assert "fps=10" in command[command.index("-vf") + 1]
    assert manifest["compute"]["mode"] == "local_cpu"


@pytest.mark.parametrize("source", ["https://example.com/video.mp4", "ssh://host/video", "file:///tmp/video"])
def test_remote_sources_rejected_before_any_command(tmp_path, local_source, source):
    _, calls = local_source
    with pytest.raises(ValueError, match="local filesystem"):
        pilot.prepare_pilot(source, 0, 20, 10, tmp_path / "pilot")
    assert calls == []


@pytest.mark.parametrize("start,duration,fps", [(-1, 20, 10), (0, 0, 10), (0, 20, 0),
                                                (float("nan"), 20, 10), (90, 20, 10)])
def test_invalid_ranges_do_not_encode_or_create_output(tmp_path, local_source, start, duration, fps):
    video, calls = local_source
    output = tmp_path / "pilot"
    with pytest.raises(ValueError):
        pilot.prepare_pilot(video, start, duration, fps, output)
    assert not output.exists()
    assert all("ffprobe" in command[0] for command in calls)


def test_existing_output_is_never_overwritten(tmp_path, local_source):
    video, calls = local_source
    output = tmp_path / "pilot"
    output.mkdir()
    (output / "clip.mp4").write_bytes(b"existing")
    with pytest.raises(ValueError, match="overwrite"):
        pilot.prepare_pilot(video, 0, 20, 10, output)
    assert (output / "clip.mp4").read_bytes() == b"existing"
    assert not calls


def test_cli_defaults_and_manifest_is_preparation_not_predictions(tmp_path, local_source):
    video, _ = local_source
    output = tmp_path / "pilot"
    assert pilot.main(["--video", str(video), "--start", "0", "--out", str(output)]) == 0
    manifest = json.loads((output / "pilot_manifest.json").read_text())
    assert manifest["sampling"]["fps"] == 10
    assert manifest["sampling"]["duration_s"] == 20
    assert manifest["artifact_type"] == "video_pilot_preparation"
    assert "events" not in manifest and "predictions" not in manifest
