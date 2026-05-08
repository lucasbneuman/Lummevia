from __future__ import annotations

from lummevia_integrations.phoenix.exceptions import (
    PhoenixIntegrationNotImplementedError,
)
from lummevia_integrations.phoenix.schemas import (
    PhoenixEvaluationPayload,
    PhoenixSpanPayload,
    PhoenixTracePayload,
)


class PhoenixClient:
    def _not_implemented(self, operation: str) -> None:
        raise PhoenixIntegrationNotImplementedError(
            "Phoenix integration is not implemented yet. "
            f"Operation '{operation}' is still a placeholder."
        )

    def create_trace(self, payload: PhoenixTracePayload) -> None:
        self._not_implemented("create_trace")

    def create_span(self, payload: PhoenixSpanPayload) -> None:
        self._not_implemented("create_span")

    def add_evaluation(self, payload: PhoenixEvaluationPayload) -> None:
        self._not_implemented("add_evaluation")

    def get_trace(self, trace_id: str) -> None:
        self._not_implemented("get_trace")
