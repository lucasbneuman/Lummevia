import httpx
import pytest
from pydantic import ValidationError

from lummevia_integrations.youtrack import (
    AgentContextBundle,
    YouTrackArtifactLink,
    YouTrackBugPayload,
    YouTrackClient,
    YouTrackCommentPayload,
    YouTrackConfigurationError,
    YouTrackIssueCreatePayload,
    YouTrackIssueRef,
    YouTrackIssueUpdatePayload,
    YouTrackKnowledgeDocumentUpsertPayload,
)


def _build_transport(handler):
    return httpx.MockTransport(handler)


def test_youtrack_client_can_be_instantiated_without_configuration() -> None:
    client = YouTrackClient()

    assert isinstance(client, YouTrackClient)
    assert client.is_configured is False


def test_youtrack_issue_ref_accepts_valid_payload() -> None:
    issue_ref = YouTrackIssueRef(issue_id="LUM-101", project="lummevia-os")

    assert issue_ref.issue_id == "LUM-101"
    assert issue_ref.project == "lummevia-os"


def test_youtrack_comment_payload_accepts_valid_payload() -> None:
    payload = YouTrackCommentPayload(body="Artifact linked for QA review")

    assert payload.body == "Artifact linked for QA review"


def test_youtrack_artifact_link_accepts_valid_payload() -> None:
    artifact_link = YouTrackArtifactLink(
        artifact_type="ValidationPackage",
        artifact_id="qa-validation-lum-101",
        title="QA validation package",
        url="https://example.test/artifacts/qa-validation-lum-101",
    )

    assert artifact_link.artifact_type == "ValidationPackage"
    assert str(artifact_link.url) == "https://example.test/artifacts/qa-validation-lum-101"


def test_youtrack_bug_payload_accepts_valid_payload() -> None:
    payload = YouTrackBugPayload(
        project="lummevia-os",
        summary="Validation fails on empty acceptance criteria",
        description="QA found that validation accepts an empty criteria list.",
        related_issue_id="LUM-102",
        steps_to_reproduce=["Open validation flow", "Submit empty criteria list"],
        expected_behavior="Validation should reject empty criteria",
        actual_behavior="Validation succeeds unexpectedly",
    )

    assert payload.project == "lummevia-os"
    assert payload.related_issue_id == "LUM-102"


def test_youtrack_bug_payload_requires_summary() -> None:
    with pytest.raises(ValidationError):
        YouTrackBugPayload(
            project="lummevia-os",
            summary="",
            description="Description",
            steps_to_reproduce=[],
        )


def test_youtrack_client_requires_configuration_before_requests() -> None:
    client = YouTrackClient()

    with pytest.raises(
        YouTrackConfigurationError,
        match="YOUTRACK_BASE_URL and YOUTRACK_TOKEN",
    ):
        client.get_issue("LUM-101")


def test_youtrack_client_reads_issue_and_searches_related_context() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/issues/LUM-101":
            return httpx.Response(
                200,
                json={
                    "id": "2-101",
                    "idReadable": "LUM-101",
                    "summary": "MVP without front",
                    "description": "Use Telegram and YouTrack as the control plane.",
                    "project": {"shortName": "LUM"},
                    "customFields": [
                        {"name": "State", "value": {"name": "Open"}},
                    ],
                    "tags": [{"name": "telegram"}],
                },
            )
        if request.url.path == "/api/issues":
            assert request.url.params["query"].startswith("project: LUM")
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "2-202",
                        "idReadable": "LUM-202",
                        "summary": "Related PM workflow task",
                        "description": "Context issue for PM.",
                        "project": {"shortName": "LUM"},
                        "customFields": [],
                        "tags": [],
                    }
                ],
            )
        if request.url.path == "/api/articles":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "10-1",
                        "idReadable": "LUM-A-1",
                        "summary": "PM workflow guide",
                        "content": "PM workflow and approval gate.",
                        "project": {"shortName": "LUM"},
                        "tags": [{"name": "pm"}],
                    },
                    {
                        "id": "10-2",
                        "idReadable": "LUM-A-2",
                        "summary": "PO task package guide",
                        "content": "Task package rules for the PO.",
                        "project": {"shortName": "LUM"},
                        "tags": [{"name": "po"}],
                    },
                ],
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = YouTrackClient(
        base_url="https://youtrack.example.com",
        token="token-123",
        transport=_build_transport(handler),
    )

    issue = client.get_issue("LUM-101")
    context = client.get_agent_context(
        project="LUM",
        role="PM",
        issue_id="LUM-101",
        issue_query="tag: {pm}",
    )

    assert issue.issue_id == "LUM-101"
    assert issue.project == "LUM"
    assert issue.state == "Open"
    assert issue.tags == ["telegram"]
    assert isinstance(context, AgentContextBundle)
    assert context.issue is not None
    assert context.issue.issue_id == "LUM-101"
    assert context.related_issues[0].issue_id == "LUM-202"
    assert context.knowledge_documents[0].document_id == "10-1"
    assert context.sources[0].source_id == "LUM-101"


def test_youtrack_client_can_create_update_and_comment_on_issues() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/youtrack/api/issues" and request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "id": "2-303",
                    "idReadable": "LUM-303",
                    "summary": "Telegram founder intent",
                    "description": "Founder intent body",
                    "project": {"shortName": "LUM"},
                    "customFields": [],
                    "tags": [],
                },
            )
        if request.url.path == "/youtrack/api/issues/LUM-303" and request.method == "POST":
            payload = request.content.decode("utf-8")
            assert "approved" in payload.lower()
            return httpx.Response(
                200,
                json={
                    "id": "2-303",
                    "idReadable": "LUM-303",
                    "summary": "Updated summary",
                    "description": "Founder intent body",
                    "project": {"shortName": "LUM"},
                    "customFields": [{"name": "State", "value": {"name": "Approved"}}],
                    "tags": [],
                },
            )
        if request.url.path == "/youtrack/api/issues/LUM-303/comments" and request.method == "POST":
            return httpx.Response(200, json={"id": "4-88", "text": "Tracked from Lummevia"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = YouTrackClient(
        base_url="https://youtrack.example.com/youtrack",
        token="token-123",
        transport=_build_transport(handler),
    )

    created = client.create_issue(
        YouTrackIssueCreatePayload(
            project="LUM",
            summary="Telegram founder intent",
            description="Founder intent body",
        )
    )
    updated = client.update_issue(
        "LUM-303",
        YouTrackIssueUpdatePayload(state="Approved", summary="Updated summary"),
    )
    comment = client.add_comment("LUM-303", YouTrackCommentPayload(body="Tracked from Lummevia"))

    assert created.issue_id == "LUM-303"
    assert str(created.url) == "https://youtrack.example.com/youtrack/issue/LUM-303"
    assert updated.state == "Approved"
    assert comment.comment_id == "4-88"
    assert comment.issue_id == "LUM-303"


def test_youtrack_client_can_create_bug_and_link_artifact() -> None:
    requests_seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(f"{request.method} {request.url.path}")
        if request.url.path == "/api/issues":
            return httpx.Response(
                200,
                json={
                    "id": "2-404",
                    "idReadable": "LUM-404",
                    "summary": "Validation fails",
                    "description": "Bug body",
                    "project": {"shortName": "LUM"},
                    "customFields": [],
                    "tags": [],
                },
            )
        if request.url.path == "/api/issues/LUM-404/comments":
            return httpx.Response(
                200,
                json={"id": "4-99", "text": "Artifact link comment"},
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = YouTrackClient(
        base_url="https://youtrack.example.com",
        token="token-123",
        transport=_build_transport(handler),
    )

    bug = client.create_bug(
        YouTrackBugPayload(
            project="LUM",
            summary="Validation fails",
            description="Bug body",
            steps_to_reproduce=["Open", "Submit"],
        )
    )
    comment = client.link_artifact(
        "LUM-404",
        YouTrackArtifactLink(
            artifact_type="ValidationPackage",
            artifact_id="validation-1",
            title="Validation package",
            url="https://example.test/validation-1",
        ),
    )

    assert bug.issue_id == "LUM-404"
    assert comment.comment_id == "4-99"
    assert requests_seen == ["POST /api/issues", "POST /api/issues/LUM-404/comments"]


def test_youtrack_client_can_read_and_upsert_knowledge_documents() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/articles" and request.method == "GET":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "10-9",
                        "idReadable": "LUM-A-9",
                        "summary": "PO handbook",
                        "content": "PO handbook content",
                        "project": {"shortName": "LUM"},
                        "tags": [{"name": "po"}],
                    }
                ],
            )
        if request.url.path == "/api/articles/10-9" and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "id": "10-9",
                    "idReadable": "LUM-A-9",
                    "summary": "PO handbook",
                    "content": "PO handbook content",
                    "project": {"shortName": "LUM"},
                    "tags": [{"name": "po"}],
                },
            )
        if request.url.path == "/api/articles" and request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "id": "10-10",
                    "idReadable": "LUM-A-10",
                    "summary": "PM handbook",
                    "content": "PM handbook content",
                    "project": {"shortName": "LUM"},
                    "tags": [{"name": "pm"}],
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = YouTrackClient(
        base_url="https://youtrack.example.com",
        token="token-123",
        transport=_build_transport(handler),
    )

    documents = client.list_knowledge_documents(project="LUM")
    document = client.get_knowledge_document("10-9")
    created = client.upsert_knowledge_document(
        YouTrackKnowledgeDocumentUpsertPayload(
            project="LUM",
            title="PM handbook",
            content="PM handbook content",
        )
    )

    assert documents[0].document_id == "10-9"
    assert document.title == "PO handbook"
    assert created.document_id == "10-10"
