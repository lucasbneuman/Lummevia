from app.api.routes import system as system_routes
from fastapi.testclient import TestClient

from app.core.config import settings
from main import app


client = TestClient(app)


def test_health_returns_ok_status(monkeypatch) -> None:
    monkeypatch.setattr(system_routes, "_check_postgres", lambda: {"status": "skipped"})
    monkeypatch.setattr(system_routes, "_check_redis", lambda: {"status": "skipped"})
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_info_returns_runtime_metadata() -> None:
    response = client.get("/info")

    assert response.status_code == 200
    assert response.json()["app"] == settings.app_name
    assert response.json()["version"] == settings.app_version
    assert response.json()["environment"] == settings.app_env
    assert response.json()["public_base_url"] == settings.app.public_base_url
    assert response.json()["integrations"] == {
        "telegram_enabled": settings.telegram.enabled,
        "youtrack_enabled": settings.youtrack.enabled,
        "deepseek_enabled": settings.deepseek.enabled,
        "phoenix_enabled": settings.phoenix.enabled,
        "kilo_enabled": settings.kilo.enabled,
        "kilo_dry_run": settings.kilo.dry_run,
        "runtime_persistence_enabled": settings.runtime_persistence.enabled,
    }


def test_info_does_not_expose_secrets() -> None:
    response = client.get("/info")

    assert response.status_code == 200
    body = response.json()

    assert "token" not in body
    assert "github_token" not in body
    assert "youtrack_token" not in body
    assert "postgres_password" not in body
    assert "deepseek_api_key" not in body
    assert "api_key" not in body
