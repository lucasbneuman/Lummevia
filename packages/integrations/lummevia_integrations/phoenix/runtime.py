from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Callable

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
        persistence_metadata_supplier: Callable[[RuntimeState], dict[str, object]] | None = None,
    ) -> None:
        self._client = client
        self._environment = environment
        self._persistence_metadata_supplier = persistence_metadata_supplier

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
        for key in ("thread_id", "conversation_status", "conversation_phase"):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = value
        for key in (
            "health_status",
            "watchdog_id",
            "recovery_action_id",
            "dead_letter_id",
        ):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = str(value)
        for key in ("retry_attempts", "watchdog_count", "recovery_action_count", "dead_letter_count"):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = int(value)
        for key in ("stuck_detected", "workflow_cancelled"):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = bool(value)
        for key in ("decision_requires_human_review",):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = bool(value)
        for key in (
            "strategy_id",
            "strategy_type",
            "risk_level",
            "qa_level",
            "sandbox_level",
            "selected_model",
            "selected_provider",
            "execution_mode",
            "budget_id",
            "cost_control_status",
            "cost_recommendation",
        ):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = str(value)
        estimated_cost_total = state.metadata.get("estimated_cost_total")
        if estimated_cost_total is not None:
            attributes["estimated_cost_total"] = float(estimated_cost_total)
        for key in ("model_calls_count", "tokens_estimated_total"):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = int(value)
        for key in ("iteration_count", "message_count", "pending_questions_count", "brief_version"):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = int(value)
        for key in ("session_attempts", "output_count", "event_count"):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = int(value)
        for key in ("files_changed_count", "lines_added", "lines_removed", "artifact_count"):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = int(value)
        for key in ("decision_count",):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = int(value)
        for key in ("adaptive_plan_count", "mutation_count"):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = int(value)
        for key in ("learning_signal_count", "insight_count", "recommendation_count"):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = int(value)
        for key in ("change_set_id", "current_change_set_id", "validation_status", "validation_notes", "qa_checked_change_set_id"):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = str(value)
        for key in (
            "decision_id",
            "decision_type",
            "decision_status",
            "autonomy_level",
            "decision_review_id",
            "adaptive_plan_id",
            "adaptive_plan_status",
            "replanning_trigger",
            "adaptive_plan_review_id",
            "learning_severity",
            "recommendation_type",
        ):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = str(value)
        decision_confidence = state.metadata.get("decision_confidence")
        if decision_confidence is not None:
            attributes["confidence"] = float(decision_confidence)
        workspace_id = state.metadata.get("workspace_id")
        if workspace_id is not None:
            attributes["workspace_id"] = str(workspace_id)
        branch_name = state.metadata.get("branch_name")
        if branch_name is not None:
            attributes["branch_name"] = str(branch_name)
        worktree_path = state.metadata.get("worktree_path")
        if worktree_path is not None:
            attributes["worktree_path"] = str(worktree_path)
        workspace_status = state.metadata.get("workspace_status")
        if workspace_status is not None:
            attributes["workspace_status"] = str(workspace_status)
        for key in ("resource_locks_count", "active_locks_count"):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = int(value)
        allocation_id = state.metadata.get("allocation_id")
        if allocation_id is not None:
            attributes["allocation_id"] = str(allocation_id)
        allocation_status = state.metadata.get("allocation_status")
        if allocation_status is not None:
            attributes["allocation_status"] = str(allocation_status)
        for key in ("capacity_used_slots", "capacity_max_slots", "allocated_resources_count"):
            value = state.metadata.get(key)
            if value is not None:
                attributes[key] = int(value)
        queue_id = state.metadata.get("queue_id")
        if queue_id is not None:
            attributes["queue_id"] = str(queue_id)
        current_queue_item_id = state.metadata.get("current_queue_item_id")
        if current_queue_item_id is not None:
            attributes["current_queue_item_id"] = str(current_queue_item_id)
            attributes["queue_item_id"] = str(current_queue_item_id)
        for key in ("queue_size", "ready_count", "blocked_count", "completed_count"):
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
        timeline_event_count = state.metadata.get("timeline_event_count")
        if timeline_event_count is not None:
            attributes["timeline_event_count"] = int(timeline_event_count)
        timeline_sources = state.metadata.get("timeline_sources")
        if timeline_sources:
            attributes["timeline_sources"] = ",".join(
                str(source) for source in timeline_sources
            )
        replay_available = state.metadata.get("replay_available")
        if replay_available is not None:
            attributes["replay_available"] = bool(replay_available)
        memory_records_created = state.metadata.get("memory_records_created")
        if memory_records_created is not None:
            attributes["memory_records_created"] = int(memory_records_created)
        project_memory_count = state.metadata.get("project_memory_count")
        if project_memory_count is not None:
            attributes["project_memory_count"] = int(project_memory_count)
        memory_categories = state.metadata.get("memory_categories")
        if memory_categories:
            attributes["memory_categories"] = ",".join(str(category) for category in memory_categories)
        mutation_types = state.metadata.get("mutation_types")
        if mutation_types:
            attributes["mutation_types"] = ",".join(str(mutation_type) for mutation_type in mutation_types)
        if self._persistence_metadata_supplier is not None:
            for key, value in self._persistence_metadata_supplier(state).items():
                if value is None:
                    continue
                if isinstance(value, (bool, int, str)):
                    attributes[key] = value
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
            if kilo_step.get("retry_attempts") is not None:
                attributes["retry_attempts"] = int(kilo_step["retry_attempts"])
            attributes["attempts_count"] = kilo_step["attempts_count"]
            attributes["final_status"] = kilo_step["final_status"]
            if kilo_step.get("health_status") is not None:
                attributes["health_status"] = str(kilo_step["health_status"])
            if kilo_step.get("watchdog_id") is not None:
                attributes["watchdog_id"] = str(kilo_step["watchdog_id"])
            if kilo_step.get("recovery_action_id") is not None:
                attributes["recovery_action_id"] = str(kilo_step["recovery_action_id"])
            if kilo_step.get("dead_letter_id") is not None:
                attributes["dead_letter_id"] = str(kilo_step["dead_letter_id"])
            if kilo_step.get("queue_id") is not None:
                attributes["queue_id"] = str(kilo_step["queue_id"])
            if kilo_step.get("queue_item_id") is not None:
                attributes["queue_item_id"] = str(kilo_step["queue_item_id"])
            if kilo_step.get("workspace_id") is not None:
                attributes["workspace_id"] = str(kilo_step["workspace_id"])
            if kilo_step.get("branch_name") is not None:
                attributes["branch_name"] = str(kilo_step["branch_name"])
            if kilo_step.get("worktree_path") is not None:
                attributes["worktree_path"] = str(kilo_step["worktree_path"])
            if kilo_step.get("workspace_status") is not None:
                attributes["workspace_status"] = str(kilo_step["workspace_status"])
            if kilo_step.get("allocation_id") is not None:
                attributes["allocation_id"] = str(kilo_step["allocation_id"])
            if kilo_step.get("allocation_status") is not None:
                attributes["allocation_status"] = str(kilo_step["allocation_status"])
            if kilo_step.get("capacity_id") is not None:
                attributes["capacity_id"] = str(kilo_step["capacity_id"])
            if kilo_step.get("capacity_used_slots") is not None:
                attributes["capacity_used_slots"] = int(kilo_step["capacity_used_slots"])
            if kilo_step.get("capacity_max_slots") is not None:
                attributes["capacity_max_slots"] = int(kilo_step["capacity_max_slots"])
            if kilo_step.get("allocated_resources_count") is not None:
                attributes["allocated_resources_count"] = int(
                    kilo_step["allocated_resources_count"]
                )
            if kilo_step.get("real_execution") is not None:
                attributes["real_execution"] = bool(kilo_step["real_execution"])
            if kilo_step.get("exit_code") is not None:
                attributes["exit_code"] = int(kilo_step["exit_code"])
            if kilo_step.get("safety_status") is not None:
                attributes["safety_status"] = str(kilo_step["safety_status"])
            if kilo_step.get("workspace_path") is not None:
                attributes["workspace_path"] = str(kilo_step["workspace_path"])
            if kilo_step.get("stdout_bytes") is not None:
                attributes["stdout_bytes"] = int(kilo_step["stdout_bytes"])
            if kilo_step.get("stderr_bytes") is not None:
                attributes["stderr_bytes"] = int(kilo_step["stderr_bytes"])
            if kilo_step.get("change_set_id") is not None:
                attributes["change_set_id"] = str(kilo_step["change_set_id"])
            if kilo_step.get("files_changed_count") is not None:
                attributes["files_changed_count"] = int(kilo_step["files_changed_count"])
            if kilo_step.get("lines_added") is not None:
                attributes["lines_added"] = int(kilo_step["lines_added"])
            if kilo_step.get("lines_removed") is not None:
                attributes["lines_removed"] = int(kilo_step["lines_removed"])
            if kilo_step.get("artifact_count") is not None:
                attributes["artifact_count"] = int(kilo_step["artifact_count"])
            for key in (
                "strategy_id",
                "strategy_type",
                "risk_level",
                "qa_level",
                "sandbox_level",
                "selected_model",
                "selected_provider",
                "execution_mode",
            ):
                if kilo_step.get(key) is not None:
                    attributes[key] = str(kilo_step[key])
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
