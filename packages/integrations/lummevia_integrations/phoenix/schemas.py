from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PhoenixBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class PhoenixTraceRef(PhoenixBaseSchema):
    trace_id: str = Field(min_length=1)


class PhoenixTracePayload(PhoenixBaseSchema):
    run_id: str = Field(min_length=1)
    workflow: str = Field(min_length=1)
    project: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    agent_role: str = Field(min_length=1)
    agent_name: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    fallback_used: bool = False
    status: str = Field(min_length=1)
    latency_ms: int | None = Field(default=None, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PhoenixSpanPayload(PhoenixBaseSchema):
    trace_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    input: str | None = None
    output: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PhoenixEvaluationPayload(PhoenixBaseSchema):
    trace_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    score: float
    label: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
