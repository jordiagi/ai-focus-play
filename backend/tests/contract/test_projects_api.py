from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app import dependencies
from src.app.main import app


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("AI_FOCUS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AI_FOCUS_DB_PATH", str(tmp_path / "data" / "app.db"))
    dependencies.clear_caches()
    return TestClient(app)


def test_create_list_and_get_project_use_sqlite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(monkeypatch, tmp_path)

    created = client.post("/projects", json={"name": "Final"})
    project_id = created.json()["project_id"]

    assert created.status_code == 201
    assert created.json()["name"] == "Final"
    assert created.json()["status"] == "draft"
    assert client.get("/projects").json()[0]["project_id"] == project_id
    assert client.get(f"/projects/{project_id}").json()["analysis"] == {
        "overall_status": "not_started",
        "stages": [],
        "no_readable_jersey_numbers": False,
    }
