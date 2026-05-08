from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from lummevia_core import AgentRole


class AgentBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class AgentRunRequest(AgentBaseSchema):
    input: str = Field(min_length=1)
    issue_id: str | None = None
    project: str | None = None
    environment: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentRunResult(AgentBaseSchema):
    agent_name: str = Field(min_length=1)
    role: AgentRole
    status: str = Field(min_length=1)
    output: str | None = None
    provider: str | None = None
    model: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
