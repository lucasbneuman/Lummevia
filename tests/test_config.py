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
    assert settings.phoenix.host == "phoenix"
    assert settings.phoenix.port == 6006
    assert settings.phoenix.base_url == "http://phoenix:6006"
    assert settings.youtrack.base_url is None
    assert settings.youtrack.token is None
    assert settings.github.token is None
    assert settings.github.org is None


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
            "PHOENIX_HOST": "phoenix.internal",
            "PHOENIX_PORT": "7007",
            "PHOENIX_BASE_URL": "http://phoenix.internal:7007",
            "YOUTRACK_BASE_URL": "https://youtrack.example.com",
            "YOUTRACK_TOKEN": "yt-token",
            "GITHUB_TOKEN": "gh-token",
            "GITHUB_ORG": "lummevia",
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
    assert settings.phoenix.host == "phoenix.internal"
    assert settings.phoenix.port == 7007
    assert settings.phoenix.base_url == "http://phoenix.internal:7007"
    assert settings.youtrack.base_url == "https://youtrack.example.com"
    assert settings.youtrack.token == "yt-token"
    assert settings.github.token == "gh-token"
    assert settings.github.org == "lummevia"


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
        "PHOENIX_HOST=",
        "PHOENIX_PORT=",
        "PHOENIX_BASE_URL=",
        "YOUTRACK_BASE_URL=",
        "YOUTRACK_TOKEN=",
        "GITHUB_TOKEN=",
        "GITHUB_ORG=",
    ]

    for variable in expected_variables:
        assert variable in env_example
