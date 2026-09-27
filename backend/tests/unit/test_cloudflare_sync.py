import pytest
from fastapi.testclient import TestClient

from backend.src.app.main import app
from backend.src.services.cloudflare_sync import cloudflare_sync_service
from backend.src.storage.repository import match_repo

client = TestClient(app)


def test_sync_summary_endpoint():
    matches = match_repo.list_matches()
    assert len(matches) > 0
    match_id = matches[0].id

    response = client.get(f"/api/matches/{match_id}/sync/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["match_id"] == match_id
    assert "video" in data
    assert "clips" in data
    assert "metadata" in data
    assert "public_url" in data
    assert "bucket_name" in data


def test_sync_status_endpoint():
    matches = match_repo.list_matches()
    match_id = matches[0].id

    response = client.get(f"/api/matches/{match_id}/sync/status")
    assert response.status_code == 200
    data = response.json()
    assert data["match_id"] == match_id
    assert "status" in data
    assert "progress_percent" in data


def test_export_match_json_bundle():
    matches = match_repo.list_matches()
    match_id = matches[0].id

    bundle = cloudflare_sync_service.export_match_json_bundle(match_id)
    assert "match.json" in bundle
    assert "events.json" in bundle
    assert "highlights.json" in bundle
    assert "radar.json" in bundle
    assert "index.json" in bundle
    assert bundle["match.json"]["id"] == match_id


def test_trigger_sync_local_bundle_fallback():
    matches = match_repo.list_matches()
    match_id = matches[0].id

    res = cloudflare_sync_service.trigger_sync(match_id, metadata_only=True)
    assert res["status"] in ("started", "already_syncing")

    # Wait briefly for synchronous local export to complete
    import time
    time.sleep(0.5)

    status = cloudflare_sync_service.get_status(match_id)
    assert status["status"] in ("completed", "needs_credentials", "syncing")
