import pytest
from pydantic import ValidationError

from lummevia_integrations.phoenix import (
    PhoenixClient,
    PhoenixEvaluationPayload,
    PhoenixIntegrationNotImplementedError,
    PhoenixSpanPayload,
    PhoenixTracePayload,
    PhoenixTraceRef,
)


def test_phoenix_client_can_be_instantiated() -> None:
    client = PhoenixClient()

    assert isinstance(client, PhoenixClient)


def test_phoenix_trace_ref_accepts_valid_payload() -> None:
    trace_ref = PhoenixTraceRef(trace_id="trace-001")

    assert trace_ref.trace_id == "trace-001"


def test_phoenix_trace_payload_accepts_valid_payload() -> None:
    payload = PhoenixTracePayload(
        run_id="run-001",
        workflow="loop-desarrollo",
        project="lummevia-os",
        environment="development",
        issue_id="LUM-101",
        agent_role="dev",
        agent_name="builder-agent",
        provider="openai",
        model="gpt-4.1-mini",
        fallback_used=True,
        status="completed",
        latency_ms=1280,
        estimated_cost=0.12,
        error=None,
        metadata={"commit_sha": "abc123def456"},
    )

    assert payload.run_id == "run-001"
    assert payload.fallback_used is True
    assert payload.latency_ms == 1280
    assert payload.estimated_cost == 0.12


def test_phoenix_trace_payload_defaults_fallback_to_false() -> None:
    payload = PhoenixTracePayload(
        run_id="run-002",
        workflow="loop-desarrollo",
        project="lummevia-os",
        environment="development",
        issue_id="LUM-102",
        agent_role="qa",
        agent_name="validator-agent",
        provider="openai",
        model="gpt-4.1-mini",
        status="completed",
        metadata={},
    )

    assert payload.fallback_used is False


def test_phoenix_span_payload_accepts_valid_payload() -> None:
    payload = PhoenixSpanPayload(
        trace_id="trace-001",
        name="draft-implementation",
        input="Summarize requirements",
        output="Requirements summarized",
        metadata={"step": "implementation"},
    )

    assert payload.trace_id == "trace-001"
    assert payload.name == "draft-implementation"


def test_phoenix_evaluation_payload_accepts_valid_payload() -> None:
    payload = PhoenixEvaluationPayload(
        trace_id="trace-001",
        name="quality-score",
        score=0.92,
        label="pass",
        explanation="The trace satisfied the expected validation criteria.",
    )

    assert payload.score == 0.92
    assert payload.label == "pass"


def test_phoenix_trace_payload_requires_run_id() -> None:
    with pytest.raises(ValidationError):
        PhoenixTracePayload(
            run_id="",
            workflow="loop-desarrollo",
            project="lummevia-os",
            environment="development",
            issue_id="LUM-101",
            agent_role="dev",
            agent_name="builder-agent",
            provider="openai",
            model="gpt-4.1-mini",
            status="completed",
            metadata={},
        )


def test_phoenix_trace_payload_rejects_negative_latency() -> None:
    with pytest.raises(ValidationError):
        PhoenixTracePayload(
            run_id="run-003",
            workflow="loop-desarrollo",
            project="lummevia-os",
            environment="development",
            issue_id="LUM-103",
            agent_role="dev",
            agent_name="builder-agent",
            provider="openai",
            model="gpt-4.1-mini",
            status="failed",
            latency_ms=-1,
            metadata={},
        )


def test_phoenix_trace_payload_rejects_negative_estimated_cost() -> None:
    with pytest.raises(ValidationError):
        PhoenixTracePayload(
            run_id="run-004",
            workflow="loop-desarrollo",
            project="lummevia-os",
            environment="development",
            issue_id="LUM-104",
            agent_role="dev",
            agent_name="builder-agent",
            provider="openai",
            model="gpt-4.1-mini",
            status="failed",
            estimated_cost=-0.01,
            metadata={},
        )


@pytest.mark.parametrize(
    "call_name",
    [
        "create_trace",
        "create_span",
        "add_evaluation",
        "get_trace",
    ],
)
def test_phoenix_client_methods_raise_clear_placeholder_error(call_name: str) -> None:
    client = PhoenixClient()
    trace_payload = PhoenixTracePayload(
        run_id="run-001",
        workflow="loop-desarrollo",
        project="lummevia-os",
        environment="development",
        issue_id="LUM-101",
        agent_role="dev",
        agent_name="builder-agent",
        provider="openai",
        model="gpt-4.1-mini",
        fallback_used=False,
        status="completed",
        latency_ms=640,
        estimated_cost=0.03,
        metadata={},
    )
    span_payload = PhoenixSpanPayload(
        trace_id="trace-001",
        name="collect-context",
        input="Read docs",
        output="Docs collected",
        metadata={"phase": "context"},
    )
    evaluation_payload = PhoenixEvaluationPayload(
        trace_id="trace-001",
        name="correctness",
        score=1.0,
        label="pass",
        explanation="Placeholder payload is valid.",
    )

    with pytest.raises(
        PhoenixIntegrationNotImplementedError,
        match="Phoenix integration is not implemented yet",
    ):
        if call_name == "create_trace":
            client.create_trace(trace_payload)
        elif call_name == "create_span":
            client.create_span(span_payload)
        elif call_name == "add_evaluation":
            client.add_evaluation(evaluation_payload)
        else:
            client.get_trace("trace-001")
