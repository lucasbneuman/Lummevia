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


def _read_optional_path(env: Mapping[str, str], key: str) -> Path | None:
    value = _read_optional_string(env, key)
    return Path(value).expanduser() if value is not None else None


def _read_csv(env: Mapping[str, str], key: str) -> tuple[str, ...]:
    value = env.get(key)
    if value is None or not value.strip():
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


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
class DeepSeekSettings:
    enabled: bool
    api_key: str | None
    base_url: str
    timeout_seconds: int


@dataclass(frozen=True)
class RuntimePersistenceSettings:
    enabled: bool
    database_url: str


@dataclass(frozen=True)
class KiloSettings:
    enabled: bool
    cli_path: Path | None
    workspace_root: Path | None
    default_timeout_seconds: int
    dry_run: bool
    allowed_repos: tuple[str, ...]
    max_output_bytes: int


@dataclass(frozen=True)
class Settings:
    app: AppSettings
    postgres: PostgresSettings
    redis: RedisSettings
    phoenix: PhoenixSettings
    youtrack: YouTrackSettings
    github: GitHubSettings
    deepseek: DeepSeekSettings
    runtime_persistence: RuntimePersistenceSettings
    kilo: KiloSettings

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
    kilo_enabled = _read_bool(environment, "KILO_ENABLED", False)
    kilo_cli_path = _read_optional_path(environment, "KILO_CLI_PATH")
    kilo_workspace_root = _read_optional_path(environment, "KILO_WORKSPACE_ROOT")
    kilo_default_timeout_seconds = _read_int(
        environment, "KILO_DEFAULT_TIMEOUT_SECONDS", 300
    )
    kilo_dry_run = _read_bool(environment, "KILO_DRY_RUN", True)
    kilo_allowed_repos = _read_csv(environment, "KILO_ALLOWED_REPOS")
    kilo_max_output_bytes = _read_int(environment, "KILO_MAX_OUTPUT_BYTES", 32768)

    if kilo_enabled:
        if kilo_cli_path is None:
            raise ValueError("KILO_CLI_PATH is required when KILO_ENABLED=true.")
        if kilo_workspace_root is None:
            raise ValueError("KILO_WORKSPACE_ROOT is required when KILO_ENABLED=true.")
        if not kilo_cli_path.exists():
            raise ValueError(
                "KILO_CLI_PATH must point to an existing filesystem path when "
                "KILO_ENABLED=true."
            )
        if not kilo_workspace_root.exists():
            raise ValueError(
                "KILO_WORKSPACE_ROOT must point to an existing filesystem path when "
                "KILO_ENABLED=true."
            )

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
        deepseek=DeepSeekSettings(
            enabled=_read_bool(environment, "DEEPSEEK_ENABLED", False),
            api_key=_read_optional_string(environment, "DEEPSEEK_API_KEY"),
            base_url=_read_string(
                environment,
                "DEEPSEEK_BASE_URL",
                "https://api.deepseek.com",
            ),
            timeout_seconds=_read_int(
                environment,
                "DEEPSEEK_TIMEOUT_SECONDS",
                60,
            ),
        ),
        runtime_persistence=RuntimePersistenceSettings(
            enabled=_read_bool(environment, "RUNTIME_PERSISTENCE_ENABLED", False),
            database_url=_read_optional_string(environment, "RUNTIME_DATABASE_URL")
            or postgres_settings.sqlalchemy_url,
        ),
        kilo=KiloSettings(
            enabled=kilo_enabled,
            cli_path=kilo_cli_path,
            workspace_root=kilo_workspace_root,
            default_timeout_seconds=kilo_default_timeout_seconds,
            dry_run=kilo_dry_run,
            allowed_repos=kilo_allowed_repos,
            max_output_bytes=kilo_max_output_bytes,
        ),
    )


settings = load_settings()
