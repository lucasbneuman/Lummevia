import pytest
from pydantic import ValidationError

from lummevia_integrations.youtrack import (
    YouTrackArtifactLink,
    YouTrackBugPayload,
    YouTrackClient,
    YouTrackCommentPayload,
    YouTrackIntegrationNotImplementedError,
    YouTrackIssueRef,
)


def test_youtrack_client_can_be_instantiated() -> None:
    client = YouTrackClient()

    assert isinstance(client, YouTrackClient)


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


@pytest.mark.parametrize(
    "call_name",
    [
        "get_issue",
        "add_comment",
        "create_bug",
        "link_artifact",
    ],
)
def test_youtrack_client_methods_raise_clear_placeholder_error(call_name: str) -> None:
    client = YouTrackClient()
    bug_payload = YouTrackBugPayload(
        project="lummevia-os",
        summary="Bug summary",
        description="Bug description",
        steps_to_reproduce=["Step 1"],
    )
    comment_payload = YouTrackCommentPayload(body="Diagnostic comment")
    artifact_link = YouTrackArtifactLink(
        artifact_type="BusinessBrief",
        artifact_id="brief-1",
        title="Business brief",
    )

    with pytest.raises(
        YouTrackIntegrationNotImplementedError,
        match="YouTrack integration is not implemented yet",
    ):
        if call_name == "get_issue":
            client.get_issue("LUM-101")
        elif call_name == "add_comment":
            client.add_comment("LUM-101", comment_payload)
        elif call_name == "create_bug":
            client.create_bug(bug_payload)
        else:
            client.link_artifact("LUM-101", artifact_link)
