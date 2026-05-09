from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import quote_plus

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[4]
load_dotenv(BASE_DIR / ".env")


def _read_string(
    env: Mapping[str, str],
    key: str,
    default: str,
) -> str:
    value = env.get(key)

    if value is None:
        return default

    stripped = value.strip()
    return stripped or default


def _read_optional_string(env: Mapping[str, str], key: str) -> str | None:
    value = env.get(key)

    if value is None:
        return None

    stripped = value.strip()
    return stripped or None


def _read_int(env: Mapping[str, str], key: str, default: int) -> int:
    value = env.get(key)

    if value is None or not value.strip():
        return default

    return int(value)


def _read_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    value = env.get(key)

    if value is None or not value.strip():
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppSettings:
    name: str
    version: str
    environment: str
    port: int


@dataclass(frozen=True)
class PostgresSettings:
    host: str
    port: int
    database: str
    user: str
    password: str

    @property
    def sqlalchemy_url(self) -> str:
        user = quote_plus(self.user)
        password = quote_plus(self.password)
        return (
            f"postgresql+psycopg://{user}:{password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


@dataclass(frozen=True)
class RedisSettings:
    host: str
    port: int


@dataclass(frozen=True)
class PhoenixSettings:
    enabled: bool
    host: str
    port: int
    base_url: str


@dataclass(frozen=True)
class YouTrackSettings:
    base_url: str | None
    token: str | None


@dataclass(frozen=True)
class GitHubSettings:
    token: str | None
    org: str | None


@dataclass(frozen=True)
class RuntimePersistenceSettings:
    enabled: bool
    database_url: str


@dataclass(frozen=True)
class Settings:
    app: AppSettings
    postgres: PostgresSettings
    redis: RedisSettings
    phoenix: PhoenixSettings
    youtrack: YouTrackSettings
    github: GitHubSettings
    runtime_persistence: RuntimePersistenceSettings

    @property
    def app_name(self) -> str:
        return self.app.name

    @property
    def app_version(self) -> str:
        return self.app.version

    @property
    def app_env(self) -> str:
        return self.app.environment

    @property
    def app_port(self) -> int:
        return self.app.port


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    environment = os.environ if env is None else env

    phoenix_host = _read_string(environment, "PHOENIX_HOST", "phoenix")
    phoenix_port = _read_int(environment, "PHOENIX_PORT", 6006)
    postgres_settings = PostgresSettings(
        host=_read_string(environment, "POSTGRES_HOST", "postgres"),
        port=_read_int(environment, "POSTGRES_PORT", 5432),
        database=_read_string(environment, "POSTGRES_DB", "lummevia"),
        user=_read_string(environment, "POSTGRES_USER", "lummevia"),
        password=_read_string(environment, "POSTGRES_PASSWORD", "lummevia"),
    )

    return Settings(
        app=AppSettings(
            name=_read_string(environment, "APP_NAME", "lummevia-orchestrator-api"),
            version=_read_string(environment, "APP_VERSION", "0.1.0"),
            environment=_read_string(environment, "APP_ENV", "development"),
            port=_read_int(environment, "APP_PORT", 8000),
        ),
        postgres=postgres_settings,
        redis=RedisSettings(
            host=_read_string(environment, "REDIS_HOST", "redis"),
            port=_read_int(environment, "REDIS_PORT", 6379),
        ),
        phoenix=PhoenixSettings(
            enabled=_read_bool(environment, "PHOENIX_ENABLED", True),
            host=phoenix_host,
            port=phoenix_port,
            base_url=_read_string(
                environment,
                "PHOENIX_BASE_URL",
                f"http://{phoenix_host}:{phoenix_port}",
            ),
        ),
        youtrack=YouTrackSettings(
            base_url=_read_optional_string(environment, "YOUTRACK_BASE_URL"),
            token=_read_optional_string(environment, "YOUTRACK_TOKEN"),
        ),
        github=GitHubSettings(
            token=_read_optional_string(environment, "GITHUB_TOKEN"),
            org=_read_optional_string(environment, "GITHUB_ORG"),
        ),
        runtime_persistence=RuntimePersistenceSettings(
            enabled=_read_bool(environment, "RUNTIME_PERSISTENCE_ENABLED", False),
            database_url=_read_optional_string(environment, "RUNTIME_DATABASE_URL")
            or postgres_settings.sqlalchemy_url,
        ),
    )


settings = load_settings()
