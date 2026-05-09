from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from lummevia_integrations import PhoenixClient, PhoenixRuntimeObserver
from lummevia_runtime import (
    DevelopmentRuntime,
    PersistedRunNotFoundError,
    RuntimeNotFoundError,
    RuntimeState,
)
from lummevia_runtime.persistence.repository import WorkflowRunRepository


router = APIRouter(prefix="/runtime", tags=["runtime"])

runtime_service = DevelopmentRuntime(
    observer=PhoenixRuntimeObserver(
        PhoenixClient(
            base_url=settings.phoenix.base_url,
            enabled=settings.phoenix.enabled,
            service_name=settings.app_name,
            environment=settings.app_env,
        ),
        environment=settings.app_env,
    )
)
runtime_repository: WorkflowRunRepository | None = None


class DevelopmentRunRequest(BaseModel):
    project: str
    issue_id: str


@router.post("/development/run", response_model=RuntimeState)
def create_development_run(request: DevelopmentRunRequest) -> RuntimeState:
    state = runtime_service.start_run(
        project=request.project,
        issue_id=request.issue_id,
    )

    if (
        runtime_repository is not None
        and getattr(runtime_service, "repository", None) is not runtime_repository
    ):
        runtime_repository.save_run(state)

    return state


@router.get("/development/runs", response_model=list[RuntimeState])
def list_development_runs(limit: int = 50) -> list[RuntimeState]:
    if runtime_repository is not None:
        return runtime_repository.list_runs(limit=limit)

    return runtime_service.list_runs()


@router.get("/development/run/{run_id}", response_model=RuntimeState)
def get_development_run(run_id: str) -> RuntimeState:
    try:
        return runtime_service.get_run(run_id)
    except RuntimeNotFoundError as exc:
        if runtime_repository is not None:
            try:
                return runtime_repository.get_run(run_id)
            except PersistedRunNotFoundError:
                pass

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
