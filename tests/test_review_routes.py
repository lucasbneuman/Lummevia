from __future__ import annotations

from fastapi.testclient import TestClient

from lummevia_reviews import HumanReviewRegistry, ReviewType
from main import app


client = TestClient(app)


def test_review_endpoints_list_get_and_approve() -> None:
    registry = HumanReviewRegistry.default()
    created = registry.create_review(
        review_type=ReviewType.TASK_PLAN,
        target_id="plan-001",
        target_type="TaskPlan",
        requested_by="po",
        notes="Bootstrap review for API coverage.",
    )
    review_id = created.review_id

    list_response = client.get("/reviews")
    assert list_response.status_code == 200
    assert any(review["review_id"] == review_id for review in list_response.json())

    get_response = client.get(f"/reviews/{review_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "PENDING"

    approve_response = client.post(
        f"/reviews/{review_id}/approve",
        json={"notes": "Approved through endpoint."},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["decision"] == "APPROVED"
    assert approve_response.json()["status"] == "COMPLETED"


def test_review_reject_endpoint_updates_decision() -> None:
    registry = HumanReviewRegistry.default()
    created = registry.create_review(
        review_type=ReviewType.QA_VALIDATION,
        target_id="validation-001",
        target_type="ValidationPackage",
        requested_by="qa",
        notes="Bootstrap reject case.",
    )
    review_id = created.review_id

    reject_response = client.post(
        f"/reviews/{review_id}/reject",
        json={"notes": "Needs rework."},
    )

    assert reject_response.status_code == 200
    assert reject_response.json()["decision"] == "REJECTED"
    assert reject_response.json()["status"] == "COMPLETED"
