from __future__ import annotations

import socket
from pathlib import Path

import psycopg
from fastapi import APIRouter, Response, status

from app.core import persistence as persistence_runtime
from app.core.config import settings


router = APIRouter()


@router.get("/health", tags=["system"])
def healthcheck(response: Response) -> dict[str, object]:
    checks = {
        "api": {"status": "ok"},
        "config": _check_basic_config(),
        "postgres": _check_postgres(),
        "redis": _check_redis(),
    }
    unhealthy = [name for name, result in checks.items() if result["status"] == "error"]
    if unhealthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unhealthy", "checks": checks}
    return {"status": "ok", "checks": checks}


@router.get("/readiness", tags=["system"])
def readiness(response: Response) -> dict[str, object]:
    checks = {
        "persistence": _check_persistence_readiness(),
        "telegram": _check_telegram_readiness(),
        "youtrack": _check_youtrack_readiness(),
        "deepseek": _check_deepseek_readiness(),
        "phoenix": _check_phoenix_readiness(),
        "kilo": _check_kilo_readiness(),
    }
    failed = [name for name, result in checks.items() if result["status"] == "error"]
    ready = not failed
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready else "not_ready",
        "ready": ready,
        "checks": checks,
    }


@router.get("/info", tags=["system"])
def info() -> dict[str, object]:
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "public_base_url": settings.app.public_base_url,
        "public_api_url": settings.app.public_api_url,
        "integrations": {
            "telegram_enabled": settings.telegram.enabled,
            "youtrack_enabled": settings.youtrack.enabled,
            "deepseek_enabled": settings.deepseek.enabled,
            "phoenix_enabled": settings.phoenix.enabled,
            "kilo_enabled": settings.kilo.enabled,
            "kilo_dry_run": settings.kilo.dry_run,
            "runtime_persistence_enabled": settings.runtime_persistence.enabled,
        },
    }


def _check_basic_config() -> dict[str, object]:
    if not settings.app.name.strip():
        return {"status": "error", "detail": "APP_NAME is required."}
    if not settings.app.version.strip():
        return {"status": "error", "detail": "APP_VERSION is required."}
    if settings.app.port <= 0:
        return {"status": "error", "detail": "APP_PORT must be greater than zero."}
    return {"status": "ok"}


def _check_postgres() -> dict[str, object]:
    if not settings.runtime_persistence.enabled:
        return {"status": "skipped", "detail": "Runtime persistence is disabled."}

    try:
        with psycopg.connect(
            host=settings.postgres.host,
            port=settings.postgres.port,
            dbname=settings.postgres.database,
            user=settings.postgres.user,
            password=settings.postgres.password,
            connect_timeout=2,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
    except Exception as exc:
        return {"status": "error", "detail": f"Postgres check failed: {exc}"}

    return {"status": "ok"}


def _check_redis() -> dict[str, object]:
    if settings.app_env == "test":
        return {"status": "skipped", "detail": "Redis probe skipped in test environment."}

    try:
        with socket.create_connection(
            (settings.redis.host, settings.redis.port),
            timeout=2,
        ) as connection:
            if settings.redis.password is not None:
                encoded_password = settings.redis.password.encode("utf-8")
                auth_command = (
                    b"*2\r\n$4\r\nAUTH\r\n$"
                    + str(len(encoded_password)).encode("ascii")
                    + b"\r\n"
                    + encoded_password
                    + b"\r\n"
                )
                connection.sendall(auth_command)
                auth_reply = connection.recv(128)
                if not auth_reply.startswith(b"+OK"):
                    return {"status": "error", "detail": "Redis AUTH failed."}
            connection.sendall(b"*1\r\n$4\r\nPING\r\n")
            reply = connection.recv(16)
    except Exception as exc:
        return {"status": "error", "detail": f"Redis check failed: {exc}"}

    if not reply.startswith(b"+PONG"):
        return {"status": "error", "detail": "Redis did not return PONG."}
    return {"status": "ok"}


def _check_persistence_readiness() -> dict[str, object]:
    if not settings.runtime_persistence.enabled:
        return {"status": "disabled"}
    if persistence_runtime.operational_persistence is None:
        return {"status": "error", "detail": "Persistence is enabled but not initialized."}
    if not persistence_runtime.rehydration_completed:
        return {
            "status": "error",
            "detail": "Persistence is enabled but registry rehydration has not completed.",
        }
    return {"status": "ok"}


def _check_telegram_readiness() -> dict[str, object]:
    if not settings.telegram.enabled:
        return {"status": "disabled"}
    missing = []
    if settings.telegram.bot_token is None:
        missing.append("TELEGRAM_BOT_TOKEN")
    if settings.app.effective_public_api_url is None:
        missing.append("PUBLIC_API_URL or PUBLIC_BASE_URL")
    if missing:
        return {
            "status": "error",
            "detail": f"Telegram is enabled but missing: {', '.join(missing)}.",
        }
    webhook_url = settings.app.effective_public_api_url.rstrip("/") + "/telegram/webhook"
    return {
        "status": "ok",
        "webhook_url": webhook_url,
        "allowed_chat_ids_configured": bool(settings.telegram.allowed_chat_ids),
    }


def _check_youtrack_readiness() -> dict[str, object]:
    if not settings.youtrack.enabled:
        return {"status": "disabled"}
    missing = []
    if settings.youtrack.base_url is None:
        missing.append("YOUTRACK_BASE_URL")
    if settings.youtrack.token is None:
        missing.append("YOUTRACK_TOKEN")
    if missing:
        return {
            "status": "error",
            "detail": f"YouTrack is enabled but missing: {', '.join(missing)}.",
        }
    return {
        "status": "ok",
        "project_id_configured": settings.youtrack.project_id is not None,
        "default_assignee_configured": settings.youtrack.default_assignee is not None,
    }


def _check_deepseek_readiness() -> dict[str, object]:
    if not settings.deepseek.enabled:
        return {"status": "disabled"}
    if settings.deepseek.api_key is None:
        return {
            "status": "error",
            "detail": "DeepSeek is enabled but DEEPSEEK_API_KEY is missing.",
        }
    return {"status": "ok", "base_url": settings.deepseek.base_url}


def _check_phoenix_readiness() -> dict[str, object]:
    if not settings.phoenix.enabled:
        return {"status": "disabled"}
    return {
        "status": "ok",
        "base_url": settings.phoenix.base_url,
        "api_key_configured": settings.phoenix.api_key is not None,
        "non_blocking_export": True,
    }


def _check_kilo_readiness() -> dict[str, object]:
    if not settings.kilo.enabled:
        return {"status": "safe", "detail": "Kilo is disabled."}
    if settings.kilo.dry_run:
        return {"status": "safe", "detail": "Kilo is enabled in dry-run mode."}
    if settings.kilo.workspace_root is None:
        return {"status": "error", "detail": "KILO_WORKSPACE_ROOT is required."}
    if not settings.kilo.workspace_root.is_absolute():
        return {"status": "error", "detail": "KILO_WORKSPACE_ROOT must be absolute."}
    if _is_unsafe_workspace_root(settings.kilo.workspace_root):
        return {
            "status": "error",
            "detail": "Kilo real is active with an unsafe workspace root.",
        }
    if not settings.kilo.allowed_repos:
        return {
            "status": "error",
            "detail": "Kilo real is active without a repository allowlist.",
        }
    return {"status": "warning", "detail": "Kilo real is active with allowlist controls."}


def _is_unsafe_workspace_root(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return True
    return len(resolved.parts) <= 1
