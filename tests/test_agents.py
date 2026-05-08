import pytest
from pydantic import ValidationError

from lummevia_core import AgentRole
from model_router import RoutingResolution

from lummevia_agents import (
    AgentNotImplementedError,
    AgentRunRequest,
    AgentRunResult,
    BaseAgent,
    DevAgent,
    PMAgent,
    POAgent,
    QAAgent,
    QCAgent,
)


def test_agent_run_request_accepts_valid_payload() -> None:
    request = AgentRunRequest(
        input="Convert founder intent into a business brief",
        issue_id="LUM-201",
        project="lummevia-os",
        environment="development",
        metadata={"source": "manual"},
    )

    assert request.input == "Convert founder intent into a business brief"
    assert request.project == "lummevia-os"


def test_agent_run_result_accepts_valid_payload() -> None:
    result = AgentRunResult(
        agent_name="pm-agent",
        role=AgentRole.PM,
        status="placeholder",
        output=None,
        provider="OPENROUTER",
        model="deepseek/deepseek-chat",
        metadata={"reason": "not implemented"},
    )

    assert result.role == AgentRole.PM
    assert result.status == "placeholder"


def test_agent_run_request_requires_input() -> None:
    with pytest.raises(ValidationError):
        AgentRunRequest(input="")


@pytest.mark.parametrize(
    ("agent_cls", "expected_role"),
    [
        (PMAgent, AgentRole.PM),
        (POAgent, AgentRole.PO),
        (DevAgent, AgentRole.DEV),
        (QAAgent, AgentRole.QA),
        (QCAgent, AgentRole.QC),
    ],
)
def test_agents_expose_expected_role(agent_cls: type[BaseAgent], expected_role: AgentRole) -> None:
    agent = agent_cls()

    assert isinstance(agent, BaseAgent)
    assert agent.role == expected_role


@pytest.mark.parametrize(
    "agent_cls",
    [PMAgent, POAgent, DevAgent, QAAgent, QCAgent],
)
def test_agents_can_resolve_model(agent_cls: type[BaseAgent]) -> None:
    agent = agent_cls()

    resolution = agent.resolve_model(project="lummevia-os", environment="development")

    assert isinstance(resolution, RoutingResolution)
    assert resolution.role.value == agent.role.value
    assert resolution.model


@pytest.mark.parametrize(
    "agent_cls",
    [PMAgent, POAgent, DevAgent, QAAgent, QCAgent],
)
def test_agents_run_raise_clear_placeholder_error(agent_cls: type[BaseAgent]) -> None:
    agent = agent_cls()
    request = AgentRunRequest(
        input="Placeholder execution",
        project="lummevia-os",
        environment="development",
    )

    with pytest.raises(
        AgentNotImplementedError,
        match="Agent runtime is not implemented yet",
    ):
        agent.run(request)
