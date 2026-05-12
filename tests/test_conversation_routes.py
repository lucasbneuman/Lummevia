from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_conversation_endpoints_list_get_and_add_message() -> None:
    create_response = client.post(
        "/runtime/development/run",
        json={
            "project": "lummevia-os",
            "issue_id": "OS-401",
        },
    )
    assert create_response.status_code == 200
    thread_id = create_response.json()["metadata"]["thread_id"]

    list_response = client.get("/conversations")
    assert list_response.status_code == 200
    assert any(thread["thread_id"] == thread_id for thread in list_response.json())

    get_response = client.get(f"/conversations/{thread_id}")
    assert get_response.status_code == 200
    assert get_response.json()["thread_id"] == thread_id

    message_response = client.post(
        f"/conversations/{thread_id}/message",
        json={
            "role": "user",
            "author_type": "FOUNDER",
            "content": "Please tighten the scope before approval.",
            "metadata": {"channel": "api"},
        },
    )
    assert message_response.status_code == 200
    body = message_response.json()
    assert body["thread_id"] == thread_id
    assert body["messages"][-1]["content"] == "Please tighten the scope before approval."
    assert body["messages"][-1]["metadata"]["channel"] == "api"


def test_conversation_get_returns_404_for_missing_thread() -> None:
    response = client.get("/conversations/thread-missing")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Conversation thread 'thread-missing' not found.",
    }
