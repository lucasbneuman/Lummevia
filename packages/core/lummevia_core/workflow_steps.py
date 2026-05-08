from __future__ import annotations

from pydantic import Field

from lummevia_core.enums import AgentRole
from lummevia_core.validation import CoreArtifactModel


class WorkflowStep(CoreArtifactModel):
    name: str
    responsible_role: AgentRole
    consumes: list[str] = Field(default_factory=list)
    produces: list[str] = Field(default_factory=list)
    description: str
