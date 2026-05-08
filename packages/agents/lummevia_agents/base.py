from __future__ import annotations

from lummevia_core import AgentRole
from model_router import AgentRole as RouterAgentRole
from model_router import RoutingRequest, RoutingResolution, resolve_model

from lummevia_agents.exceptions import AgentNotImplementedError
from lummevia_agents.schemas import AgentRunRequest


class BaseAgent:
    name: str
    role: AgentRole

    def __init__(self, name: str | None = None) -> None:
        self.name = name or self.default_name

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

    def run(self, input: AgentRunRequest) -> None:
        raise AgentNotImplementedError(
            "Agent runtime is not implemented yet. "
            f"Role '{self.role.value}' is still a placeholder."
        )
