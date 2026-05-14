from fastapi.testclient import TestClient

from app.core.youtrack import set_youtrack_client_override
from lummevia_integrations import YouTrackClient
from main import app


client = TestClient(app)


def test_youtrack_context_route_returns_agent_bundle() -> None:
    def handler(request):
        if request.url.path == "/api/issues/LUM-101":
            return _json_response(
                {
                    "id": "2-101",
                    "idReadable": "LUM-101",
                    "summary": "Telegram-first MVP",
                    "description": "Main issue",
                    "project": {"shortName": "LUM"},
                    "customFields": [{"name": "State", "value": {"name": "Open"}}],
                    "tags": [],
                }
            )
        if request.url.path == "/api/articles":
            return _json_response(
                [
                    {
                        "id": "10-1",
                        "idReadable": "LUM-A-1",
                        "summary": "PM workflow guide",
                        "content": "PM workflow guide",
                        "project": {"shortName": "LUM"},
                        "tags": [{"name": "pm"}],
                    }
                ]
            )
        if request.url.path == "/api/issues":
            return _json_response([])
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    set_youtrack_client_override(
        YouTrackClient(
            base_url="https://youtrack.example.com",
            token="token-123",
            transport=_transport(handler),
        )
    )

    response = client.get("/youtrack/context/PM", params={"project": "LUM", "issue_id": "LUM-101"})

    assert response.status_code == 200
    body = response.json()
    assert body["project"] == "LUM"
    assert body["role"] == "PM"
    assert body["issue"]["issue_id"] == "LUM-101"
    assert body["knowledge_documents"][0]["document_id"] == "10-1"


def test_youtrack_issue_routes_support_get_create_update_and_comment() -> None:
    def handler(request):
        if request.url.path == "/api/issues/LUM-101" and request.method == "GET":
            return _json_response(
                {
                    "id": "2-101",
                    "idReadable": "LUM-101",
                    "summary": "Main issue",
                    "description": "Description",
                    "project": {"shortName": "LUM"},
                    "customFields": [],
                    "tags": [],
                }
            )
        if request.url.path == "/api/issues" and request.method == "POST":
            return _json_response(
                {
                    "id": "2-102",
                    "idReadable": "LUM-102",
                    "summary": "Created issue",
                    "description": "Created description",
                    "project": {"shortName": "LUM"},
                    "customFields": [],
                    "tags": [],
                }
            )
        if request.url.path == "/api/issues/LUM-102" and request.method == "POST":
            return _json_response(
                {
                    "id": "2-102",
                    "idReadable": "LUM-102",
                    "summary": "Updated issue",
                    "description": "Created description",
                    "project": {"shortName": "LUM"},
                    "customFields": [{"name": "State", "value": {"name": "Approved"}}],
                    "tags": [],
                }
            )
        if request.url.path == "/api/issues/LUM-102/comments" and request.method == "POST":
            return _json_response({"id": "4-2", "text": "Comment body"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    set_youtrack_client_override(
        YouTrackClient(
            base_url="https://youtrack.example.com",
            token="token-123",
            transport=_transport(handler),
        )
    )

    get_response = client.get("/youtrack/issues/LUM-101")
    create_response = client.post(
        "/youtrack/issues",
        json={"project": "LUM", "summary": "Created issue", "description": "Created description"},
    )
    update_response = client.post(
        "/youtrack/issues/LUM-102",
        json={"summary": "Updated issue", "state": "Approved", "custom_fields": {}},
    )
    comment_response = client.post(
        "/youtrack/issues/LUM-102/comments",
        json={"body": "Comment body"},
    )

    assert get_response.status_code == 200
    assert get_response.json()["issue_id"] == "LUM-101"
    assert create_response.status_code == 200
    assert create_response.json()["issue_id"] == "LUM-102"
    assert update_response.status_code == 200
    assert update_response.json()["state"] == "Approved"
    assert comment_response.status_code == 200
    assert comment_response.json()["comment_id"] == "4-2"


def test_youtrack_article_routes_support_read_and_upsert() -> None:
    def handler(request):
        if request.url.path == "/api/articles" and request.method == "GET":
            return _json_response(
                [
                    {
                        "id": "10-1",
                        "idReadable": "LUM-A-1",
                        "summary": "PM guide",
                        "content": "PM guide content",
                        "project": {"shortName": "LUM"},
                        "tags": [{"name": "pm"}],
                    }
                ]
            )
        if request.url.path == "/api/articles/10-1" and request.method == "GET":
            return _json_response(
                {
                    "id": "10-1",
                    "idReadable": "LUM-A-1",
                    "summary": "PM guide",
                    "content": "PM guide content",
                    "project": {"shortName": "LUM"},
                    "tags": [{"name": "pm"}],
                }
            )
        if request.url.path == "/api/articles" and request.method == "POST":
            return _json_response(
                {
                    "id": "10-2",
                    "idReadable": "LUM-A-2",
                    "summary": "PO guide",
                    "content": "PO guide content",
                    "project": {"shortName": "LUM"},
                    "tags": [{"name": "po"}],
                }
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    set_youtrack_client_override(
        YouTrackClient(
            base_url="https://youtrack.example.com",
            token="token-123",
            transport=_transport(handler),
        )
    )

    list_response = client.get("/youtrack/articles", params={"project": "LUM"})
    get_response = client.get("/youtrack/articles/10-1")
    create_response = client.post(
        "/youtrack/articles",
        json={"project": "LUM", "title": "PO guide", "content": "PO guide content"},
    )

    assert list_response.status_code == 200
    assert list_response.json()["documents"][0]["document_id"] == "10-1"
    assert get_response.status_code == 200
    assert get_response.json()["document_id"] == "10-1"
    assert create_response.status_code == 200
    assert create_response.json()["document_id"] == "10-2"


def _transport(handler):
    import httpx

    return httpx.MockTransport(handler)


def _json_response(payload):
    import httpx

    return httpx.Response(200, json=payload)
