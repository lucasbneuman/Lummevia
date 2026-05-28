from pathlib import Path

import pytest

from app.core.config import load_settings


def test_settings_use_expected_defaults_when_env_is_missing() -> None:
    settings = load_settings({})

    assert settings.app.name == "lummevia-orchestrator-api"
    assert settings.app.version == "0.1.0"
    assert settings.app.environment == "development"
    assert settings.app.port == 8000
    assert settings.app.public_base_url is None
    assert settings.app.public_api_url is None
    assert settings.app.effective_public_api_url is None
    assert settings.postgres.host == "postgres"
    assert settings.postgres.port == 5432
    assert settings.redis.host == "redis"
    assert settings.redis.port == 6379
    assert settings.redis.password is None
    assert settings.phoenix.enabled is True
    assert settings.phoenix.host == "phoenix"
    assert settings.phoenix.port == 6006
    assert settings.phoenix.base_url == "http://phoenix:6006"
    assert settings.phoenix.api_key is None
    assert settings.youtrack.enabled is False
    assert settings.youtrack.base_url is None
    assert settings.youtrack.token is None
    assert settings.youtrack.project_id is None
    assert settings.youtrack.default_assignee is None
    assert settings.github.token is None
    assert settings.github.org is None
    assert settings.telegram.enabled is False
    assert settings.telegram.bot_token is None
    assert settings.telegram.webhook_secret is None
    assert settings.telegram.bot_username is None
    assert settings.telegram.allowed_chat_ids == ()
    assert settings.deepseek.enabled is False
    assert settings.deepseek.api_key is None
    assert settings.deepseek.base_url == "https://api.deepseek.com"
    assert settings.deepseek.timeout_seconds == 60
    assert settings.runtime_persistence.enabled is False
    assert settings.runtime_persistence.database_url == (
        "postgresql+psycopg://lummevia:lummevia@postgres:5432/lummevia"
    )
    assert settings.kilo.enabled is False
    assert settings.kilo.cli_path is None
    assert settings.kilo.workspace_root is None
    assert settings.kilo.default_timeout_seconds == 300
    assert settings.kilo.dry_run is True
    assert settings.kilo.allowed_repos == ()
    assert settings.kilo.max_output_bytes == 32768


def test_settings_load_safe_values_from_env() -> None:
    kilo_cli_path = Path(__file__).resolve()
    kilo_workspace_root = Path(__file__).resolve().parents[1]
    settings = load_settings(
        {
            "APP_NAME": "lummevia-test-api",
            "APP_VERSION": "0.2.0",
            "APP_ENV": "test",
            "APP_PORT": "9000",
            "PUBLIC_BASE_URL": "https://lummevia.example.com",
            "PUBLIC_API_URL": "https://api.lummevia.example.com",
            "POSTGRES_HOST": "db.internal",
            "POSTGRES_PORT": "5544",
            "POSTGRES_DB": "lummevia_test",
            "POSTGRES_USER": "tester",
            "POSTGRES_PASSWORD": "secret-password",
            "REDIS_HOST": "cache.internal",
            "REDIS_PORT": "6380",
            "REDIS_PASSWORD": "redis-secret",
            "PHOENIX_ENABLED": "false",
            "PHOENIX_HOST": "phoenix.internal",
            "PHOENIX_PORT": "7007",
            "PHOENIX_BASE_URL": "http://phoenix.internal:7007",
            "PHOENIX_API_KEY": "phoenix-api-key",
            "YOUTRACK_ENABLED": "true",
            "YOUTRACK_BASE_URL": "https://youtrack.example.com",
            "YOUTRACK_TOKEN": "yt-token",
            "YOUTRACK_PROJECT_ID": "LUM",
            "YOUTRACK_DEFAULT_ASSIGNEE": "pm-founder",
            "GITHUB_TOKEN": "gh-token",
            "GITHUB_ORG": "lummevia",
            "TELEGRAM_ENABLED": "true",
            "TELEGRAM_BOT_TOKEN": "telegram-token",
            "TELEGRAM_WEBHOOK_SECRET": "telegram-secret",
            "TELEGRAM_BOT_USERNAME": "lummevia_pm_bot",
            "TELEGRAM_ALLOWED_CHAT_IDS": "12345,67890",
            "DEEPSEEK_ENABLED": "true",
            "DEEPSEEK_API_KEY": "ds-key",
            "DEEPSEEK_BASE_URL": "https://deepseek.example.com",
            "DEEPSEEK_TIMEOUT_SECONDS": "75",
            "RUNTIME_PERSISTENCE_ENABLED": "true",
            "RUNTIME_DATABASE_URL": "postgresql+psycopg://tester:secret@db.internal:5544/lummevia_test",
            "KILO_ENABLED": "true",
            "KILO_CLI_PATH": str(kilo_cli_path),
            "KILO_WORKSPACE_ROOT": str(kilo_workspace_root),
            "KILO_DEFAULT_TIMEOUT_SECONDS": "120",
            "KILO_DRY_RUN": "false",
            "KILO_ALLOWED_REPOS": "lummevia-os, sandbox-repo ",
            "KILO_MAX_OUTPUT_BYTES": "2048",
        }
    )

    assert settings.app.name == "lummevia-test-api"
    assert settings.app.version == "0.2.0"
    assert settings.app.environment == "test"
    assert settings.app.port == 9000
    assert settings.app.public_base_url == "https://lummevia.example.com"
    assert settings.app.public_api_url == "https://api.lummevia.example.com"
    assert settings.app.effective_public_api_url == "https://api.lummevia.example.com"
    assert settings.postgres.host == "db.internal"
    assert settings.postgres.port == 5544
    assert settings.postgres.database == "lummevia_test"
    assert settings.postgres.user == "tester"
    assert settings.postgres.password == "secret-password"
    assert settings.redis.host == "cache.internal"
    assert settings.redis.port == 6380
    assert settings.redis.password == "redis-secret"
    assert settings.phoenix.enabled is False
    assert settings.phoenix.host == "phoenix.internal"
    assert settings.phoenix.port == 7007
    assert settings.phoenix.base_url == "http://phoenix.internal:7007"
    assert settings.phoenix.api_key == "phoenix-api-key"
    assert settings.youtrack.enabled is True
    assert settings.youtrack.base_url == "https://youtrack.example.com"
    assert settings.youtrack.token == "yt-token"
    assert settings.youtrack.project_id == "LUM"
    assert settings.youtrack.default_assignee == "pm-founder"
    assert settings.github.token == "gh-token"
    assert settings.github.org == "lummevia"
    assert settings.telegram.enabled is True
    assert settings.telegram.bot_token == "telegram-token"
    assert settings.telegram.webhook_secret == "telegram-secret"
    assert settings.telegram.bot_username == "lummevia_pm_bot"
    assert settings.telegram.allowed_chat_ids == ("12345", "67890")
    assert settings.deepseek.enabled is True
    assert settings.deepseek.api_key == "ds-key"
    assert settings.deepseek.base_url == "https://deepseek.example.com"
    assert settings.deepseek.timeout_seconds == 75
    assert settings.runtime_persistence.enabled is True
    assert settings.runtime_persistence.database_url == (
        "postgresql+psycopg://tester:secret@db.internal:5544/lummevia_test"
    )
    assert settings.kilo.enabled is True
    assert settings.kilo.cli_path == kilo_cli_path
    assert settings.kilo.workspace_root == kilo_workspace_root
    assert settings.kilo.default_timeout_seconds == 120
    assert settings.kilo.dry_run is False
    assert settings.kilo.allowed_repos == ("lummevia-os", "sandbox-repo")
    assert settings.kilo.max_output_bytes == 2048


def test_settings_build_phoenix_base_url_from_host_and_port_when_not_provided() -> None:
    settings = load_settings(
        {
            "PHOENIX_HOST": "phoenix.coolify.internal",
            "PHOENIX_PORT": "7443",
            "PHOENIX_BASE_URL": "",
        }
    )

    assert settings.phoenix.host == "phoenix.coolify.internal"
    assert settings.phoenix.port == 7443
    assert settings.phoenix.base_url == "http://phoenix.coolify.internal:7443"


def test_kilo_disabled_does_not_require_cli_path_or_workspace() -> None:
    settings = load_settings(
        {
            "KILO_ENABLED": "false",
            "KILO_CLI_PATH": "",
            "KILO_WORKSPACE_ROOT": "",
        }
    )

    assert settings.kilo.enabled is False
    assert settings.kilo.cli_path is None
    assert settings.kilo.workspace_root is None


def test_kilo_enabled_requires_cli_path_and_workspace() -> None:
    with pytest.raises(ValueError, match="KILO_CLI_PATH"):
        load_settings(
            {
                "KILO_ENABLED": "true",
                "KILO_WORKSPACE_ROOT": str(Path(__file__).resolve().parents[1]),
            }
        )

    with pytest.raises(ValueError, match="KILO_WORKSPACE_ROOT"):
        load_settings(
            {
                "KILO_ENABLED": "true",
                "KILO_CLI_PATH": str(Path(__file__).resolve()),
            }
        )


def test_kilo_enabled_validates_cli_path_and_workspace_exist() -> None:
    missing_cli = Path(__file__).resolve().parent / "missing-kilo-cli"
    missing_workspace = Path(__file__).resolve().parent / "missing-workspace"

    with pytest.raises(ValueError, match="KILO_CLI_PATH"):
        load_settings(
            {
                "KILO_ENABLED": "true",
                "KILO_CLI_PATH": str(missing_cli),
                "KILO_WORKSPACE_ROOT": str(Path(__file__).resolve().parents[1]),
            }
        )

    with pytest.raises(ValueError, match="KILO_WORKSPACE_ROOT"):
        load_settings(
            {
                "KILO_ENABLED": "true",
                "KILO_CLI_PATH": str(Path(__file__).resolve()),
                "KILO_WORKSPACE_ROOT": str(missing_workspace),
            }
        )


def test_env_example_contains_expected_configuration_variables() -> None:
    env_example = (Path(__file__).resolve().parents[1] / ".env.example").read_text(
        encoding="utf-8"
    )

    expected_variables = [
        "APP_ENV=",
        "APP_PORT=",
        "APP_NAME=",
        "APP_VERSION=",
        "PUBLIC_BASE_URL=",
        "PUBLIC_API_URL=",
        "POSTGRES_HOST=",
        "POSTGRES_PORT=",
        "POSTGRES_DB=",
        "POSTGRES_USER=",
        "POSTGRES_PASSWORD=",
        "REDIS_HOST=",
        "REDIS_PORT=",
        "REDIS_PASSWORD=",
        "SSH_TUNNEL_HOST=",
        "SSH_TUNNEL_USER=",
        "SSH_TUNNEL_PORT=",
        "SSH_TUNNEL_IDENTITY_FILE=",
        "SSH_TUNNEL_POSTGRES_REMOTE_HOST=",
        "SSH_TUNNEL_POSTGRES_REMOTE_PORT=",
        "SSH_TUNNEL_POSTGRES_LOCAL_PORT=",
        "SSH_TUNNEL_REDIS_REMOTE_HOST=",
        "SSH_TUNNEL_REDIS_REMOTE_PORT=",
        "SSH_TUNNEL_REDIS_LOCAL_PORT=",
        "REMOTE_DEV_PHOENIX_ENABLED=",
        "PHOENIX_ENABLED=",
        "PHOENIX_HOST=",
        "PHOENIX_PORT=",
        "PHOENIX_BASE_URL=",
        "PHOENIX_API_KEY=",
        "YOUTRACK_ENABLED=",
        "YOUTRACK_BASE_URL=",
        "YOUTRACK_TOKEN=",
        "YOUTRACK_PROJECT_ID=",
        "YOUTRACK_DEFAULT_ASSIGNEE=",
        "GITHUB_TOKEN=",
        "GITHUB_ORG=",
        "TELEGRAM_ENABLED=",
        "TELEGRAM_BOT_TOKEN=",
        "TELEGRAM_WEBHOOK_SECRET=",
        "TELEGRAM_BOT_USERNAME=",
        "TELEGRAM_ALLOWED_CHAT_IDS=",
        "DEEPSEEK_API_KEY=",
        "DEEPSEEK_BASE_URL=",
        "DEEPSEEK_ENABLED=",
        "DEEPSEEK_TIMEOUT_SECONDS=",
        "MODEL_PM_PROVIDER=",
        "MODEL_PM_NAME=",
        "MODEL_PO_PROVIDER=",
        "MODEL_PO_NAME=",
        "MODEL_DEV_PROVIDER=",
        "MODEL_DEV_NAME=",
        "MODEL_QA_PROVIDER=",
        "MODEL_QA_NAME=",
        "MODEL_QC_PROVIDER=",
        "MODEL_QC_NAME=",
        "RUNTIME_PERSISTENCE_ENABLED=",
        "RUNTIME_DATABASE_URL=",
        "KILO_ENABLED=",
        "KILO_CLI_PATH=",
        "KILO_WORKSPACE_ROOT=",
        "KILO_DEFAULT_TIMEOUT_SECONDS=",
        "KILO_DRY_RUN=",
        "KILO_ALLOWED_REPOS=",
        "KILO_MAX_OUTPUT_BYTES=",
    ]

    for variable in expected_variables:
        assert variable in env_example


def test_compose_passes_deepseek_and_model_router_variables_without_hardcoded_secrets() -> None:
    compose_file = (
        Path(__file__).resolve().parents[1] / "infra" / "compose" / "docker-compose.yml"
    ).read_text(encoding="utf-8")

    expected_entries = [
        "PUBLIC_BASE_URL: ${PUBLIC_BASE_URL:-http://localhost:8000}",
        "PUBLIC_API_URL: ${PUBLIC_API_URL:-}",
        "YOUTRACK_ENABLED: ${YOUTRACK_ENABLED:-false}",
        "YOUTRACK_BASE_URL: ${YOUTRACK_BASE_URL:-}",
        "YOUTRACK_TOKEN: ${YOUTRACK_TOKEN:-}",
        "YOUTRACK_PROJECT_ID: ${YOUTRACK_PROJECT_ID:-}",
        "YOUTRACK_DEFAULT_ASSIGNEE: ${YOUTRACK_DEFAULT_ASSIGNEE:-}",
        "TELEGRAM_ENABLED: ${TELEGRAM_ENABLED:-false}",
        "TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:-}",
        "TELEGRAM_WEBHOOK_SECRET: ${TELEGRAM_WEBHOOK_SECRET:-}",
        "TELEGRAM_BOT_USERNAME: ${TELEGRAM_BOT_USERNAME:-}",
        "TELEGRAM_ALLOWED_CHAT_IDS: ${TELEGRAM_ALLOWED_CHAT_IDS:-}",
        "PHOENIX_API_KEY: ${PHOENIX_API_KEY:-}",
        "DEEPSEEK_ENABLED: ${DEEPSEEK_ENABLED:-false}",
        "DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY:-}",
        "REDIS_PASSWORD: ${REDIS_PASSWORD:-}",
        "DEEPSEEK_BASE_URL: ${DEEPSEEK_BASE_URL:-https://api.deepseek.com}",
        "DEEPSEEK_TIMEOUT_SECONDS: ${DEEPSEEK_TIMEOUT_SECONDS:-60}",
        "MODEL_PM_PROVIDER: ${MODEL_PM_PROVIDER:-DEEPSEEK}",
        "MODEL_PM_NAME: ${MODEL_PM_NAME:-deepseek-chat}",
        "MODEL_PO_PROVIDER: ${MODEL_PO_PROVIDER:-DEEPSEEK}",
        "MODEL_PO_NAME: ${MODEL_PO_NAME:-deepseek-v4-strong-placeholder}",
        "MODEL_DEV_PROVIDER: ${MODEL_DEV_PROVIDER:-DEEPSEEK}",
        "MODEL_DEV_NAME: ${MODEL_DEV_NAME:-deepseek-v4-lite-placeholder}",
        "MODEL_QA_PROVIDER: ${MODEL_QA_PROVIDER:-DEEPSEEK}",
        "MODEL_QA_NAME: ${MODEL_QA_NAME:-deepseek-v4-lite-placeholder}",
        "MODEL_QC_PROVIDER: ${MODEL_QC_PROVIDER:-DEEPSEEK}",
        "MODEL_QC_NAME: ${MODEL_QC_NAME:-deepseek-v4-qc-placeholder}",
    ]

    for entry in expected_entries:
        assert entry in compose_file

    assert "ds-secret" not in compose_file
    assert "sk-" not in compose_file
