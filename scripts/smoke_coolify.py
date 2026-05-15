from __future__ import annotations

import argparse
import json
from typing import Any

import httpx


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _get_json(client: httpx.Client, path: str) -> dict[str, Any]:
    response = client.get(path)
    response.raise_for_status()
    return response.json()


def run_smoke_tests(
    *,
    base_url: str,
    youtrack_enabled: bool = False,
    telegram_secret: str | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_seconds) as client:
        health = _get_json(client, "/health")
        _assert(health["status"] == "ok", "/health is not ok.")
        results["health"] = health

        readiness_response = client.get("/readiness")
        _assert(readiness_response.status_code in {200, 503}, "/readiness returned an unexpected status.")
        readiness = readiness_response.json()
        _assert("ready" in readiness, "/readiness payload is missing 'ready'.")
        results["readiness"] = readiness

        info = _get_json(client, "/info")
        serialized_info = json.dumps(info).casefold()
        for secret_key in ("token", "password", "api_key", "secret"):
            _assert(secret_key not in serialized_info, f"/info exposed a secret-like field: {secret_key}")
        results["info"] = info

        persistence = _get_json(client, "/persistence/health")
        _assert("enabled" in persistence, "/persistence/health is missing 'enabled'.")
        results["persistence"] = persistence

        if youtrack_enabled:
            youtrack_health = _get_json(client, "/youtrack/health")
            _assert(youtrack_health["status"] == "ok", "/youtrack/health is not ok.")
            results["youtrack"] = youtrack_health

        webhook_headers = {}
        webhook_params = {}
        if telegram_secret:
            webhook_params["secret"] = telegram_secret
        webhook_response = client.post(
            "/telegram/webhook",
            params=webhook_params,
            headers=webhook_headers,
            json={"update_id": 999999},
        )
        webhook_response.raise_for_status()
        webhook_body = webhook_response.json()
        _assert(webhook_body["action"] == "ignored", "Telegram webhook smoke test was not ignored as expected.")
        results["telegram_webhook"] = webhook_body

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Coolify deployment smoke tests.")
    parser.add_argument("--base-url", required=True, help="Base URL for the deployed orchestrator API.")
    parser.add_argument("--youtrack-enabled", action="store_true", help="Check /youtrack/health as part of the smoke test.")
    parser.add_argument("--telegram-secret", default=None, help="Telegram webhook secret if the endpoint requires one.")
    parser.add_argument("--timeout-seconds", type=float, default=10.0, help="HTTP timeout per request.")
    args = parser.parse_args()

    results = run_smoke_tests(
        base_url=args.base_url,
        youtrack_enabled=args.youtrack_enabled,
        telegram_secret=args.telegram_secret,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
