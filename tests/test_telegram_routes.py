import httpx
from fastapi.testclient import TestClient

from app.core.youtrack import set_youtrack_client_override
from app.api.routes import runtime as runtime_routes
from lummevia_conversations import ConversationRegistry, ConversationPhase
from lummevia_core import ApprovedProjectHandoffRegistry
from lummevia_integrations import YouTrackClient
from lummevia_reviews import HumanReviewRegistry
from main import app


client = TestClient(app)


def test_telegram_webhook_creates_issue_and_pm_questions_from_founder_intent(monkeypatch) -> None:
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

    comments: list[str] = []

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
        if request.url.path == "/api/issues/LUM-501":
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
        if request.url.path == "/api/articles":
            return httpx.Response(200, json=[])
        if request.url.path == "/api/issues/LUM-501/comments":
            comments.append(request.content.decode())
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
                "text": "/lummevia project=LUM\ncrear app para reservas medicas",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "pm_questions"
    assert body["project"] == "LUM"
    assert body["issue_id"] == "LUM-501"
    assert body["conversation_phase"] == "PM_QUESTIONS"
    assert body["pending_questions_count"] == 3
    thread = ConversationRegistry.default().get_thread(body["thread_id"])
    assert thread.issue_id == "LUM-501"
    assert thread.founder_pm_state is not None
    assert thread.founder_pm_state.phase == ConversationPhase.PM_QUESTIONS
    assert thread.messages[0].metadata["source"] == "telegram"
    assert any("Founder response received from Telegram" in payload for payload in comments)
    assert any("PM needs clarification before drafting" in payload for payload in comments)


def test_telegram_webhook_builds_draft_and_publishes_to_youtrack(monkeypatch) -> None:
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

    comments: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/issues/LUM-777":
            return httpx.Response(
                200,
                json={
                    "id": "2-777",
                    "idReadable": "LUM-777",
                    "summary": "Medical booking app",
                    "description": "Main issue",
                    "project": {"shortName": "LUM"},
                    "customFields": [],
                    "tags": [],
                },
            )
        if request.url.path == "/api/articles":
            return httpx.Response(200, json=[])
        if request.url.path == "/api/issues/LUM-777/comments":
            comments.append(request.content.decode())
            return httpx.Response(200, json={"id": "4-777", "text": "Comment"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    set_youtrack_client_override(
        YouTrackClient(
            base_url="https://youtrack.example.com",
            token="token-123",
            transport=httpx.MockTransport(handler),
        )
    )

    first_response = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret-token"},
        json={
            "update_id": 2,
            "message": {
                "message_id": 11,
                "date": 1710000001,
                "chat": {"id": 7001, "type": "private"},
                "from": {"id": 44, "is_bot": False, "first_name": "Ana", "username": "ana"},
                "text": "/lummevia project=LUM issue=LUM-777\ncrear app para reservas medicas",
            },
        },
    )
    assert first_response.status_code == 200
    thread_id = first_response.json()["thread_id"]

    second_response = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret-token"},
        json={
            "update_id": 3,
            "message": {
                "message_id": 12,
                "date": 1710000002,
                "chat": {"id": 7001, "type": "private"},
                "from": {"id": 44, "is_bot": False, "first_name": "Ana", "username": "ana"},
                "text": (
                    "/lummevia project=LUM issue=LUM-777\n"
                    "1. Sin chatbot libre ni autoaprobacion.\n"
                    "2. Lo usan recepcionistas y pacientes.\n"
                    "3. MVP: crear reserva, confirmar turno y ver agenda diaria.\n"
                    "4. Exito: validar una reserva end to end."
                ),
            },
        },
    )

    assert second_response.status_code == 200
    body = second_response.json()
    assert body["action"] == "pending_approval"
    assert body["thread_id"] == thread_id
    assert body["conversation_phase"] == "PENDING_APPROVAL"
    assert body["brief_version"] == 1
    assert body["pending_questions_count"] == 0
    thread = ConversationRegistry.default().get_thread(thread_id)
    assert thread.founder_pm_state is not None
    assert thread.founder_pm_state.phase == ConversationPhase.PENDING_APPROVAL
    assert thread.founder_pm_state.metadata["brief_draft"]["brief_version"] == 1
    assert any("BusinessBriefDraft" in payload for payload in comments)


def test_telegram_webhook_requires_explicit_approval_and_creates_review(monkeypatch) -> None:
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

    comments: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/issues/LUM-888":
            return httpx.Response(
                200,
                json={
                    "id": "2-888",
                    "idReadable": "LUM-888",
                    "summary": "Medical booking app",
                    "description": "Main issue",
                    "project": {"shortName": "LUM"},
                    "customFields": [],
                    "tags": [],
                },
            )
        if request.url.path == "/api/articles":
            return httpx.Response(200, json=[])
        if request.url.path == "/api/issues/LUM-888/comments":
            comments.append(request.content.decode())
            return httpx.Response(200, json={"id": "4-888", "text": "Comment"})
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
            "update_id": 4,
            "message": {
                "message_id": 13,
                "date": 1710000003,
                "chat": {"id": 7001, "type": "private"},
                "from": {"id": 44, "is_bot": False, "first_name": "Ana", "username": "ana"},
                "text": "/lummevia project=LUM issue=LUM-888\ncrear app para reservas medicas",
            },
        },
    )
    client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret-token"},
        json={
            "update_id": 5,
            "message": {
                "message_id": 14,
                "date": 1710000004,
                "chat": {"id": 7001, "type": "private"},
                "from": {"id": 44, "is_bot": False, "first_name": "Ana", "username": "ana"},
                "text": (
                    "/lummevia project=LUM issue=LUM-888\n"
                    "1. Sin chatbot libre ni autoaprobacion.\n"
                    "2. Lo usan recepcionistas y pacientes.\n"
                    "3. MVP: crear reserva, confirmar turno y ver agenda diaria.\n"
                    "4. Exito: validar una reserva end to end."
                ),
            },
        },
    )

    response = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret-token"},
        json={
            "update_id": 6,
            "message": {
                "message_id": 15,
                "date": 1710000005,
                "chat": {"id": 7001, "type": "private"},
                "from": {"id": 44, "is_bot": False, "first_name": "Ana", "username": "ana"},
                "text": "/approve project=LUM issue=LUM-888",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "approved"
    assert body["approved"] is True
    assert body["conversation_phase"] == "APPROVED"
    assert body["review_id"].startswith("review-")
    assert body["metadata"]["handoff_id"].startswith("handoff-")
    assert body["metadata"]["workflow_run_id"].startswith("run-")
    thread = ConversationRegistry.default().get_thread(body["thread_id"])
    assert thread.status.value == "APPROVED"
    assert thread.founder_pm_state is not None
    assert thread.founder_pm_state.phase == ConversationPhase.APPROVED
    handoff = ApprovedProjectHandoffRegistry.default().get_handoff(body["metadata"]["handoff_id"])
    assert handoff is not None
    assert handoff.metadata["workflow_run_id"] == body["metadata"]["workflow_run_id"]
    runtime_state = runtime_routes.runtime_service.get_run(body["metadata"]["workflow_run_id"])
    assert runtime_state.metadata["handoff_id"] == handoff.handoff_id
    review = HumanReviewRegistry.default().get_review(body["review_id"])
    assert review is not None
    assert review.decision.value == "APPROVED"
    assert any("Founder approved the Business Brief from Telegram" in payload for payload in comments)


def test_telegram_conversation_endpoints_list_and_get_threads(monkeypatch) -> None:
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
        if request.url.path == "/api/issues/LUM-999":
            return httpx.Response(
                200,
                json={
                    "id": "2-999",
                    "idReadable": "LUM-999",
                    "summary": "Medical booking app",
                    "description": "Main issue",
                    "project": {"shortName": "LUM"},
                    "customFields": [],
                    "tags": [],
                },
            )
        if request.url.path == "/api/articles":
            return httpx.Response(200, json=[])
        if request.url.path == "/api/issues/LUM-999/comments":
            return httpx.Response(200, json={"id": "4-999", "text": "Comment"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    set_youtrack_client_override(
        YouTrackClient(
            base_url="https://youtrack.example.com",
            token="token-123",
            transport=httpx.MockTransport(handler),
        )
    )

    webhook_response = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret-token"},
        json={
            "update_id": 7,
            "message": {
                "message_id": 16,
                "date": 1710000006,
                "chat": {"id": 7001, "type": "private"},
                "from": {"id": 44, "is_bot": False, "first_name": "Ana", "username": "ana"},
                "text": "/lummevia project=LUM issue=LUM-999\ncrear app para reservas medicas",
            },
        },
    )
    thread_id = webhook_response.json()["thread_id"]

    list_response = client.get("/telegram/conversations")
    get_response = client.get(f"/telegram/conversations/{thread_id}")

    assert list_response.status_code == 200
    assert any(thread["thread_id"] == thread_id for thread in list_response.json())
    assert get_response.status_code == 200
    assert get_response.json()["thread_id"] == thread_id


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
            "update_id": 8,
            "message": {
                "message_id": 17,
                "date": 1710000007,
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
        json={"update_id": 9},
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
        "conversation_phase": None,
        "brief_version": 0,
        "approved": False,
        "pending_questions": [],
        "pending_questions_count": 0,
        "review_id": None,
        "metadata": {
            "ignored_reason": "missing_message_text",
            "telegram_update_id": 9,
        },
    }
