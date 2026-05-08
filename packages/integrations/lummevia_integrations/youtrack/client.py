from __future__ import annotations

from lummevia_integrations.youtrack.exceptions import (
    YouTrackIntegrationNotImplementedError,
)
from lummevia_integrations.youtrack.schemas import (
    YouTrackArtifactLink,
    YouTrackBugPayload,
    YouTrackCommentPayload,
)


class YouTrackClient:
    def _not_implemented(self, operation: str) -> None:
        raise YouTrackIntegrationNotImplementedError(
            "YouTrack integration is not implemented yet. "
            f"Operation '{operation}' is still a placeholder."
        )

    def get_issue(self, issue_id: str) -> None:
        self._not_implemented("get_issue")

    def add_comment(self, issue_id: str, payload: YouTrackCommentPayload) -> None:
        self._not_implemented("add_comment")

    def create_bug(self, payload: YouTrackBugPayload) -> None:
        self._not_implemented("create_bug")

    def link_artifact(self, issue_id: str, artifact_link: YouTrackArtifactLink) -> None:
        self._not_implemented("link_artifact")
