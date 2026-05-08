from __future__ import annotations

from lummevia_integrations.github.exceptions import (
    GitHubIntegrationNotImplementedError,
)
from lummevia_integrations.github.schemas import (
    GitHubPullRequestPayload,
    GitHubRepoRef,
)


class GitHubClient:
    def _not_implemented(self, operation: str) -> None:
        raise GitHubIntegrationNotImplementedError(
            "GitHub integration is not implemented yet. "
            f"Operation '{operation}' is still a placeholder."
        )

    def get_pull_request(self, repo: GitHubRepoRef, pr_number: int) -> None:
        self._not_implemented("get_pull_request")

    def create_pull_request(self, payload: GitHubPullRequestPayload) -> None:
        self._not_implemented("create_pull_request")

    def add_comment(self, repo: GitHubRepoRef, pr_number: int, body: str) -> None:
        self._not_implemented("add_comment")

    def get_branch(self, repo: GitHubRepoRef, branch: str) -> None:
        self._not_implemented("get_branch")

    def get_commit(self, repo: GitHubRepoRef, sha: str) -> None:
        self._not_implemented("get_commit")
