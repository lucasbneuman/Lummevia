from pathlib import Path

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
    assert settings.runtime_persistence.enabled is False
    assert settings.runtime_persistence.database_url == (
        "postgresql+psycopg://lummevia:lummevia@postgres:5432/lummevia"
    )


def test_settings_load_safe_values_from_env() -> None:
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
            "RUNTIME_PERSISTENCE_ENABLED": "true",
            "RUNTIME_DATABASE_URL": "postgresql+psycopg://tester:secret@db.internal:5544/lummevia_test",
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
    assert settings.runtime_persistence.enabled is True
    assert settings.runtime_persistence.database_url == (
        "postgresql+psycopg://tester:secret@db.internal:5544/lummevia_test"
    )


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
        "RUNTIME_PERSISTENCE_ENABLED=",
        "RUNTIME_DATABASE_URL=",
    ]

    for variable in expected_variables:
        assert variable in env_example
