from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _read_env(name: str, *, required: bool = False) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        if required:
            raise RuntimeError(f"{name} is required.")
        return None
    return value.strip()


def _webhook_url(explicit_url: str | None) -> str:
    if explicit_url is not None and explicit_url.strip():
        return explicit_url.strip()
    public_api_url = _read_env("PUBLIC_API_URL")
    public_base_url = _read_env("PUBLIC_BASE_URL")
    base_url = public_api_url or public_base_url
    if base_url is None:
        raise RuntimeError("PUBLIC_API_URL or PUBLIC_BASE_URL is required.")
    return base_url.rstrip("/") + "/telegram/webhook"


def _request(
    *,
    bot_token: str,
    method: str,
    payload: dict[str, Any] | None = None,
    timeout_seconds: float,
) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Telegram API request failed: {exc}") from exc

    if body.get("ok") is not True:
        raise RuntimeError(json.dumps(body, indent=2, sort_keys=True))
    return body


def set_webhook(args: argparse.Namespace) -> dict[str, Any]:
    bot_token = _read_env("TELEGRAM_BOT_TOKEN", required=True)
    assert bot_token is not None
    payload: dict[str, Any] = {
        "url": _webhook_url(args.url),
        "drop_pending_updates": args.drop_pending_updates,
    }
    secret = _read_env("TELEGRAM_WEBHOOK_SECRET")
    if secret is not None:
        payload["secret_token"] = secret
    allowed_updates = [item.strip() for item in args.allowed_updates.split(",") if item.strip()]
    if allowed_updates:
        payload["allowed_updates"] = allowed_updates
    return _request(
        bot_token=bot_token,
        method="setWebhook",
        payload=payload,
        timeout_seconds=args.timeout_seconds,
    )


def get_webhook_info(args: argparse.Namespace) -> dict[str, Any]:
    bot_token = _read_env("TELEGRAM_BOT_TOKEN", required=True)
    assert bot_token is not None
    return _request(
        bot_token=bot_token,
        method="getWebhookInfo",
        timeout_seconds=args.timeout_seconds,
    )


def delete_webhook(args: argparse.Namespace) -> dict[str, Any]:
    bot_token = _read_env("TELEGRAM_BOT_TOKEN", required=True)
    assert bot_token is not None
    return _request(
        bot_token=bot_token,
        method="deleteWebhook",
        payload={"drop_pending_updates": args.drop_pending_updates},
        timeout_seconds=args.timeout_seconds,
    )


def main() -> int:
    _load_env_file(ROOT_DIR / ".env")

    parser = argparse.ArgumentParser(description="Manage the Lummevia Telegram webhook.")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="HTTP timeout for Telegram API calls.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    set_parser = subparsers.add_parser("set", help="Register the Telegram webhook.")
    set_parser.add_argument(
        "--url",
        default=None,
        help="Webhook URL. Defaults to PUBLIC_API_URL or PUBLIC_BASE_URL + /telegram/webhook.",
    )
    set_parser.add_argument(
        "--allowed-updates",
        default="message",
        help="Comma-separated Telegram update types to deliver.",
    )
    set_parser.add_argument(
        "--drop-pending-updates",
        action="store_true",
        help="Discard pending updates when setting the webhook.",
    )
    set_parser.set_defaults(handler=set_webhook)

    info_parser = subparsers.add_parser("info", help="Show current webhook info.")
    info_parser.set_defaults(handler=get_webhook_info)

    delete_parser = subparsers.add_parser("delete", help="Delete the Telegram webhook.")
    delete_parser.add_argument(
        "--drop-pending-updates",
        action="store_true",
        help="Discard pending updates when deleting the webhook.",
    )
    delete_parser.set_defaults(handler=delete_webhook)

    args = parser.parse_args()
    try:
        result = args.handler(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
