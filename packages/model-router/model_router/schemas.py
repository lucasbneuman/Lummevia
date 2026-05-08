from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class AgentRole(str, Enum):
    PM = "PM"
    PO = "PO"
    DEV = "DEV"
    QA = "QA"
    QC = "QC"


class Provider(str, Enum):
    OPENAI = "OPENAI"
    OPENROUTER = "OPENROUTER"
    ANTHROPIC = "ANTHROPIC"
    LOCAL = "LOCAL"


class ModelConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: Provider
    model: str
    temperature: float = 0.2
    max_tokens: int = 2048


class RoutingRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: AgentRole
    project: str | None = None
    environment: str | None = None


class RoutingResolution(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: AgentRole
    project: str | None = None
    environment: str | None = None
    provider: Provider
    model: str
    temperature: float
    max_tokens: int
    source: Literal[
        "default",
        "environment",
        "project",
        "project_environment",
        "env_override",
    ]
