import httpx
from fastapi.testclient import TestClient

from app.core.youtrack import set_youtrack_client_override
from lummevia_conversations import ConversationRegistry
from lummevia_integrations import YouTrackClient
from main import app


client = TestClient(app)


def test_telegram_webhook_creates_issue_and_conversation_from_founder_intent(monkeypatch) -> None:
    from app.core import config as config_module
    from app.api.routes import telegram as telegram_routes

    monkeypatch.setattr(
        config_module,
        "settings",
        config_module.load_settings(
            {
                "TELEGRAM_WEBHOOK_SECRET": "secret-token",
                "YOUTRACK_BASE_URL": "https://youtrack.example.com",
                "YOUTRACK_TOKEN": "token-123",
            }
        ),
    )
    monkeypatch.setattr(telegram_routes, "settings", config_module.settings)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/issues":
            return httpx.Response(
                200,
                json={
                    "id": "2-501",
                    "idReadable": "LUM-501",
                    "summary": "Telegram MVP",
                    "description": "Founder intent body",
                    "project": {"shortName": "LUM"},
                    "customFields": [],
                    "tags": [],
                },
            )
        if request.url.path == "/api/issues/LUM-501/comments":
            return httpx.Response(200, json={"id": "4-501", "text": "Founder comment"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    set_youtrack_client_override(
        YouTrackClient(
            base_url="https://youtrack.example.com",
            token="token-123",
            transport=httpx.MockTransport(handler),
        )
    )

    response = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret-token"},
        json={
            "update_id": 1,
            "message": {
                "message_id": 10,
                "date": 1710000000,
                "chat": {"id": 7001, "type": "private"},
                "from": {"id": 44, "is_bot": False, "first_name": "Ana", "username": "ana"},
                "text": "/lummevia project=LUM\nTelegram MVP\nFounder intent body",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "captured"
    assert body["project"] == "LUM"
    assert body["issue_id"] == "LUM-501"
    thread = ConversationRegistry.default().get_thread(body["thread_id"])
    assert thread.issue_id == "LUM-501"
    assert thread.messages[0].metadata["source"] == "telegram"


def test_telegram_webhook_approves_existing_thread(monkeypatch) -> None:
    from app.core import config as config_module
    from app.api.routes import telegram as telegram_routes

    registry = ConversationRegistry.default()
    thread = registry.create_thread(
        topic="Founder thread",
        project="LUM",
        issue_id="LUM-777",
        metadata={"telegram_chat_id": 7001},
    )

    monkeypatch.setattr(
        config_module,
        "settings",
        config_module.load_settings(
            {
                "TELEGRAM_WEBHOOK_SECRET": "secret-token",
                "YOUTRACK_BASE_URL": "https://youtrack.example.com",
                "YOUTRACK_TOKEN": "token-123",
            }
        ),
    )
    monkeypatch.setattr(telegram_routes, "settings", config_module.settings)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/issues/LUM-777/comments":
            return httpx.Response(200, json={"id": "4-777", "text": "Approval comment"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    set_youtrack_client_override(
        YouTrackClient(
            base_url="https://youtrack.example.com",
            token="token-123",
            transport=httpx.MockTransport(handler),
        )
    )

    response = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret-token"},
        json={
            "update_id": 2,
            "message": {
                "message_id": 11,
                "date": 1710000001,
                "chat": {"id": 7001, "type": "private"},
                "from": {"id": 44, "is_bot": False, "first_name": "Ana", "username": "ana"},
                "text": "/approve project=LUM issue=LUM-777",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "approved"
    approved_thread = ConversationRegistry.default().get_thread(thread.thread_id)
    assert approved_thread.status.value == "APPROVED"


def test_telegram_webhook_rejects_invalid_secret(monkeypatch) -> None:
    from app.core import config as config_module
    from app.api.routes import telegram as telegram_routes

    monkeypatch.setattr(
        config_module,
        "settings",
        config_module.load_settings({"TELEGRAM_WEBHOOK_SECRET": "secret-token"}),
    )
    monkeypatch.setattr(telegram_routes, "settings", config_module.settings)

    response = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        json={
            "update_id": 3,
            "message": {
                "message_id": 12,
                "date": 1710000002,
                "chat": {"id": 7001, "type": "private"},
                "from": {"id": 44, "is_bot": False, "first_name": "Ana", "username": "ana"},
                "text": "/lummevia project=LUM\nFounder intent",
            },
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid Telegram webhook secret."


def test_telegram_webhook_ignores_incomplete_payload(monkeypatch) -> None:
    from app.core import config as config_module
    from app.api.routes import telegram as telegram_routes

    monkeypatch.setattr(
        config_module,
        "settings",
        config_module.load_settings({"TELEGRAM_WEBHOOK_SECRET": "secret-token"}),
    )
    monkeypatch.setattr(telegram_routes, "settings", config_module.settings)

    response = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret-token"},
        json={"update_id": 4},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "action": "ignored",
        "project": None,
        "issue_id": None,
        "thread_id": None,
        "youtrack_comment_added": False,
        "conversation_status": None,
        "metadata": {
            "ignored_reason": "missing_message_text",
            "telegram_update_id": 4,
        },
    }
