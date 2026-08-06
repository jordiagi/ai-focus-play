from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


def test_protocol_and_registry_imports_do_not_import_torch() -> None:
    sys.modules.pop("torch", None)

    from src.ml import interfaces, model_registry

    assert interfaces.Detector is not None
    assert all(model.revision != "main" for model in model_registry.MODELS)
    assert "torch" not in sys.modules


def test_device_override_sets_mps_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FOCUS_DEVICE", "cpu")
    monkeypatch.delenv("PYTORCH_ENABLE_MPS_FALLBACK", raising=False)

    from src.ml.device import get_device

    assert get_device() == "cpu"
    assert __import__("os").environ["PYTORCH_ENABLE_MPS_FALLBACK"] == "1"


def test_fake_models_replay_ground_truth_deterministically(tmp_path: Path) -> None:
    from src.ml.interfaces import CropInput, FrameInput
    from tests.fakes.fake_models import FakeDetector, FakeEmbedder, FakeOCR

    truth = {
        "frames": [
            {
                "ts": 0.0,
                "detections": [
                    {
                        "identity_id": "home-8",
                        "number": "8",
                        "x": 0.1,
                        "y": 0.2,
                        "w": 0.1,
                        "h": 0.3,
                    }
                ],
            }
        ]
    }
    path = tmp_path / "ground_truth.json"
    path.write_text(json.dumps(truth))
    crop = CropInput(data=None, identity_id="home-8", number="8")

    boxes = FakeDetector(path).detect([FrameInput(data=None, ts=0.0)])[0]
    vectors = FakeEmbedder().embed([crop, crop])
    readings = FakeOCR().recognize([crop])

    assert boxes[0].identity_id == "home-8"
    assert vectors[0] == vectors[1]
    assert readings[0].text == "8"


def test_doctor_report_runs_without_ml_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FOCUS_DEVICE", "cpu")

    from src.ml.doctor import collect_report

    report = collect_report()
    assert report["device"] == "cpu"
    assert set(report["tools"]) == {"ffmpeg", "ffprobe"}
    assert set(report["models"])
