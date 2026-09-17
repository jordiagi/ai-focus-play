import pytest
import numpy as np
from fastapi.testclient import TestClient
from backend.src.app.main import app
from backend.src.services.pipeline.cv_engine import SoccerCVEngine, PITCH_LENGTH, PITCH_WIDTH

@pytest.fixture
def client():
    return TestClient(app)

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"

def test_list_matches(client):
    response = client.get("/api/matches")
    assert response.status_code == 200
    matches = response.json()
    assert len(matches) >= 1
    demo = matches[0]
    assert "Arlington SA" in demo["home_team"]
    assert demo["home_score"] == 3
    assert demo["away_score"] == 3

def test_get_match_details(client):
    response = client.get("/api/matches/demo-arlington-skyline")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "demo-arlington-skyline"
    assert len(data["lineup"]) > 0

def test_get_match_highlights(client):
    response = client.get("/api/matches/demo-arlington-skyline/highlights")
    assert response.status_code == 200
    highlights = response.json()
    assert len(highlights) >= 3
    goal_highlight = next((h for h in highlights if h["event_type"] == "goal"), None)
    assert goal_highlight is not None

def test_get_match_radar_frames(client):
    response = client.get("/api/matches/demo-arlington-skyline/radar")
    assert response.status_code == 200
    frames = response.json()
    assert len(frames) > 0
    f0 = frames[0]
    assert "players" in f0
    assert "ball" in f0
    assert len(f0["players"]) >= 10

def test_get_match_analytics(client):
    response = client.get("/api/matches/demo-arlington-skyline/analytics")
    assert response.status_code == 200
    data = response.json()
    assert "home_stats" in data
    assert "shot_map" in data
    assert "pass_locations" in data
    assert "possession_locations" in data
    assert "pass_strings" in data

def test_homography_projection():
    engine = SoccerCVEngine()
    H = engine.estimate_pitch_homography((1080, 1920))
    assert H is not None
    assert H.shape == (3, 3)

    # Test projection of a center point
    x_m, y_m = engine.project_point_to_pitch(H, 960, 540)
    assert 0.0 <= x_m <= PITCH_LENGTH
    assert 0.0 <= y_m <= PITCH_WIDTH

def test_drawing_crud(client):
    match_id = "demo-arlington-skyline"
    # Create drawing
    req = {
        "timestamp": 18.5,
        "tool_type": "spotlight",
        "color": "#00E676",
        "coordinates": [{"x": 0.5, "y": 0.4}],
        "text_label": "Key Movement"
    }
    create_res = client.post(f"/api/matches/{match_id}/drawings", json=req)
    assert create_res.status_code == 200
    drawing = create_res.json()
    assert drawing["tool_type"] == "spotlight"
    d_id = drawing["id"]

    # Fetch drawings
    get_res = client.get(f"/api/matches/{match_id}/drawings")
    assert get_res.status_code == 200
    drawings = get_res.json()
    assert any(d["id"] == d_id for d in drawings)

    # Delete drawing
    del_res = client.delete(f"/api/matches/{match_id}/drawings/{d_id}")
    assert del_res.status_code == 200
