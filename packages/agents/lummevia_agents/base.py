from __future__ import annotations

from typing import Any

from lummevia_core import AgentRole
from model_router import AgentRole as RouterAgentRole
from model_router import RoutingRequest, RoutingResolution, resolve_model

from lummevia_agents.execution import (
    ModelExecutionRequest,
    ModelExecutionResult,
    ModelExecutor,
)
from lummevia_agents.exceptions import AgentNotImplementedError
from lummevia_agents.schemas import AgentRunRequest


class BaseAgent:
    name: str
    role: AgentRole

    def __init__(
        self,
        name: str | None = None,
        *,
        model_executor: ModelExecutor | None = None,
    ) -> None:
        self.name = name or self.default_name
        self.model_executor = model_executor or ModelExecutor()

    @property
    def default_name(self) -> str:
        return f"{self.role.value.lower()}-agent"

    def resolve_model(
        self,
        project: str | None = None,
        environment: str | None = None,
    ) -> RoutingResolution:
        return resolve_model(
            RoutingRequest(
                role=RouterAgentRole[self.role.value],
                project=project,
                environment=environment,
            )
        )

    def execute_model(
        self,
        prompt: str,
        *,
        project: str | None = None,
        environment: str | None = None,
        system_prompt: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ModelExecutionResult:
        return self.model_executor.execute(
            ModelExecutionRequest(
                role=self.role,
                project=project,
                environment=environment,
                prompt=prompt,
                system_prompt=system_prompt,
                metadata=metadata or {},
            )
        )

    def run(self, input: AgentRunRequest) -> None:
        raise AgentNotImplementedError(
            "Agent runtime is not implemented yet. "
            f"Role '{self.role.value}' is still a placeholder."
        )
