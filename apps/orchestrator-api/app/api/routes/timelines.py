from fastapi import APIRouter, HTTPException, status

from app.core.persistence import operational_persistence
from app.api.routes import runtime as runtime_routes
from lummevia_runtime import PersistedRunNotFoundError, RuntimeNotFoundError
from lummevia_timeline import TimelineRegistry, WorkflowTimeline, build_workflow_timeline


router = APIRouter(prefix="/timelines", tags=["timelines"])


def _get_timeline(workflow_run_id: str) -> WorkflowTimeline | None:
    timeline = TimelineRegistry.default().get_timeline(workflow_run_id)
    if timeline is not None:
        return timeline

    try:
        state = runtime_routes.runtime_service.get_run(workflow_run_id)
    except RuntimeNotFoundError:
        if runtime_routes.runtime_repository is None:
            return None
        try:
            state = runtime_routes.runtime_repository.get_run(workflow_run_id)
        except PersistedRunNotFoundError:
            return None

    if operational_persistence is not None:
        rebuilt = build_workflow_timeline(
            state,
            conversations=[
                thread
                for thread in operational_persistence.conversations.list_threads()
                if thread.project == state.run.project and thread.issue_id == state.run.issue_id
            ],
            sessions=[
                session
                for session in operational_persistence.sessions.list_sessions()
                if session.project == state.run.project and session.issue_id == state.run.issue_id
            ],
            reviews=[
                review
                for review in operational_persistence.reviews.list_reviews()
                if review.metadata.get("project") == state.run.project
                and review.metadata.get("issue_id") == state.run.issue_id
            ],
            memory_records=[
                record
                for record in operational_persistence.memory.list_records()
                if record.project == state.run.project
                and record.metadata.get("issue_id") == state.run.issue_id
            ],
        )
    else:
        rebuilt = build_workflow_timeline(state)
    TimelineRegistry.default().create_timeline(
        workflow_run_id=rebuilt.workflow_run_id,
        project=rebuilt.project,
        issue_id=rebuilt.issue_id,
        metadata=rebuilt.metadata,
    )
    for event in rebuilt.events:
        TimelineRegistry.default().add_event(rebuilt.workflow_run_id, event)
    return TimelineRegistry.default().get_timeline(workflow_run_id)


@router.get("", response_model=list[WorkflowTimeline])
def list_timelines() -> list[WorkflowTimeline]:
    return TimelineRegistry.default().list_timelines()


@router.get("/{workflow_run_id}", response_model=WorkflowTimeline)
def get_timeline(workflow_run_id: str) -> WorkflowTimeline:
    timeline = _get_timeline(workflow_run_id)
    if timeline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Timeline for workflow run '{workflow_run_id}' not found.",
        )
    return timeline
