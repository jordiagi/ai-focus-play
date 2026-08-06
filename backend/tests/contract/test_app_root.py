from fastapi.testclient import TestClient

from src.app.main import app


def test_root_explains_api_and_frontend_url() -> None:
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["frontend"] == "http://localhost:5173"
