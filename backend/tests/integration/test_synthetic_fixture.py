from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.fixtures.make_synthetic_match import make_synthetic_match


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
def test_synthetic_fixture_has_video_and_ground_truth(tmp_path: Path) -> None:
    video_path, truth_path = make_synthetic_match(tmp_path)

    truth = json.loads(truth_path.read_text())
    assert video_path.stat().st_size > 1024
    assert truth["duration_s"] == 10.0
    assert len(truth["frames"]) == 100
    assert {item["identity_id"] for item in truth["frames"][0]["detections"]} == {
        "home-8",
        "away-11",
    }
