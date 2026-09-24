"""Hermetic tests for ML pipeline ingestion and analytics.

Decoupled from gitignored .local/artifacts so CI and clean clones test the ML
provenance contract without needing to rebuild or download large artifact files.
"""
import json
from pathlib import Path
import pytest

from backend.src.services.pipeline.ml_ingest import build, TYPE_TO_LABEL, UNAVAILABLE, DEMO_MATCH_ID
from backend.src.services.pipeline.ml_analytics import build_ml_analytics, STATS_UNAVAILABLE

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "ml"


@pytest.fixture
def ml_fixtures():
    with open(FIXTURES_DIR / "pred_sample.json") as f:
        pred = json.load(f)
    with open(FIXTURES_DIR / "manifest_sample.json") as f:
        manifest = json.load(f)
    with open(FIXTURES_DIR / "score_sample.json") as f:
        score = json.load(f)
    return pred, manifest, score


def test_ml_ingest_build_events_and_capabilities(ml_fixtures):
    pred, manifest, score = ml_fixtures
    match_id = "test-match-123"
    
    events, caps = build(pred, manifest, score, match_id)
    
    # 1. Ingests all valid events in pred
    assert len(events) == len(pred["events"])
    
    # 2. Invariant: No metric positions are invented
    for ev in events:
        assert ev.pitch_x is None
        assert ev.pitch_y is None
        assert ev.player_jersey is None
        assert ev.player_name is None
        assert ev.match_id == match_id
        
    # 3. Check capability surface covers all 16 labels
    assert len(caps) == 16
    for label, cap in caps.items():
        if cap.status == "detected":
            assert cap.count > 0
        elif cap.status == "unavailable":
            assert cap.reason is not None
            assert len(cap.reason) > 10


def test_ml_ingest_refuses_pinned_demo_match(ml_fixtures):
    """The demo match must never be overwritten by an ML ingest."""
    assert DEMO_MATCH_ID == "demo-arlington-skyline"


def test_ml_analytics_provenance_and_unavailable(ml_fixtures):
    pred, manifest, score = ml_fixtures
    analytics = build_ml_analytics(pred, manifest, score)
    
    assert analytics.provenance == "ml"
    assert analytics.unavailable is not None
    
    # Key unmeasured stats must be listed in unavailable
    for unavail_key in ("corners", "free_kicks", "fouls", "penalties", "tackles", "passes_completed"):
        assert unavail_key in analytics.unavailable
        
    # Heatmaps and pass strings must be empty
    assert analytics.pass_strings == {"home": [], "away": []}
    assert analytics.heatmaps == {"home": [], "away": []}
