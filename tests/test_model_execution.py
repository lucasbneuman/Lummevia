import pytest

from lummevia_core import AgentRole

from lummevia_agents import (
    AgentNotImplementedError,
    AgentRunRequest,
    DevAgent,
    FakeModelProvider,
    ModelExecutionError,
    ModelExecutionRequest,
    ModelExecutor,
    PMAgent,
)


def test_fake_model_provider_returns_deterministic_output() -> None:
    provider = FakeModelProvider()
    executor = ModelExecutor(provider=provider)
    request = ModelExecutionRequest(
        role=AgentRole.PM,
        project="lummevia-os",
        environment="development",
        prompt="Summarize the brief",
        system_prompt="You are a PM",
        metadata={"trace_id": "trace-001"},
    )

    first = executor.execute(request)
    second = executor.execute(request)

    assert first.output == second.output
    assert first.raw_output == second.raw_output
    assert first.provider == "OPENROUTER"
    assert first.model == "deepseek/deepseek-chat"


def test_model_executor_resolves_pm_model() -> None:
    executor = ModelExecutor()

    result = executor.execute(
        ModelExecutionRequest(
            role=AgentRole.PM,
            project="lummevia-os",
            environment="production",
            prompt="Draft the business brief",
            system_prompt="You are a PM",
            metadata={},
        )
    )

    assert result.provider == "OPENROUTER"
    assert result.model == "deepseek/deepseek-chat-pro"
    assert result.metadata["role"] == "PM"


def test_model_executor_resolves_dev_model() -> None:
    executor = ModelExecutor()

    result = executor.execute(
        ModelExecutionRequest(
            role=AgentRole.DEV,
            project="lummevia-os",
            environment="development",
            prompt="Implement the task",
            system_prompt="You are a DEV",
            metadata={},
        )
    )

    assert result.provider == "OPENROUTER"
    assert result.model == "deepseek/deepseek-chat-lite"
    assert result.metadata["model"] == "deepseek/deepseek-chat-lite"


def test_model_executor_propagates_metadata() -> None:
    executor = ModelExecutor()

    result = executor.execute(
        ModelExecutionRequest(
            role=AgentRole.QA,
            project="lummevia-os",
            environment="development",
            prompt="Validate edge cases",
            system_prompt="You are a QA",
            metadata={"run_id": "run-123", "issue_id": "LUM-42"},
        )
    )

    assert result.metadata["run_id"] == "run-123"
    assert result.metadata["issue_id"] == "LUM-42"
    assert result.metadata["provider"] == "OPENROUTER"
    assert result.metadata["latency_ms"] >= 0
    assert result.metadata["fallback_used"] is False


def test_model_executor_handles_provider_error() -> None:
    executor = ModelExecutor(
        provider=FakeModelProvider(fail_for_prompts={"Break now"}),
    )

    with pytest.raises(
        ModelExecutionError,
        match="Model provider execution failed for role 'DEV'",
    ) as exc_info:
        executor.execute(
            ModelExecutionRequest(
                role=AgentRole.DEV,
                project="lummevia-os",
                environment="development",
                prompt="Break now",
                system_prompt="You are a DEV",
                metadata={},
            )
        )

    assert exc_info.value.provider == "OPENROUTER"
    assert exc_info.value.model == "deepseek/deepseek-chat-lite"


def test_base_agent_execute_model_works() -> None:
    agent = PMAgent()

    result = agent.execute_model(
        "Turn intent into brief",
        project="lummevia-os",
        environment="production",
        system_prompt="You are a PM",
        metadata={"run_id": "run-321"},
    )

    assert result.model == "deepseek/deepseek-chat-pro"
    assert result.metadata["run_id"] == "run-321"
    assert result.metadata["role"] == "PM"


def test_run_still_raises_agent_not_implemented_error() -> None:
    agent = DevAgent()

    with pytest.raises(AgentNotImplementedError):
        agent.run(
            AgentRunRequest(
                input="Placeholder",
                project="lummevia-os",
                environment="development",
            )
        )
