from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from lummevia_integrations.phoenix.client import PhoenixClient
from lummevia_runtime.observability import RuntimeObserver
from lummevia_runtime.state import RuntimeState


class PhoenixRuntimeObserver(RuntimeObserver):
    def __init__(
        self,
        client: PhoenixClient,
        *,
        environment: str,
    ) -> None:
        self._client = client
        self._environment = environment

    @contextmanager
    def observe_workflow_run(self, state: RuntimeState) -> Iterator[None]:
        with self._client.start_as_current_span(
            f"workflow_run:{state.run.workflow_name}",
            attributes=self._build_attributes(state),
        ) as span:
            try:
                yield
            except Exception as exc:
                self._record_exception(span, state, exc)
                raise
            finally:
                self._apply_state(
                    span,
                    state,
                    event_count=len(state.run.events),
                )

    @contextmanager
    def observe_step(self, state: RuntimeState, step_name: str) -> Iterator[None]:
        start_index = len(state.run.events)
        with self._client.start_as_current_span(
            f"step:{step_name}",
            attributes=self._build_attributes(state, current_step=step_name),
        ) as span:
            try:
                yield
            except Exception as exc:
                self._record_exception(span, state, exc, step_name=step_name)
                raise
            finally:
                event_count = len(state.run.events[start_index:])
                self._apply_state(
                    span,
                    state,
                    current_step=step_name,
                    event_count=event_count,
                )
                self._add_runtime_events(span, state, start_index)

    def record_runtime_error(
        self,
        state: RuntimeState,
        error: Exception,
        *,
        step_name: str | None = None,
    ) -> None:
        if not self._client.enabled:
            return

        span = trace.get_current_span()
        if span is not None and span.is_recording():
            self._record_exception(span, state, error, step_name=step_name)
            self._client.force_flush()
            return

        with self._client.start_as_current_span(
            "runtime_error",
            attributes=self._build_attributes(state, current_step=step_name),
        ) as error_span:
            self._record_exception(error_span, state, error, step_name=step_name)
        self._client.force_flush()

    def _build_attributes(
        self,
        state: RuntimeState,
        *,
        current_step: str | None = None,
    ) -> dict[str, bool | int | str]:
        attributes: dict[str, bool | int | str] = {
            "run_id": state.run.run_id,
            "workflow": state.run.workflow_name,
            "project": state.run.project,
            "issue_id": state.run.issue_id,
            "environment": self._environment,
            "current_step": current_step or state.run.current_step or "workflow_start",
            "status": state.run.status.value,
            "loop_count": state.loop_count,
        }
        for key in ("thread_id", "conversation_status"):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = value
        for key in ("iteration_count", "message_count"):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = int(value)
        for key in ("session_attempts", "output_count", "event_count"):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = int(value)
        session_id = state.metadata.get("current_session_id")
        if session_id is not None:
            attributes["session_id"] = str(session_id)
        for key in ("session_status", "session_role"):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = str(value)
        memory_records_created = state.metadata.get("memory_records_created")
        if memory_records_created is not None:
            attributes["memory_records_created"] = int(memory_records_created)
        project_memory_count = state.metadata.get("project_memory_count")
        if project_memory_count is not None:
            attributes["project_memory_count"] = int(project_memory_count)
        memory_categories = state.metadata.get("memory_categories")
        if memory_categories:
            attributes["memory_categories"] = ",".join(str(category) for category in memory_categories)
        review_metadata = self._extract_review_metadata(state, current_step=current_step)
        attributes.update(review_metadata)
        kilo_step = (
            state.metadata.get("kilo_execution_by_step", {}).get(current_step)
            if current_step is not None
            else None
        )
        if kilo_step is not None:
            attributes["kilo_mode"] = kilo_step["kilo_mode"]
            attributes["execution_id"] = kilo_step["execution_id"]
            if kilo_step.get("session_id") is not None:
                attributes["session_id"] = kilo_step["session_id"]
            attributes["role"] = kilo_step["role"]
            attributes["task_id"] = kilo_step["task_id"]
            attributes["kilo_status"] = kilo_step["kilo_status"]
            attributes["retry_count"] = kilo_step["retry_count"]
            attributes["attempts_count"] = kilo_step["attempts_count"]
            attributes["final_status"] = kilo_step["final_status"]
        return attributes

    def _extract_review_metadata(
        self,
        state: RuntimeState,
        *,
        current_step: str | None,
    ) -> dict[str, str]:
        if current_step is None:
            return {}

        step_metadata = state.run.metadata.get(current_step, {})
        review_metadata = {}
        for key in ("review_id", "review_type", "review_status", "review_decision"):
            value = step_metadata.get(key)
            if value is not None:
                review_metadata[key] = value
        return review_metadata

    def _apply_state(
        self,
        span,
        state: RuntimeState,
        *,
        current_step: str | None = None,
        event_count: int,
    ) -> None:
        if span is None:
            return

        for key, value in self._build_attributes(
            state,
            current_step=current_step,
        ).items():
            span.set_attribute(key, value)

        span.set_attribute("runtime_event_count", event_count)
        if span.status.status_code is not StatusCode.ERROR:
            span.set_status(Status(StatusCode.OK))
        self._client.force_flush()

    def _add_runtime_events(self, span, state: RuntimeState, start_index: int) -> None:
        if span is None:
            return

        for event in state.run.events[start_index:]:
            span.add_event(
                event.metadata.get("type", "RUNTIME_EVENT"),
                {
                    "step_name": event.step_name,
                    "status": event.status.value,
                    "message": event.message,
                    "loop_count": int(event.metadata.get("loop_count", state.loop_count)),
                },
            )

    def _record_exception(
        self,
        span,
        state: RuntimeState,
        error: Exception,
        *,
        step_name: str | None = None,
    ) -> None:
        if span is None:
            return

        span.record_exception(error)
        span.set_status(Status(StatusCode.ERROR, str(error)))
        span.set_attribute("status", "FAILED")
        span.set_attribute(
            "current_step",
            step_name or state.run.current_step or "runtime_error",
        )
