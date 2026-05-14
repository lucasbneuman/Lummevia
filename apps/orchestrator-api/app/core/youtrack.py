from __future__ import annotations

from typing import Any

from lummevia_core import AgentRole
from lummevia_integrations import (
    AgentContextBundle,
    YouTrackArtifactLink,
    YouTrackClient,
    YouTrackCommentPayload,
    YouTrackConfigurationError,
)

from app.core.config import settings

_client_override: YouTrackClient | None = None


def set_youtrack_client_override(client: YouTrackClient | None) -> None:
    global _client_override
    _client_override = client


def get_youtrack_client() -> YouTrackClient:
    if _client_override is not None:
        return _client_override
    return YouTrackClient(
        base_url=settings.youtrack.base_url,
        token=settings.youtrack.token,
    )


def load_agent_context_bundle(
    *,
    project: str,
    role: AgentRole | str,
    issue_id: str | None = None,
    issue_query: str | None = None,
) -> AgentContextBundle | None:
    client = get_youtrack_client()
    if not client.is_configured:
        return None

    role_value = role.value if isinstance(role, AgentRole) else role
    return client.get_agent_context(
        project=project,
        role=role_value,
        issue_id=issue_id,
        issue_query=issue_query,
    )


def sync_issue_comment(issue_id: str, body: str) -> None:
    client = get_youtrack_client()
    if not client.is_configured:
        return
    client.add_comment(issue_id, YouTrackCommentPayload(body=body))


def sync_artifact_link(
    *,
    issue_id: str,
    artifact_type: str,
    artifact_id: str,
    title: str,
    url: str | None = None,
) -> None:
    client = get_youtrack_client()
    if not client.is_configured:
        return
    client.link_artifact(
        issue_id,
        YouTrackArtifactLink(
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            title=title,
            url=url,
        ),
    )


def ensure_youtrack_available() -> YouTrackClient:
    client = get_youtrack_client()
    if client.is_configured:
        return client
    raise YouTrackConfigurationError(
        "YouTrack integration requires YOUTRACK_BASE_URL and YOUTRACK_TOKEN."
    )


def summarize_artifact_for_youtrack(
    *,
    artifact_type: str,
    payload: dict[str, Any],
) -> str:
    lines = [f"[{artifact_type}]"]
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, list):
            if not value:
                continue
            lines.append(f"{key}:")
            lines.extend(f"- {item}" for item in value[:8])
            if len(value) > 8:
                lines.append(f"- ... (+{len(value) - 8} more)")
            continue
        if isinstance(value, dict):
            lines.append(f"{key}: {value}")
            continue
        lines.append(f"{key}: {value}")
    return "\n".join(lines)
