import pytest
from fastapi.testclient import TestClient
from backend.src.app.main import app
from backend.src.services.pipeline.stats_benchmark import load_live_veo_benchmark, compare_stats_table


def test_load_live_veo_benchmark():
    gt = load_live_veo_benchmark()
    assert gt["match"]["title"] == "Arlington SA U16B ECNL (26-27) vs. Skyline U16B ECNL"
    assert len(gt["stats_table"]["rows"]) == 13


def test_compare_stats_table_exact_match():
    # If model outputs exact ground truth values
    home = {
        "goals": 3,
        "shots": 9,
        "attempts": 12,
        "corners": 3,
        "free_kicks": 8,
        "throw_ins": 14,
        "fouls": 7,
        "penalties": 0,
        "tackles": 43,
        "passes_completed": 283,
        "possession_percent": 62,
        "possession_minutes": 22,
        "possession_won": 151,
    }
    away = {
        "goals": 3,
        "shots": 10,
        "attempts": 13,
        "corners": 6,
        "free_kicks": 7,
        "throw_ins": 24,
        "fouls": 8,
        "penalties": 0,
        "tackles": 41,
        "passes_completed": 203,
        "possession_percent": 38,
        "possession_minutes": 14,
        "possession_won": 150,
    }

    result = compare_stats_table(home, away)
    assert result["evaluated_count"] == 26
    assert result["exact_match_count"] == 26
    assert result["exact_match_ratio"] == 1.0


def test_compare_stats_table_honors_unavailable():
    home = {"goals": 3, "throw_ins": 28}
    away = {"goals": 0, "throw_ins": 18}
    unavailable = {"goals": "detection count, not a scoreline"}

    result = compare_stats_table(home, away, unavailable=unavailable)
    metrics = result["metrics"]
    assert metrics["goal"]["status"] == "unavailable"
    assert metrics["goal"]["reason"] == "detection count, not a scoreline"
    assert metrics["goal"]["pred_home"] is None


def test_api_benchmark_endpoint():
    client = TestClient(app)
    res = client.get("/api/matches/demo-arlington-skyline/benchmark")
    assert res.status_code == 200
    body = res.json()
    assert body["match_id"] == "demo-arlington-skyline"
    assert "comparison" in body
    assert "metrics" in body["comparison"]
