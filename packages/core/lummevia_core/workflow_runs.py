from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import Field

from lummevia_core.enums import WorkflowRunStatus
from lummevia_core.validation import CoreArtifactModel


def _generate_run_id() -> str:
    return f"run-{uuid4()}"


class WorkflowRunEvent(CoreArtifactModel):
    event_id: str
    step_name: str
    status: WorkflowRunStatus
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowRun(CoreArtifactModel):
    run_id: str = Field(default_factory=_generate_run_id)
    workflow_name: str
    project: str
    issue_id: str
    status: WorkflowRunStatus
    current_step: str | None = None
    events: list[WorkflowRunEvent] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
