from fastapi import APIRouter, HTTPException, status

from app.api.routes import runtime as runtime_routes
from lummevia_code_changes import CodeChangeRegistry, CodeChangeSet, CodeChangeStatus
from lummevia_runtime.timeline import sync_timeline_for_state
from lummevia_runtime.supervisor import record_supervisor_event
from lummevia_supervisor import ExecutionHealthStatus


router = APIRouter(prefix="/code-changes", tags=["code-changes"])


def _get_registry() -> CodeChangeRegistry:
    return CodeChangeRegistry.default()


@router.get("", response_model=list[CodeChangeSet])
def list_code_changes() -> list[CodeChangeSet]:
    return _get_registry().list_change_sets()


@router.get("/{change_set_id}", response_model=CodeChangeSet)
def get_code_change(change_set_id: str) -> CodeChangeSet:
    change_set = _get_registry().get_change_set(change_set_id)
    if change_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Code change set '{change_set_id}' not found.",
        )
    return change_set


@router.post("/{change_set_id}/discard", response_model=CodeChangeSet)
def discard_code_change(change_set_id: str) -> CodeChangeSet:
    change_set = _get_registry().get_change_set(change_set_id)
    if change_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Code change set '{change_set_id}' not found.",
        )
    discarded = _get_registry().update_status(
        change_set_id,
        status=CodeChangeStatus.DISCARDED,
        metadata={"discarded": True},
    )

    run_id = discarded.metadata.get("run_id")
    if isinstance(run_id, str):
        try:
            state = runtime_routes.runtime_service.get_run(run_id)
        except Exception:
            state = None
        if state is not None:
            state.metadata.setdefault("code_change_sets", {})[discarded.change_set_id] = (
                discarded.model_dump(mode="json")
            )
            record_supervisor_event(
                state,
                event_type="CODE_CHANGE_DISCARDED",
                status=ExecutionHealthStatus.CANCELLED,
                metadata={
                    "change_set_id": discarded.change_set_id,
                    "task_id": discarded.task_id,
                },
            )
            sync_timeline_for_state(state)
    return discarded
