import pytest
from pydantic import ValidationError

from lummevia_integrations.github import (
    GitHubBranchRef,
    GitHubClient,
    GitHubCommitRef,
    GitHubIntegrationNotImplementedError,
    GitHubPullRequestPayload,
    GitHubPullRequestRef,
    GitHubRepoRef,
)


def test_github_client_can_be_instantiated() -> None:
    client = GitHubClient()

    assert isinstance(client, GitHubClient)


def test_github_repo_ref_accepts_valid_payload() -> None:
    repo = GitHubRepoRef(owner="lummevia", name="lummevia-os")

    assert repo.owner == "lummevia"
    assert repo.name == "lummevia-os"


def test_github_branch_ref_accepts_valid_payload() -> None:
    branch = GitHubBranchRef(
        repo=GitHubRepoRef(owner="lummevia", name="lummevia-os"),
        branch="feature/core-artifacts",
    )

    assert branch.branch == "feature/core-artifacts"


def test_github_commit_ref_accepts_valid_payload() -> None:
    commit = GitHubCommitRef(
        repo=GitHubRepoRef(owner="lummevia", name="lummevia-os"),
        sha="abc123def456",
    )

    assert commit.sha == "abc123def456"


def test_github_pull_request_ref_accepts_valid_payload() -> None:
    pr = GitHubPullRequestRef(
        repo=GitHubRepoRef(owner="lummevia", name="lummevia-os"),
        pr_number=42,
    )

    assert pr.pr_number == 42


def test_github_pull_request_payload_accepts_valid_payload() -> None:
    payload = GitHubPullRequestPayload(
        repo=GitHubRepoRef(owner="lummevia", name="lummevia-os"),
        title="Add core artifacts package",
        body="Implements shared artifacts and tests.",
        head="feature/core-artifacts",
        base="main",
        draft=True,
    )

    assert payload.title == "Add core artifacts package"
    assert payload.draft is True


def test_github_pull_request_payload_requires_title() -> None:
    with pytest.raises(ValidationError):
        GitHubPullRequestPayload(
            repo=GitHubRepoRef(owner="lummevia", name="lummevia-os"),
            title="",
            body="Body",
            head="feature/core-artifacts",
            base="main",
        )


@pytest.mark.parametrize(
    "call_name",
    [
        "get_pull_request",
        "create_pull_request",
        "add_comment",
        "get_branch",
        "get_commit",
    ],
)
def test_github_client_methods_raise_clear_placeholder_error(call_name: str) -> None:
    client = GitHubClient()
    repo = GitHubRepoRef(owner="lummevia", name="lummevia-os")
    payload = GitHubPullRequestPayload(
        repo=repo,
        title="Add model router diagnostics",
        body="Adds diagnostic endpoints for model routing.",
        head="feature/model-router-diagnostics",
        base="main",
    )

    with pytest.raises(
        GitHubIntegrationNotImplementedError,
        match="GitHub integration is not implemented yet",
    ):
        if call_name == "get_pull_request":
            client.get_pull_request(repo, 10)
        elif call_name == "create_pull_request":
            client.create_pull_request(payload)
        elif call_name == "add_comment":
            client.add_comment(repo, 10, "Looks good")
        elif call_name == "get_branch":
            client.get_branch(repo, "main")
        else:
            client.get_commit(repo, "abc123def456")
