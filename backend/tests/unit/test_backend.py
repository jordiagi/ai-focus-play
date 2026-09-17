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

def test_capabilities_endpoint(client):
    response = client.get("/api/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert "read_only" in data
    assert "allow_uploads" in data
    assert data["allow_uploads"] is True

def test_list_matches(client):
    response = client.get("/api/matches")
    assert response.status_code == 200
    matches = response.json()
    assert len(matches) >= 1
    demo = next((m for m in matches if m["id"] == "demo-arlington-skyline"), None)
    assert demo is not None
    assert "Arlington SA" in demo["home_team"]
    assert demo["home_score"] == 3
    assert demo["away_score"] == 3

def test_get_match_details(client):
    response = client.get("/api/matches/demo-arlington-skyline")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "demo-arlington-skyline"
    assert len(data["lineup"]) > 0
    assert data["analysis_mode"] == "demo"

def test_get_match_highlights(client):
    response = client.get("/api/matches/demo-arlington-skyline/highlights")
    assert response.status_code == 200
    highlights = response.json()
    assert len(highlights) >= 3
    goal_highlight = next((h for h in highlights if h["event_type"] == "goal"), None)
    assert goal_highlight is not None

def test_get_match_radar_frames_and_window(client):
    # Full radar frames
    response = client.get("/api/matches/demo-arlington-skyline/radar")
    assert response.status_code == 200
    frames = response.json()
    assert len(frames) > 0
    f0 = frames[0]
    assert "players" in f0
    assert "ball" in f0
    assert len(f0["players"]) >= 10

    # Windowed radar query (P2-1)
    win_res = client.get("/api/matches/demo-arlington-skyline/radar/window?start=10.0&end=20.0")
    assert win_res.status_code == 200
    win_frames = win_res.json()
    assert len(win_frames) > 0
    for f in win_frames:
        assert 10.0 <= f["timestamp"] <= 20.0

    # Radar meta (P2-1)
    meta_res = client.get("/api/matches/demo-arlington-skyline/radar/meta")
    assert meta_res.status_code == 200
    meta = meta_res.json()
    assert meta["frame_count"] == len(frames)

def test_get_match_analytics(client):
    response = client.get("/api/matches/demo-arlington-skyline/analytics")
    assert response.status_code == 200
    data = response.json()
    assert "home_stats" in data
    assert "shot_map" in data
    assert "pass_locations" in data
    assert "possession_locations" in data
    assert "pass_strings" in data

def test_team_swap_endpoint(client):
    match_id = "demo-arlington-skyline"
    orig_match = client.get(f"/api/matches/{match_id}").json()
    orig_home_score = orig_match["home_score"]
    orig_away_score = orig_match["away_score"]

    # Swap teams
    swap_res = client.post(f"/api/matches/{match_id}/teams/swap")
    assert swap_res.status_code == 200

    swapped_match = client.get(f"/api/matches/{match_id}").json()
    assert swapped_match["home_score"] == orig_away_score
    assert swapped_match["away_score"] == orig_home_score

    # Swap back to preserve demo state
    client.post(f"/api/matches/{match_id}/teams/swap")

def test_homography_projection_and_known_correspondences():
    """Assert known pitch corner correspondences and center mapping (P2-7)."""
    engine = SoccerCVEngine()
    w, h = 1920, 1080
    H = engine.estimate_pitch_homography((h, w))
    assert H is not None
    assert H.shape == (3, 3)

    # 1. Top-left corner
    tl_x, tl_y, in_b = engine.project_point_to_pitch(H, w * 0.05, h * 0.15)
    assert in_b is True
    assert abs(tl_x - 0.0) < 0.5
    assert abs(tl_y - 0.0) < 0.5

    # 2. Top-right corner
    tr_x, tr_y, in_b = engine.project_point_to_pitch(H, w * 0.95, h * 0.15)
    assert in_b is True
    assert abs(tr_x - PITCH_LENGTH) < 0.5
    assert abs(tr_y - 0.0) < 0.5

    # 3. Bottom-right corner
    br_x, br_y, in_b = engine.project_point_to_pitch(H, w * 0.98, h * 0.92)
    assert in_b is True
    assert abs(br_x - PITCH_LENGTH) < 0.5
    assert abs(br_y - PITCH_WIDTH) < 0.5

    # 4. Bottom-left corner
    bl_x, bl_y, in_b = engine.project_point_to_pitch(H, w * 0.02, h * 0.92)
    assert in_b is True
    assert abs(bl_x - 0.0) < 0.5
    assert abs(bl_y - PITCH_WIDTH) < 0.5

    # 5. Image center near pitch center
    c_x, c_y, in_b = engine.project_point_to_pitch(H, w * 0.5, h * 0.5)
    assert in_b is True
    assert 35.0 <= c_x <= 70.0
    assert 20.0 <= c_y <= 50.0

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
