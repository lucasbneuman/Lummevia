import httpx
from fastapi.testclient import TestClient

from app.core.youtrack import set_youtrack_client_override
from lummevia_integrations import YouTrackClient
from main import app


client = TestClient(app)


def test_projects_handoff_endpoints_return_created_handoff(monkeypatch) -> None:
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
        if request.url.path == "/api/issues/LUM-111":
            return httpx.Response(
                200,
                json={
                    "id": "2-111",
                    "idReadable": "LUM-111",
                    "summary": "Medical booking app",
                    "description": "Main issue",
                    "project": {"shortName": "LUM"},
                    "customFields": [],
                    "tags": [],
                },
            )
        if request.url.path == "/api/articles":
            return httpx.Response(200, json=[])
        if request.url.path == "/api/issues/LUM-111/comments":
            return httpx.Response(200, json={"id": "4-111", "text": "Comment"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    set_youtrack_client_override(
        YouTrackClient(
            base_url="https://youtrack.example.com",
            token="token-123",
            transport=httpx.MockTransport(handler),
        )
    )

    client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret-token"},
        json={
            "update_id": 1,
            "message": {
                "message_id": 10,
                "date": 1710000000,
                "chat": {"id": 7001, "type": "private"},
                "from": {"id": 44, "is_bot": False, "first_name": "Ana", "username": "ana"},
                "text": "/lummevia project=LUM issue=LUM-111\ncrear app para reservas medicas",
            },
        },
    )
    client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret-token"},
        json={
            "update_id": 2,
            "message": {
                "message_id": 11,
                "date": 1710000001,
                "chat": {"id": 7001, "type": "private"},
                "from": {"id": 44, "is_bot": False, "first_name": "Ana", "username": "ana"},
                "text": (
                    "/lummevia project=LUM issue=LUM-111\n"
                    "1. Sin chatbot libre ni autoaprobacion.\n"
                    "2. Lo usan recepcionistas y pacientes.\n"
                    "3. MVP: crear reserva, confirmar turno y ver agenda diaria.\n"
                    "4. Exito: validar una reserva end to end."
                ),
            },
        },
    )
    approval_response = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret-token"},
        json={
            "update_id": 3,
            "message": {
                "message_id": 12,
                "date": 1710000002,
                "chat": {"id": 7001, "type": "private"},
                "from": {"id": 44, "is_bot": False, "first_name": "Ana", "username": "ana"},
                "text": "/approve project=LUM issue=LUM-111",
            },
        },
    )

    handoff_id = approval_response.json()["metadata"]["handoff_id"]
    list_response = client.get("/projects/handoffs")
    get_response = client.get(f"/projects/handoffs/{handoff_id}")

    assert list_response.status_code == 200
    assert any(handoff["handoff_id"] == handoff_id for handoff in list_response.json())
    assert get_response.status_code == 200
    assert get_response.json()["handoff_id"] == handoff_id
    assert get_response.json()["metadata"]["workflow_run_id"].startswith("run-")
