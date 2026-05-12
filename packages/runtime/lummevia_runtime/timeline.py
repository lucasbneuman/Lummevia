from __future__ import annotations

from lummevia_timeline import TimelineRegistry, build_workflow_timeline

from lummevia_runtime.state import RuntimeState


def sync_timeline_for_state(state: RuntimeState) -> None:
    timeline = build_workflow_timeline(state)
    registry = TimelineRegistry.default()
    stored_timeline = registry.create_timeline(
        workflow_run_id=timeline.workflow_run_id,
        project=timeline.project,
        issue_id=timeline.issue_id,
        metadata=timeline.metadata,
    )
    for event in timeline.events:
        stored_timeline = registry.add_event(timeline.workflow_run_id, event)
    state.metadata["timeline_id"] = stored_timeline.timeline_id
    state.metadata["timeline_event_count"] = timeline.metadata["timeline_event_count"]
    state.metadata["timeline_sources"] = timeline.metadata["timeline_sources"]
    state.metadata["replay_available"] = timeline.metadata["replay_available"]
