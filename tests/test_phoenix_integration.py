from __future__ import annotations

from collections.abc import Sequence

import pytest
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from pydantic import ValidationError

from lummevia_integrations.phoenix import (
    PhoenixClient,
    PhoenixEvaluationPayload,
    PhoenixSpanPayload,
    PhoenixTracePayload,
    PhoenixTraceRef,
)


class RecordingSpanExporter(SpanExporter):
    def __init__(self) -> None:
        self.spans = []

    def export(self, spans: Sequence[object]) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


def test_phoenix_client_can_be_instantiated() -> None:
    client = PhoenixClient(enabled=False)

    assert isinstance(client, PhoenixClient)


def test_phoenix_client_builds_otlp_endpoint_from_base_url() -> None:
    client = PhoenixClient(base_url="http://phoenix.internal:7007/", enabled=False)

    assert client.base_url == "http://phoenix.internal:7007"
    assert client.endpoint == "http://phoenix.internal:7007/v1/traces"


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


def test_phoenix_client_disabled_mode_yields_no_span() -> None:
    client = PhoenixClient(enabled=False)

    with client.start_as_current_span("disabled-span") as span:
        assert span is None


def test_phoenix_client_exports_spans_with_custom_exporter() -> None:
    exporter = RecordingSpanExporter()
    client = PhoenixClient(
        base_url="http://phoenix:6006",
        span_exporter=exporter,
    )

    with client.start_as_current_span(
        "workflow_run:development_loop",
        attributes={
            "run_id": "run-001",
            "project": "lummevia-os",
            "issue_id": "OS-100",
        },
    ):
        pass

    client.force_flush()

    assert exporter.spans
    exported = exporter.spans[0]
    assert exported.attributes["run_id"] == "run-001"
    assert exported.attributes["project"] == "lummevia-os"
    assert exported.attributes["issue_id"] == "OS-100"
