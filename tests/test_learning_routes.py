from fastapi.testclient import TestClient

from lummevia_learning import LearningRegistry, RecommendationStatus
from lummevia_reviews import HumanReviewRegistry, ReviewStatus
from main import app


client = TestClient(app)


def test_learning_endpoints_list_and_analyze() -> None:
    run_response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-LR-1"},
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["run"]["run_id"]

    analyze_response = client.post(
        "/learning/analyze",
        json={"workflow_run_id": run_id, "context": {"qa_failure_count": 2}},
    )
    assert analyze_response.status_code == 200
    body = analyze_response.json()
    assert body["signals"]
    assert body["insights"]
    assert body["recommendations"]

    signals_response = client.get("/learning/signals")
    insights_response = client.get("/learning/insights")
    recommendations_response = client.get("/learning/recommendations")

    assert signals_response.status_code == 200
    assert insights_response.status_code == 200
    assert recommendations_response.status_code == 200
    assert any(signal["project"] == "lummevia-os" for signal in signals_response.json())
    assert any(insight["project"] == "lummevia-os" for insight in insights_response.json())
    assert any(
        recommendation["project"] == "lummevia-os"
        for recommendation in recommendations_response.json()
    )


def test_learning_recommendation_accept_and_reject_endpoints_update_status() -> None:
    run_response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-LR-2"},
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["run"]["run_id"]
    client.post(
        "/learning/analyze",
        json={"workflow_run_id": run_id, "context": {"qa_failure_count": 2}},
    )

    recommendation = LearningRegistry.default().list_recommendations(project="lummevia-os")[0]
    accept_response = client.post(
        f"/learning/recommendations/{recommendation.recommendation_id}/accept",
        json={"notes": "Approved for future manual rollout.", "assigned_to": "founder"},
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == RecommendationStatus.ACCEPTED.value

    review_id = accept_response.json()["metadata"]["review_id"]
    review = HumanReviewRegistry.default().get_review(review_id)
    assert review is not None
    assert review.status == ReviewStatus.COMPLETED

    rejected = next(
        item
        for item in LearningRegistry.default().list_recommendations(project="lummevia-os")
        if item.recommendation_id != recommendation.recommendation_id
    )
    reject_response = client.post(
        f"/learning/recommendations/{rejected.recommendation_id}/reject",
        json={"notes": "Not appropriate for now.", "assigned_to": "founder"},
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == RecommendationStatus.REJECTED.value
