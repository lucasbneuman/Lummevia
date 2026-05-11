from fastapi.testclient import TestClient

from app.core.config import settings
from main import app


client = TestClient(app)


def test_health_returns_ok_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_info_returns_runtime_metadata() -> None:
    response = client.get("/info")

    assert response.status_code == 200
    assert response.json() == {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }


def test_info_does_not_expose_secrets() -> None:
    response = client.get("/info")

    assert response.status_code == 200
    body = response.json()

    assert "token" not in body
    assert "github_token" not in body
    assert "youtrack_token" not in body
    assert "postgres_password" not in body
    assert "openrouter_api_key" not in body
    assert "api_key" not in body
