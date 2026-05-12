from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from lummevia_timeline.schemas import TimelineEvent, WorkflowTimeline


class TimelineRegistry:
    _default_instance: ClassVar["TimelineRegistry" | None] = None

    def __init__(self) -> None:
        self._timelines: dict[str, WorkflowTimeline] = {}

    @classmethod
    def default(cls) -> "TimelineRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._timelines.clear()

    def create_timeline(
        self,
        *,
        workflow_run_id: str,
        project: str,
        issue_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowTimeline:
        timeline = WorkflowTimeline(
            workflow_run_id=workflow_run_id,
            project=project,
            issue_id=issue_id,
            created_at=datetime.now(UTC),
            metadata=metadata or {},
        )
        self._timelines[workflow_run_id] = timeline
        return timeline

    def add_event(
        self,
        workflow_run_id: str,
        event: TimelineEvent,
    ) -> WorkflowTimeline:
        timeline = self._timelines[workflow_run_id]
        updated = timeline.model_copy(
            update={
                "events": sorted(
                    [*timeline.events, event],
                    key=lambda timeline_event: (
                        timeline_event.created_at,
                        timeline_event.event_id,
                    ),
                )
            }
        )
        self._timelines[workflow_run_id] = updated
        return updated

    def get_timeline(self, workflow_run_id: str) -> WorkflowTimeline | None:
        return self._timelines.get(workflow_run_id)

    def list_timelines(self) -> list[WorkflowTimeline]:
        return sorted(
            self._timelines.values(),
            key=lambda timeline: timeline.created_at,
            reverse=True,
        )
