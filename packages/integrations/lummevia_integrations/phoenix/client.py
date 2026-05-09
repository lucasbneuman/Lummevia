from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter

from lummevia_integrations.phoenix.schemas import (
    PhoenixEvaluationPayload,
    PhoenixSpanPayload,
    PhoenixTracePayload,
)


class PhoenixClient:
    def __init__(
        self,
        *,
        base_url: str = "http://phoenix:6006",
        enabled: bool = True,
        service_name: str = "lummevia-orchestrator-api",
        environment: str = "development",
        tracer_provider: TracerProvider | None = None,
        span_exporter: SpanExporter | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/v1/traces"
        self.enabled = enabled
        self._tracer_provider = tracer_provider

        if not self.enabled:
            self._tracer = None
            return

        if self._tracer_provider is None:
            exporter = span_exporter or OTLPSpanExporter(endpoint=self.endpoint)
            self._tracer_provider = TracerProvider(
                resource=Resource.create(
                    {
                        "service.name": service_name,
                        "deployment.environment": environment,
                    }
                )
            )
            self._tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

        self._tracer = self._tracer_provider.get_tracer("lummevia_integrations.phoenix")

    @property
    def tracer_provider(self) -> TracerProvider | None:
        return self._tracer_provider

    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        *,
        attributes: dict[str, bool | int | str] | None = None,
    ) -> Iterator[object | None]:
        if not self.enabled or self._tracer is None:
            yield None
            return

        with self._tracer.start_as_current_span(name, attributes=attributes or {}) as span:
            yield span

    def create_trace(self, payload: PhoenixTracePayload) -> None:
        with self.start_as_current_span(
            f"trace:{payload.workflow}",
            attributes={
                "run_id": payload.run_id,
                "workflow": payload.workflow,
                "project": payload.project,
                "issue_id": payload.issue_id,
                "environment": payload.environment,
                "status": payload.status,
            },
        ):
            return None

    def create_span(self, payload: PhoenixSpanPayload) -> None:
        with self.start_as_current_span(
            payload.name,
            attributes={
                "trace_id": payload.trace_id,
                **{key: str(value) for key, value in payload.metadata.items()},
            },
        ) as span:
            if span is not None and payload.input is not None:
                span.add_event("input", {"value": payload.input})
            if span is not None and payload.output is not None:
                span.add_event("output", {"value": payload.output})

    def add_evaluation(self, payload: PhoenixEvaluationPayload) -> None:
        with self.start_as_current_span(
            f"evaluation:{payload.name}",
            attributes={
                "trace_id": payload.trace_id,
                "label": payload.label,
                "score": str(payload.score),
            },
        ) as span:
            if span is not None:
                span.add_event("evaluation", {"explanation": payload.explanation})

    def get_trace(self, trace_id: str) -> None:
        return None

    def force_flush(self) -> bool:
        if not self.enabled or self._tracer_provider is None:
            return True

        return self._tracer_provider.force_flush()
