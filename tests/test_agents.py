import pytest
from pydantic import ValidationError

from lummevia_core import (
    AgentRole,
    BusinessBrief,
    ExecutionPackage,
    ImplementationPackage,
    QualityApproval,
    ValidationPackage,
    ValidationStatus,
)
from model_router import RoutingResolution

from lummevia_agents import (
    AgentNotImplementedError,
    AgentRunRequest,
    AgentRunResult,
    BaseAgent,
    DevAgent,
    FakeModelProvider,
    ModelExecutor,
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


@pytest.mark.parametrize(
    ("agent_cls", "target_artifact", "artifact_cls"),
    [
        (PMAgent, "BusinessBrief", BusinessBrief),
        (POAgent, "ExecutionPackage", ExecutionPackage),
        (DevAgent, "ImplementationPackage", ImplementationPackage),
        (QCAgent, "QualityApproval", QualityApproval),
    ],
)
def test_agents_can_produce_artifacts_via_prompt_pipeline(
    agent_cls: type[BaseAgent],
    target_artifact: str,
    artifact_cls: type[object],
) -> None:
    agent = agent_cls(
        model_executor=ModelExecutor(provider=FakeModelProvider()),
    )

    artifact = agent.produce_artifact(
        project="lummevia-os",
        issue_id="LUM-501",
        target_artifact=target_artifact,
        available_artifacts={
            "pull_request": {"pr_number": 1010, "status": "OPEN"},
        },
        metadata={"loop_count": 1},
    )

    assert isinstance(artifact, artifact_cls)
    assert artifact.issue_id == "LUM-501"


def test_qa_agent_produces_failed_validation_on_first_loop() -> None:
    agent = QAAgent(model_executor=ModelExecutor(provider=FakeModelProvider()))

    artifact = agent.produce_artifact(
        project="lummevia-os",
        issue_id="LUM-502",
        target_artifact="ValidationPackage",
        available_artifacts={
            "implementation_package": {
                "branch": "runtime/lum-502",
            }
        },
        metadata={"loop_count": 0},
    )

    assert isinstance(artifact, ValidationPackage)
    assert artifact.status == ValidationStatus.FAILED
    assert artifact.bugs_found == ["BUG-DEV-QA-LOOP"]


def test_qa_agent_produces_passed_validation_after_rework() -> None:
    agent = QAAgent(model_executor=ModelExecutor(provider=FakeModelProvider()))

    artifact = agent.produce_artifact(
        project="lummevia-os",
        issue_id="LUM-503",
        target_artifact="ValidationPackage",
        available_artifacts={
            "implementation_package": {
                "branch": "runtime/lum-503",
            }
        },
        metadata={"loop_count": 1},
    )

    assert isinstance(artifact, ValidationPackage)
    assert artifact.status == ValidationStatus.PASSED
    assert artifact.bugs_found == []
