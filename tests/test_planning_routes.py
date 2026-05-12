from __future__ import annotations

from fastapi.testclient import TestClient

from lummevia_planning import AdaptivePlanRegistry
from main import app


client = TestClient(app)


def test_planning_endpoints_list_get_approve_reject_and_evaluate() -> None:
    runtime_response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-PLAN-301"},
    )
    assert runtime_response.status_code == 200
    adaptive_plan_id = runtime_response.json()["metadata"]["adaptive_plan_id"]

    list_response = client.get("/planning/adaptive-plans")
    assert list_response.status_code == 200
    assert any(plan["adaptive_plan_id"] == adaptive_plan_id for plan in list_response.json())

    get_response = client.get(f"/planning/adaptive-plans/{adaptive_plan_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "PROPOSED"

    approve_response = client.post(f"/planning/adaptive-plans/{adaptive_plan_id}/approve")
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "APPROVED"

    second_runtime_response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-PLAN-302"},
    )
    assert second_runtime_response.status_code == 200
    second_plan_id = second_runtime_response.json()["metadata"]["adaptive_plan_id"]

    reject_response = client.post(f"/planning/adaptive-plans/{second_plan_id}/reject")
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "REJECTED"

    evaluate_response = client.post(
        "/planning/evaluate",
        json={
            "workflow_run_id": "run-plan-evaluate",
            "project": "lummevia-os",
            "issue_id": "OS-PLAN-EVAL",
            "source_task_id": "OS-PLAN-EVAL-T1",
            "trigger_reason": "missing_context",
            "missing_context": True,
        },
    )
    assert evaluate_response.status_code == 200
    assert any(
        mutation["mutation_type"] == "REGENERATE_PROMPT"
        for mutation in evaluate_response.json()["mutations"]
    )


def test_planning_evaluate_does_not_mutate_registry() -> None:
    before = len(AdaptivePlanRegistry.default().list_plans())

    response = client.post(
        "/planning/evaluate",
        json={
            "workflow_run_id": "run-plan-stateless",
            "project": "lummevia-os",
            "issue_id": "OS-PLAN-STATELESS",
            "source_task_id": "OS-PLAN-STATELESS-T1",
            "trigger_reason": "large_diff",
            "files_changed_count": 10,
        },
    )
    after = len(AdaptivePlanRegistry.default().list_plans())

    assert response.status_code == 200
    assert any(
        mutation["mutation_type"] == "SPLIT_TASK"
        for mutation in response.json()["mutations"]
    )
    assert before == after


def test_approved_and_rejected_plans_sync_timeline() -> None:
    runtime_response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-PLAN-303"},
    )
    assert runtime_response.status_code == 200
    run_id = runtime_response.json()["run"]["run_id"]
    adaptive_plan_id = runtime_response.json()["metadata"]["adaptive_plan_id"]

    approve_response = client.post(f"/planning/adaptive-plans/{adaptive_plan_id}/approve")
    assert approve_response.status_code == 200

    timeline_response = client.get(f"/timelines/{run_id}")
    assert timeline_response.status_code == 200
    assert any(
        event["event_type"] == "GRAPH_MUTATION_APPROVED"
        for event in timeline_response.json()["events"]
    )
