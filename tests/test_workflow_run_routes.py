from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_workflow_runs_mock_returns_created_status() -> None:
    response = client.post(
        "/workflow-runs/mock",
        json={
            "workflow_name": "development",
            "project": "lummevia-os",
            "issue_id": "OS-1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_name"] == "development"
    assert body["project"] == "lummevia-os"
    assert body["issue_id"] == "OS-1"
    assert body["status"] == "CREATED"
    assert body["events"] == []
    assert body["metadata"] == {"diagnostic": True, "mock": True}
    assert body["run_id"]


def test_workflow_runs_mock_does_not_persist_state_between_calls() -> None:
    payload = {
        "workflow_name": "development",
        "project": "lummevia-os",
        "issue_id": "OS-1",
    }

    first_response = client.post("/workflow-runs/mock", json=payload)
    second_response = client.post("/workflow-runs/mock", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_body = first_response.json()
    second_body = second_response.json()

    assert first_body["run_id"] != second_body["run_id"]
    assert first_body["events"] == []
    assert second_body["events"] == []
