from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_runtime_fake_generates_change_set_metadata() -> None:
    response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-920"},
    )

    assert response.status_code == 200
    body = response.json()

    assert body["metadata"]["current_change_set_id"].startswith("change-set-")
    assert body["metadata"]["kilo_execution_by_step"]["dev_implementation"]["change_set_id"].startswith(
        "change-set-"
    )
    assert body["metadata"]["code_change_sets"]


def test_qa_references_change_set_and_validation_status() -> None:
    response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-921"},
    )

    assert response.status_code == 200
    body = response.json()

    qa_metadata = body["run"]["metadata"]["qa_validation"]
    assert qa_metadata["qa_checked_change_set_id"].startswith("change-set-")
    assert qa_metadata["validation_status"] == "PASSED"


def test_code_change_endpoints_list_get_and_discard() -> None:
    runtime_response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-922"},
    )
    assert runtime_response.status_code == 200
    change_set_id = runtime_response.json()["metadata"]["current_change_set_id"]
    run_id = runtime_response.json()["run"]["run_id"]

    list_response = client.get("/code-changes")
    assert list_response.status_code == 200
    assert any(item["change_set_id"] == change_set_id for item in list_response.json())

    get_response = client.get(f"/code-changes/{change_set_id}")
    assert get_response.status_code == 200
    assert get_response.json()["change_set_id"] == change_set_id

    discard_response = client.post(f"/code-changes/{change_set_id}/discard")
    assert discard_response.status_code == 200
    assert discard_response.json()["status"] == "DISCARDED"

    timeline_response = client.get(f"/timelines/{run_id}")
    assert timeline_response.status_code == 200
    assert any(
        event["event_type"] == "CODE_CHANGE_DISCARDED"
        for event in timeline_response.json()["events"]
    )
