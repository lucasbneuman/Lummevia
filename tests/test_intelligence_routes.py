from __future__ import annotations

from fastapi.testclient import TestClient

from lummevia_intelligence import DecisionRegistry
from main import app


client = TestClient(app)


def test_intelligence_endpoints_list_get_accept_reject_and_evaluate() -> None:
    runtime_response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-INT-301"},
    )
    assert runtime_response.status_code == 200

    decision_id = runtime_response.json()["metadata"]["decision_id"]

    list_response = client.get("/intelligence/decisions")
    assert list_response.status_code == 200
    assert any(decision["decision_id"] == decision_id for decision in list_response.json())

    get_response = client.get(f"/intelligence/decisions/{decision_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "PROPOSED"

    accept_response = client.post(f"/intelligence/decisions/{decision_id}/accept")
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "ACCEPTED"

    second_runtime_response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-INT-302"},
    )
    assert second_runtime_response.status_code == 200
    second_decision_id = second_runtime_response.json()["metadata"]["decision_id"]

    evaluate_response = client.post(
        "/intelligence/evaluate",
        json={
            "workflow_run_id": "run-eval-only",
            "missing_context": True,
        },
    )
    assert evaluate_response.status_code == 200
    assert evaluate_response.json()["decision_type"] == "REQUEST_MORE_CONTEXT"

    reject_response = client.post(f"/intelligence/decisions/{second_decision_id}/reject")
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "REJECTED"
    assert DecisionRegistry.default().get_decision(second_decision_id).status.value == "REJECTED"


def test_evaluate_endpoint_does_not_mutate_registry() -> None:
    before = len(DecisionRegistry.default().list_decisions())

    response = client.post(
        "/intelligence/evaluate",
        json={
            "workflow_run_id": "run-eval-stateless",
            "files_changed_count": 10,
            "real_code_touched": True,
        },
    )

    after = len(DecisionRegistry.default().list_decisions())

    assert response.status_code == 200
    assert response.json()["decision_type"] == "ESCALATE_REVIEW"
    assert before == after
