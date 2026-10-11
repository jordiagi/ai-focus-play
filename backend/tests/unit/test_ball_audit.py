import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("ball_audit", Path(__file__).resolve().parents[3] / "scripts/local/score-ball-audit.py")
audit_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_tool)


def inputs():
    pred = {"input_provenance": {"clip_sha256": "a"*64}, "detections": [
        {"t": 0, "c": [[10, 10, 4, .9], [50, 50, 4, .8]]},
        {"t": .1, "c": []}, {"t": .2, "c": [[20, 20, 4, .7]]},
        {"t": .3, "c": [[30, 30, 4, .7]]}]}
    audit = {"clip_sha256": "a"*64, "frames": [
        {"t": 0, "status": "visible", "center": [10, 10]},
        {"t": .1, "status": "visible", "center": [10, 10]},
        {"t": .2, "status": "not_visible"}, {"t": .3, "status": "uncertain"}]}
    return pred, audit


def test_one_to_one_matching_counts_distractors_and_excludes_uncertainty():
    report = audit_tool.score(*inputs())
    assert (report["true_positives"], report["false_positives"], report["false_negatives"]) == (1, 2, 1)
    assert report["precision"] == pytest.approx(1/3)
    assert report["recall"] == .5
    assert report["audited_frame_fraction"] == .75
    assert report["excluded_frames"] == 1


@pytest.mark.parametrize("kind", ["hash", "duplicate", "timestamp", "status", "center", "nan_time"])
def test_invalid_audit_rejected(kind):
    pred, audit = inputs()
    if kind == "hash": audit["clip_sha256"] = "b"*64
    elif kind == "duplicate": audit["frames"].append(audit["frames"][0])
    elif kind == "timestamp": audit["frames"][0]["t"] = 99
    elif kind == "status": audit["frames"][0]["status"] = "guess"
    elif kind == "center": audit["frames"][0]["center"] = [float("nan"), 0]
    elif kind == "nan_time": audit["frames"][0]["t"] = float("nan")
    with pytest.raises(ValueError): audit_tool.score(pred, audit)


def test_no_audited_evidence_has_no_accuracy_numbers():
    pred, audit = inputs()
    audit["frames"] = [{"t": 0, "status": "occluded"}]
    report = audit_tool.score(pred, audit)
    assert report["precision"] is report["recall"] is report["f1"] is None


def test_rich_tiled_candidates_have_the_same_scoring_contract():
    pred, audit = inputs()
    expected = audit_tool.score(pred, audit)
    for frame in pred["detections"]:
        frame["candidates"] = [dict(cx=c[0], cy=c[1], size=c[2], conf=c[3]) for c in frame.pop("c")]
    assert audit_tool.score(pred, audit) == expected


def test_unknown_prediction_format_is_not_silently_counted_as_no_detection():
    pred, audit = inputs()
    pred["detections"][0].pop("c")
    with pytest.raises(ValueError, match="container"):
        audit_tool.score(pred, audit)
