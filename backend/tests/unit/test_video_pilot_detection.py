import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[3] / "scripts/local/detect-video-pilot.py"
spec = importlib.util.spec_from_file_location("video_pilot_detection", SCRIPT)
detection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(detection)


class Tensor:
    def __init__(self, values):
        self.values = values

    def cpu(self):
        return self

    def tolist(self):
        return self.values


@pytest.fixture
def pilot(tmp_path, monkeypatch):
    directory = tmp_path / "pilot"
    directory.mkdir()
    (directory / "clip.mp4").write_bytes(b"local clip")
    prep = {"artifact_type": "video_pilot_preparation", "inference_performed": False,
            "input_provenance": {"mode": "video_only", "evaluation_labels_used": False,
                                 "video_sha256": "a" * 64},
            "sampling": {"start_s": 120, "fps": 10, "duration_s": .2},
            "clip": {"sha256": hashlib.sha256(b"local clip").hexdigest()}}
    (directory / "pilot_manifest.json").write_text(json.dumps(prep))
    weights = tmp_path / "checkpoint.pt"
    weights.write_bytes(b"checkpoint")
    calls = []

    class Model:
        names = {0: "person", 32: "sports ball"}

        def predict(self, **kwargs):
            calls.append(kwargs)
            boxes = SimpleNamespace(xyxy=Tensor([[0, 0, 10, 20], [10, 20, 14, 24]]),
                                    conf=Tensor([.8, .5]), cls=Tensor([0, 32]))
            return iter([SimpleNamespace(orig_shape=(720, 1280), boxes=boxes),
                         SimpleNamespace(orig_shape=(720, 1280), boxes=None)])

    monkeypatch.setattr(detection, "load_model", lambda _: (Model(), {"ultralytics": "mock", "torch": "mock"}))
    return directory, weights, calls


def test_cpu_object_detection_preserves_video_clock_and_empty_frames(tmp_path, pilot):
    directory, weights, calls = pilot
    output = tmp_path / "detections"
    manifest = json.loads(detection.detect_pilot(directory, weights, output).read_text())
    people = json.loads((output / "players_detections.json").read_text())["detections"]
    ball = json.loads((output / "ball_candidates.json").read_text())["detections"]
    assert [row["t"] for row in people] == [120, 120.1]
    assert people[1]["boxes"] == []
    assert ball[0]["c"] == [[12, 22, 4, .5]]
    assert ball[1]["c"] == []
    assert manifest["counts"]["frames_with_ball_candidate"] == 1
    assert manifest["input_provenance"]["evaluation_labels_used"] is False
    assert manifest["model"]["sha256"] == hashlib.sha256(b"checkpoint").hexdigest()
    assert manifest["model"]["class_names"] == {"0": "person", "32": "sports ball"}
    assert manifest["frame_integrity"]["actual_frames"] == 2
    assert calls[0]["device"] == "cpu" and calls[0]["classes"] == [0, 32]
    assert calls[0]["stream"] is True and calls[0]["save"] is False
    assert len(list(output.glob("*.json"))) == 3
    assert not list(output.glob("pred*"))


def test_tampered_clip_rejected_before_model(tmp_path, pilot):
    directory, weights, calls = pilot
    (directory / "clip.mp4").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="clip hash"):
        detection.detect_pilot(directory, weights, tmp_path / "detections")
    assert not calls


@pytest.mark.parametrize("field,value", [("video_sha256", "invalid"), ("evaluation_labels_used", True),
                                         ("mode", "ml")])
def test_invalid_provenance_rejected(tmp_path, pilot, field, value):
    directory, weights, calls = pilot
    path = directory / "pilot_manifest.json"
    manifest = json.loads(path.read_text())
    manifest["input_provenance"][field] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        detection.detect_pilot(directory, weights, tmp_path / "detections")
    assert not calls


@pytest.mark.parametrize("weights", ["https://example.com/model.pt", "missing.pt"])
def test_explicit_local_checkpoint_required(tmp_path, pilot, weights):
    directory, _, calls = pilot
    with pytest.raises(ValueError):
        detection.detect_pilot(directory, weights, tmp_path / "detections")
    assert not calls


def test_no_overwrite(tmp_path, pilot):
    directory, weights, calls = pilot
    output = tmp_path / "detections"
    output.mkdir()
    with pytest.raises(ValueError, match="overwrite"):
        detection.detect_pilot(directory, weights, output)
    assert not calls


def test_dangling_output_symlink_rejected(tmp_path, pilot):
    directory, weights, calls = pilot
    output = tmp_path / "detections"
    output.symlink_to(tmp_path / "absent-target")
    with pytest.raises(ValueError, match="overwrite"):
        detection.detect_pilot(directory, weights, output)
    assert not calls


@pytest.mark.parametrize("names", [{0: "ball", 32: "person"}, {0: "person"}, None])
def test_custom_checkpoint_class_mapping_rejected_before_predict(tmp_path, pilot, monkeypatch, names):
    directory, weights, calls = pilot
    original = detection.load_model

    def load(weights):
        model, versions = original(weights)
        model.names = names
        return model, versions

    monkeypatch.setattr(detection, "load_model", load)
    with pytest.raises(ValueError, match="checkpoint must map"):
        detection.detect_pilot(directory, weights, tmp_path / "detections")
    assert not calls


@pytest.mark.parametrize("duration", [.5, .01])
def test_incomplete_or_excess_frame_stream_does_not_publish_timestamps(tmp_path, pilot, duration):
    directory, weights, calls = pilot
    path = directory / "pilot_manifest.json"
    manifest = json.loads(path.read_text())
    manifest["sampling"]["duration_s"] = duration
    path.write_text(json.dumps(manifest))
    output = tmp_path / "detections"
    with pytest.raises(ValueError, match="decoded frame count"):
        detection.detect_pilot(directory, weights, output)
    assert calls
    assert not output.exists()


def test_one_frame_rounding_tolerance_is_recorded(tmp_path, pilot):
    directory, weights, _ = pilot
    path = directory / "pilot_manifest.json"
    manifest = json.loads(path.read_text())
    manifest["sampling"]["duration_s"] = .3
    path.write_text(json.dumps(manifest))
    result = json.loads(detection.detect_pilot(directory, weights, tmp_path / "detections").read_text())
    assert result["frame_integrity"] == {"expected_frames": 3, "actual_frames": 2, "tolerance_frames": 1}
