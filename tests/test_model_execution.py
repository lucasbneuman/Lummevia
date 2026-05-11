import httpx
import pytest

from lummevia_core import AgentRole

from lummevia_agents import (
    AgentNotImplementedError,
    AgentRunRequest,
    DeepSeekModelProvider,
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
    assert first.provider == "FAKE"
    assert first.model == "fake:pm"
    assert first.metadata["resolved_provider"] == "DEEPSEEK"
    assert first.metadata["resolved_model"] == "deepseek-v4-strong-placeholder"


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

    assert result.provider == "FAKE"
    assert result.model == "fake:pm"
    assert result.metadata["role"] == "PM"
    assert result.metadata["resolved_model"] == "deepseek-v4-strong-placeholder"


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

    assert result.provider == "FAKE"
    assert result.model == "fake:dev"
    assert result.metadata["resolved_model"] == "deepseek-v4-lite-placeholder"


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
    assert result.metadata["provider"] == "FAKE"
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

    assert exc_info.value.provider == "DEEPSEEK"
    assert exc_info.value.model == "deepseek-v4-lite-placeholder"


def test_deepseek_model_provider_parses_mock_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://api.deepseek.com/chat/completions")
        payload = request.read().decode("utf-8")
        assert "deepseek-v4-strong-placeholder" in payload
        assert "You are a PM" in payload
        assert "Summarize the brief" in payload
        return httpx.Response(
            status_code=200,
            json={
                "id": "gen-123",
                "model": "deepseek-v4-pro",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "Business summary from DeepSeek.",
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 8,
                    "total_tokens": 18,
                },
            },
        )

    provider = DeepSeekModelProvider(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    executor = ModelExecutor(provider=provider)

    result = executor.execute(
        ModelExecutionRequest(
            role=AgentRole.PM,
            project="lummevia-os",
            environment="development",
            prompt="Summarize the brief",
            system_prompt="You are a PM",
        )
    )

    assert result.provider == "DEEPSEEK"
    assert result.model == "deepseek-v4-pro"
    assert result.output == "Business summary from DeepSeek."
    assert result.raw_output["usage"]["total_tokens"] == 18
    assert result.metadata["provider_adapter"] == "deepseek"


def test_deepseek_model_provider_handles_http_errors_clearly() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=429,
            json={
                "error": {
                    "code": 429,
                    "message": "Rate limit exceeded",
                }
            },
        )

    provider = DeepSeekModelProvider(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    executor = ModelExecutor(provider=provider)

    with pytest.raises(
        ModelExecutionError,
        match="Model provider execution failed for role 'PM'",
    ) as exc_info:
        executor.execute(
            ModelExecutionRequest(
                role=AgentRole.PM,
                project="lummevia-os",
                environment="development",
                prompt="Summarize the brief",
                system_prompt="You are a PM",
            )
        )

    assert exc_info.value.provider == "DEEPSEEK"
    assert exc_info.value.model == "deepseek-v4-strong-placeholder"


def test_base_agent_execute_model_works() -> None:
    agent = PMAgent()

    result = agent.execute_model(
        "Turn intent into brief",
        project="lummevia-os",
        environment="production",
        system_prompt="You are a PM",
        metadata={"run_id": "run-321"},
    )

    assert result.model == "fake:pm"
    assert result.metadata["run_id"] == "run-321"
    assert result.metadata["role"] == "PM"
    assert result.metadata["resolved_model"] == "deepseek-v4-strong-placeholder"


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
