from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import Field

from lummevia_core import AgentRole

from lummevia_agents.schemas import AgentBaseSchema


class PromptContext(AgentBaseSchema):
    project: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    role: AgentRole
    available_artifacts: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextBuilder:
    def build(
        self,
        *,
        project: str,
        issue_id: str,
        role: AgentRole,
        available_artifacts: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PromptContext:
        normalized_artifacts = {
            name: self._normalize_artifact(artifact)
            for name, artifact in (available_artifacts or {}).items()
        }
        return PromptContext(
            project=project,
            issue_id=issue_id,
            role=role,
            available_artifacts=normalized_artifacts,
            metadata=dict(metadata or {}),
        )

    def _normalize_artifact(self, artifact: Any) -> Any:
        if hasattr(artifact, "model_dump"):
            return artifact.model_dump(mode="json")
        if isinstance(artifact, datetime | date):
            return artifact.isoformat()
        if isinstance(artifact, dict):
            return {
                key: self._normalize_artifact(value)
                for key, value in artifact.items()
            }
        if isinstance(artifact, list):
            return [self._normalize_artifact(item) for item in artifact]
        return artifact
