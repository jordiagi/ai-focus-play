from fastapi.testclient import TestClient

from src.app.main import app


def test_vite_dev_origin_can_preflight_sources_endpoint() -> None:
    client = TestClient(app)

    response = client.options(
        "/sources/local",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
