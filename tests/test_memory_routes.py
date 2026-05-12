from fastapi.testclient import TestClient

from lummevia_memory import (
    MemoryCategory,
    MemorySourceType,
    ProjectMemoryRegistry,
)
from main import app


client = TestClient(app)


def test_memory_endpoints_return_project_context_category_and_tag_views() -> None:
    registry = ProjectMemoryRegistry.default()
    registry.add_memory(
        project="lummevia-os",
        category=MemoryCategory.BUSINESS_DECISION,
        title="Founder decision",
        content="Focus the first iteration on PM memory flow.",
        source_type=MemorySourceType.CONVERSATION,
        source_id="thread-101",
        tags=["founder", "pm"],
    )
    registry.add_memory(
        project="lummevia-os",
        category=MemoryCategory.QA_ISSUE,
        title="QA issue",
        content="Failing scenario on review transitions.",
        source_type=MemorySourceType.REVIEW,
        source_id="review-101",
        tags=["qa", "review"],
    )

    project_response = client.get("/memory/projects/lummevia-os")
    assert project_response.status_code == 200
    project_body = project_response.json()
    assert project_body["project"] == "lummevia-os"
    assert project_body["project_memory_count"] == 2
    assert project_body["recent_decisions"][0]["title"] == "Founder decision"

    category_response = client.get(
        "/memory/projects/lummevia-os/category/BUSINESS_DECISION"
    )
    assert category_response.status_code == 200
    assert category_response.json()[0]["category"] == "BUSINESS_DECISION"

    tag_response = client.get("/memory/projects/lummevia-os/tags/qa")
    assert tag_response.status_code == 200
    assert tag_response.json()[0]["title"] == "QA issue"
