from pathlib import Path

import pytest

from app.core.config import load_settings


def test_settings_use_expected_defaults_when_env_is_missing() -> None:
    settings = load_settings({})

    assert settings.app.name == "lummevia-orchestrator-api"
    assert settings.app.version == "0.1.0"
    assert settings.app.environment == "development"
    assert settings.app.port == 8000
    assert settings.postgres.host == "postgres"
    assert settings.postgres.port == 5432
    assert settings.redis.host == "redis"
    assert settings.redis.port == 6379
    assert settings.phoenix.enabled is True
    assert settings.phoenix.host == "phoenix"
    assert settings.phoenix.port == 6006
    assert settings.phoenix.base_url == "http://phoenix:6006"
    assert settings.youtrack.base_url is None
    assert settings.youtrack.token is None
    assert settings.github.token is None
    assert settings.github.org is None
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


def test_settings_load_safe_values_from_env() -> None:
    kilo_cli_path = Path(__file__).resolve()
    kilo_workspace_root = Path(__file__).resolve().parents[1]
    settings = load_settings(
        {
            "APP_NAME": "lummevia-test-api",
            "APP_VERSION": "0.2.0",
            "APP_ENV": "test",
            "APP_PORT": "9000",
            "POSTGRES_HOST": "db.internal",
            "POSTGRES_PORT": "5544",
            "POSTGRES_DB": "lummevia_test",
            "POSTGRES_USER": "tester",
            "POSTGRES_PASSWORD": "secret-password",
            "REDIS_HOST": "cache.internal",
            "REDIS_PORT": "6380",
            "PHOENIX_ENABLED": "false",
            "PHOENIX_HOST": "phoenix.internal",
            "PHOENIX_PORT": "7007",
            "PHOENIX_BASE_URL": "http://phoenix.internal:7007",
            "YOUTRACK_BASE_URL": "https://youtrack.example.com",
            "YOUTRACK_TOKEN": "yt-token",
            "GITHUB_TOKEN": "gh-token",
            "GITHUB_ORG": "lummevia",
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
        }
    )

    assert settings.app.name == "lummevia-test-api"
    assert settings.app.version == "0.2.0"
    assert settings.app.environment == "test"
    assert settings.app.port == 9000
    assert settings.postgres.host == "db.internal"
    assert settings.postgres.port == 5544
    assert settings.postgres.database == "lummevia_test"
    assert settings.postgres.user == "tester"
    assert settings.postgres.password == "secret-password"
    assert settings.redis.host == "cache.internal"
    assert settings.redis.port == 6380
    assert settings.phoenix.enabled is False
    assert settings.phoenix.host == "phoenix.internal"
    assert settings.phoenix.port == 7007
    assert settings.phoenix.base_url == "http://phoenix.internal:7007"
    assert settings.youtrack.base_url == "https://youtrack.example.com"
    assert settings.youtrack.token == "yt-token"
    assert settings.github.token == "gh-token"
    assert settings.github.org == "lummevia"
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
        "POSTGRES_HOST=",
        "POSTGRES_PORT=",
        "POSTGRES_DB=",
        "POSTGRES_USER=",
        "POSTGRES_PASSWORD=",
        "REDIS_HOST=",
        "REDIS_PORT=",
        "PHOENIX_ENABLED=",
        "PHOENIX_HOST=",
        "PHOENIX_PORT=",
        "PHOENIX_BASE_URL=",
        "YOUTRACK_BASE_URL=",
        "YOUTRACK_TOKEN=",
        "GITHUB_TOKEN=",
        "GITHUB_ORG=",
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
        "RUNTIME_PERSISTENCE_ENABLED=",
        "RUNTIME_DATABASE_URL=",
        "KILO_ENABLED=",
        "KILO_CLI_PATH=",
        "KILO_WORKSPACE_ROOT=",
        "KILO_DEFAULT_TIMEOUT_SECONDS=",
        "KILO_DRY_RUN=",
    ]

    for variable in expected_variables:
        assert variable in env_example
