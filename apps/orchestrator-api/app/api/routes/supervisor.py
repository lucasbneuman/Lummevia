from fastapi import APIRouter, HTTPException, status

from app.api.routes import runtime as runtime_routes
from lummevia_supervisor import (
    DeadLetterItem,
    ExecutionWatchdog,
    RecoveryAction,
    SupervisorRegistry,
)
from lummevia_runtime.timeline import sync_timeline_for_state


router = APIRouter(prefix="/supervisor", tags=["supervisor"])


@router.get("/watchdogs", response_model=list[ExecutionWatchdog])
def list_watchdogs() -> list[ExecutionWatchdog]:
    return SupervisorRegistry.default().list_watchdogs()


@router.get("/recovery-actions", response_model=list[RecoveryAction])
def list_recovery_actions() -> list[RecoveryAction]:
    return SupervisorRegistry.default().list_recovery_actions()


@router.get("/dead-letters", response_model=list[DeadLetterItem])
def list_dead_letters() -> list[DeadLetterItem]:
    return SupervisorRegistry.default().list_dead_letters()


@router.post("/workflows/{workflow_run_id}/cancel")
def cancel_workflow(workflow_run_id: str):
    try:
        state = runtime_routes.runtime_service.get_run(workflow_run_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runtime run '{workflow_run_id}' not found.",
        ) from exc
    cancelled = SupervisorRegistry.default().cancel_workflow(state)
    sync_timeline_for_state(cancelled)
    return cancelled


@router.post("/watchdogs/detect-stuck", response_model=list[ExecutionWatchdog])
def detect_stuck_watchdogs() -> list[ExecutionWatchdog]:
    detected = SupervisorRegistry.default().detect_stuck()
    for watchdog in detected:
        try:
            state = runtime_routes.runtime_service.get_run(watchdog.workflow_run_id)
        except Exception:
            continue
        SupervisorRegistry.default()._sync_runtime_metadata(state)
        sync_timeline_for_state(state)
    return detected
