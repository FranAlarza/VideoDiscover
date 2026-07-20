from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_returns_exact_public_contract() -> None:
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "status": "ok",
        "service": "video-downloader-api",
    }


def test_app_factory_creates_isolated_instances() -> None:
    first = create_app(Settings(environment="test", port=8101))
    second = create_app(Settings(environment="test", port=8102))

    assert first is not second
    assert first.state.settings.port == 8101
    assert second.state.settings.port == 8102


def test_production_hides_api_documentation() -> None:
    client = TestClient(create_app(Settings(environment="production")))

    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
