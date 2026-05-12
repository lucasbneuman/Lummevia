from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.persistence import annotate_runtime_state, resolve_runtime_persistence_metadata
from app.core.model_execution import build_pm_conversation_model_executor
from lummevia_agents import PMAgent
from lummevia_integrations import PhoenixClient, PhoenixRuntimeObserver
from lummevia_runtime import (
    DevelopmentRuntime,
    PersistedRunNotFoundError,
    RuntimeNotFoundError,
    RuntimeState,
)
from lummevia_runtime.persistence.repository import WorkflowRunRepository


router = APIRouter(prefix="/runtime", tags=["runtime"])


def _build_runtime_service() -> DevelopmentRuntime:
    try:
        founder_pm_agent = PMAgent(
            model_executor=build_pm_conversation_model_executor(
                deepseek=settings.deepseek,
            )
        )
    except ValueError:
        founder_pm_agent = PMAgent()

    return DevelopmentRuntime(
        observer=PhoenixRuntimeObserver(
            PhoenixClient(
                base_url=settings.phoenix.base_url,
                enabled=settings.phoenix.enabled,
                service_name=settings.app_name,
                environment=settings.app_env,
            ),
            environment=settings.app_env,
            persistence_metadata_supplier=resolve_runtime_persistence_metadata,
        ),
        founder_pm_agent=founder_pm_agent,
        persistence_metadata_resolver=resolve_runtime_persistence_metadata,
    )


runtime_service = _build_runtime_service()
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
    annotate_runtime_state(state)

    if (
        runtime_repository is not None
        and getattr(runtime_service, "repository", None) is not runtime_repository
    ):
        runtime_repository.save_run(state)

    return state


@router.get("/development/runs", response_model=list[RuntimeState])
def list_development_runs(limit: int = 50) -> list[RuntimeState]:
    if runtime_repository is not None:
        try:
            return [annotate_runtime_state(run) for run in runtime_repository.list_runs(limit=limit)]
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to list persisted runtime runs.",
            ) from exc

    return [annotate_runtime_state(run) for run in runtime_service.list_runs()]


@router.get("/development/run/{run_id}", response_model=RuntimeState)
def get_development_run(run_id: str) -> RuntimeState:
    try:
        return annotate_runtime_state(runtime_service.get_run(run_id))
    except RuntimeNotFoundError as exc:
        if runtime_repository is not None:
            try:
                return annotate_runtime_state(runtime_repository.get_run(run_id))
            except PersistedRunNotFoundError:
                pass

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
