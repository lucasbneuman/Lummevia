from __future__ import annotations

import importlib.util
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.core import persistence as persistence_runtime
from app.core.config import load_settings
from app.core.youtrack import set_youtrack_client_override
from app.api.routes import system as system_routes
from app.api.routes import telegram as telegram_routes
from lummevia_integrations import YouTrackClient
from main import app


client = TestClient(app)


def test_health_reports_ok_when_basic_checks_pass(monkeypatch) -> None:
    monkeypatch.setattr(system_routes, "settings", load_settings({}))
    monkeypatch.setattr(system_routes, "_check_postgres", lambda: {"status": "skipped"})
    monkeypatch.setattr(system_routes, "_check_redis", lambda: {"status": "skipped"})

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["api"]["status"] == "ok"
    assert body["checks"]["config"]["status"] == "ok"


def test_readiness_reports_ready_when_optional_services_are_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        system_routes,
        "settings",
        load_settings(
            {
                "APP_ENV": "test",
                "PHOENIX_ENABLED": "false",
                "KILO_ENABLED": "false",
                "KILO_DRY_RUN": "true",
                "RUNTIME_PERSISTENCE_ENABLED": "false",
                "TELEGRAM_ENABLED": "false",
                "YOUTRACK_ENABLED": "false",
                "DEEPSEEK_ENABLED": "false",
            }
        ),
    )
    persistence_runtime.configure_operational_persistence(None)

    response = client.get("/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["status"] == "ready"
    assert body["checks"]["persistence"]["status"] == "disabled"
    assert body["checks"]["telegram"]["status"] == "disabled"
    assert body["checks"]["youtrack"]["status"] == "disabled"
    assert body["checks"]["deepseek"]["status"] == "disabled"
    assert body["checks"]["kilo"]["status"] == "safe"


def test_readiness_fails_clearly_when_enabled_services_are_missing_config(monkeypatch) -> None:
    kilo_cli_path = Path(__file__).resolve()
    kilo_workspace_root = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(
        system_routes,
        "settings",
        load_settings(
            {
                "APP_ENV": "test",
                "RUNTIME_PERSISTENCE_ENABLED": "true",
                "TELEGRAM_ENABLED": "true",
                "YOUTRACK_ENABLED": "true",
                "DEEPSEEK_ENABLED": "true",
                "KILO_ENABLED": "true",
                "KILO_DRY_RUN": "false",
                "KILO_CLI_PATH": str(kilo_cli_path),
                "KILO_WORKSPACE_ROOT": str(kilo_workspace_root),
            }
        ),
    )
    persistence_runtime.configure_operational_persistence(None)

    response = client.get("/readiness")

    assert response.status_code == 503
    body = response.json()
    assert body["ready"] is False
    assert body["checks"]["persistence"]["status"] == "error"
    assert body["checks"]["telegram"]["status"] == "error"
    assert body["checks"]["youtrack"]["status"] == "error"
    assert body["checks"]["deepseek"]["status"] == "error"
    assert body["checks"]["kilo"]["status"] == "error"


def test_telegram_readiness_prefers_public_api_url(monkeypatch) -> None:
    monkeypatch.setattr(
        system_routes,
        "settings",
        load_settings(
            {
                "APP_ENV": "test",
                "RUNTIME_PERSISTENCE_ENABLED": "false",
                "TELEGRAM_ENABLED": "true",
                "TELEGRAM_BOT_TOKEN": "telegram-token",
                "PUBLIC_BASE_URL": "https://lummevia.example.com",
                "PUBLIC_API_URL": "https://api.lummevia.example.com",
                "YOUTRACK_ENABLED": "false",
                "DEEPSEEK_ENABLED": "false",
                "PHOENIX_ENABLED": "false",
                "KILO_ENABLED": "false",
            }
        ),
    )
    persistence_runtime.configure_operational_persistence(None)

    response = client.get("/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["checks"]["telegram"]["status"] == "ok"
    assert (
        body["checks"]["telegram"]["webhook_url"]
        == "https://api.lummevia.example.com/telegram/webhook"
    )


def test_telegram_webhook_can_use_query_secret_and_ignore_incomplete_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        telegram_routes,
        "settings",
        load_settings(
            {
                "TELEGRAM_WEBHOOK_SECRET": "secret-token",
            }
        ),
    )

    response = client.post("/telegram/webhook?secret=secret-token", json={"update_id": 99})

    assert response.status_code == 200
    assert response.json()["action"] == "ignored"


def test_youtrack_health_reports_disabled_when_integration_is_off(monkeypatch) -> None:
    from app.api.routes import youtrack as youtrack_routes

    monkeypatch.setattr(
        youtrack_routes,
        "settings",
        load_settings({"YOUTRACK_ENABLED": "false"}),
    )
    set_youtrack_client_override(None)

    response = client.get("/youtrack/health")

    assert response.status_code == 200
    assert response.json()["status"] == "disabled"


def test_youtrack_health_reports_ok_without_exposing_token(monkeypatch) -> None:
    from app.api.routes import youtrack as youtrack_routes

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/issues":
            return httpx.Response(200, json=[])
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    monkeypatch.setattr(
        youtrack_routes,
        "settings",
        load_settings(
            {
                "YOUTRACK_ENABLED": "true",
                "YOUTRACK_BASE_URL": "https://youtrack.example.com",
                "YOUTRACK_TOKEN": "token-123",
            }
        ),
    )
    set_youtrack_client_override(
        YouTrackClient(
            base_url="https://youtrack.example.com",
            token="token-123",
            transport=httpx.MockTransport(handler),
        )
    )

    response = client.get("/youtrack/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["configured"] is True
    assert body["token_present"] is True
    assert "token-123" not in response.text


def test_coolify_compose_exists_with_expected_services_and_no_hardcoded_secrets() -> None:
    compose_file = (
        Path(__file__).resolve().parents[1]
        / "infra"
        / "compose"
        / "docker-compose.coolify.yml"
    ).read_text(encoding="utf-8")

    assert "orchestrator-api:" in compose_file
    assert "postgres:" in compose_file
    assert "redis:" in compose_file
    assert "healthcheck:" in compose_file
    assert "volumes:" in compose_file
    assert "TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}" in compose_file
    assert "YOUTRACK_TOKEN: ${YOUTRACK_TOKEN}" in compose_file
    assert "DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY}" in compose_file
    assert "REDIS_PASSWORD: ${REDIS_PASSWORD}" in compose_file
    assert "redis-server --appendonly yes --requirepass" in compose_file
    assert "redis-cli -a" in compose_file
    assert "REDIS_PASSWORD" in compose_file
    assert "token-123" not in compose_file
    assert "sk-" not in compose_file


def test_orchestrator_image_includes_coolify_healthcheck_tool() -> None:
    dockerfile = (
        Path(__file__).resolve().parents[1]
        / "infra"
        / "docker"
        / "orchestrator-api.Dockerfile"
    ).read_text(encoding="utf-8")

    assert "apt-get install" in dockerfile
    assert "curl" in dockerfile


def test_remote_dev_compose_uses_host_tunnel_without_local_state_services() -> None:
    compose_file = (
        Path(__file__).resolve().parents[1]
        / "infra"
        / "compose"
        / "docker-compose.remote-dev.yml"
    ).read_text(encoding="utf-8")

    assert "orchestrator-api:" in compose_file
    assert "network_mode: host" in compose_file
    assert "POSTGRES_HOST: 127.0.0.1" in compose_file
    assert "POSTGRES_PORT: ${SSH_TUNNEL_POSTGRES_LOCAL_PORT:-15432}" in compose_file
    assert "REDIS_HOST: 127.0.0.1" in compose_file
    assert "REDIS_PORT: ${SSH_TUNNEL_REDIS_LOCAL_PORT:-16379}" in compose_file
    assert "REDIS_PASSWORD: ${REDIS_PASSWORD:-}" in compose_file
    assert "PHOENIX_ENABLED: ${REMOTE_DEV_PHOENIX_ENABLED:-false}" in compose_file
    assert "\n  postgres:" not in compose_file
    assert "\n  redis:" not in compose_file
    assert "TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:-}" in compose_file
    assert "YOUTRACK_TOKEN: ${YOUTRACK_TOKEN:-}" in compose_file
    assert "DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY:-}" in compose_file
    assert "token-123" not in compose_file
    assert "sk-" not in compose_file


def test_smoke_coolify_script_is_importable() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "smoke_coolify.py"
    spec = importlib.util.spec_from_file_location("smoke_coolify", script_path)

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert hasattr(module, "run_smoke_tests")
