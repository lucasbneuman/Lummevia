from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.persistence import annotate_runtime_state, resolve_runtime_persistence_metadata
from app.core.model_execution import build_pm_conversation_model_executor
from app.core.youtrack import load_agent_context_bundle, summarize_artifact_for_youtrack, sync_issue_comment
from lummevia_agents import PMAgent
from lummevia_integrations import PhoenixClient, PhoenixRuntimeObserver
from lummevia_kilo import KiloExecutionClient, KiloRuntimeSettings
from lummevia_runtime import (
    DevelopmentRuntime,
    PersistedRunNotFoundError,
    RuntimeNotFoundError,
    RuntimeState,
)
from lummevia_runtime.persistence.repository import WorkflowRunRepository


router = APIRouter(prefix="/runtime", tags=["runtime"])
_published_runtime_updates: set[tuple[str, str, str | None]] = set()


def _publish_runtime_artifact(issue_id: str, artifact_type: str, payload: dict) -> None:
    task_id = str(payload.get("task_id")) if payload.get("task_id") is not None else None
    milestone_type = {
        "TaskPackageCollection": "DECOMPOSITION_CREATED",
        "TaskCompleted": "TASK_COMPLETED",
        "ValidationPackage": "QA_STATUS",
        "WorkflowCompleted": "WORKFLOW_COMPLETED",
    }.get(artifact_type)
    if milestone_type is None:
        return
    if artifact_type == "ValidationPackage" and payload.get("status") != "PASSED":
        milestone_type = "QA_STATUS"
    dedupe_key = (issue_id, milestone_type, task_id)
    if dedupe_key in _published_runtime_updates:
        return
    _published_runtime_updates.add(dedupe_key)
    sync_issue_comment(
        issue_id,
        summarize_artifact_for_youtrack(artifact_type=artifact_type, payload=payload),
    )


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
        kilo_client=KiloExecutionClient(settings=_build_kilo_runtime_settings()),
        founder_pm_agent=founder_pm_agent,
        persistence_metadata_resolver=resolve_runtime_persistence_metadata,
        context_loader=load_agent_context_bundle,
        artifact_publisher=_publish_runtime_artifact,
    )


def _build_kilo_runtime_settings() -> KiloRuntimeSettings:
    return KiloRuntimeSettings(
        enabled=settings.kilo.enabled,
        dry_run=settings.kilo.dry_run,
        cli_path=settings.kilo.cli_path,
        workspace_root=settings.kilo.workspace_root,
        default_timeout_seconds=settings.kilo.default_timeout_seconds,
        allowed_repos=settings.kilo.allowed_repos,
        max_output_bytes=settings.kilo.max_output_bytes,
    )


runtime_service = _build_runtime_service()
runtime_repository: WorkflowRunRepository | None = None


class DevelopmentRunRequest(BaseModel):
    project: str
    issue_id: str
    founder_input_summary: str | None = None
    conversation_thread_id: str | None = None
    handoff_id: str | None = None
    thread_id: str | None = None
    brief_version: int | None = None
    approved_brief: dict[str, object] | None = None


@router.post("/development/run", response_model=RuntimeState)
def create_development_run(request: DevelopmentRunRequest) -> RuntimeState:
    initial_metadata: dict[str, object] = {}
    if request.founder_input_summary is not None:
        initial_metadata["founder_input"] = {
            "summary": request.founder_input_summary,
            "project": request.project,
        }
    if request.conversation_thread_id is not None:
        initial_metadata["conversation_thread_id"] = request.conversation_thread_id
    if request.thread_id is not None:
        initial_metadata["thread_id"] = request.thread_id
    if request.handoff_id is not None:
        initial_metadata["handoff_id"] = request.handoff_id
    if request.brief_version is not None:
        initial_metadata["brief_version"] = request.brief_version
    if request.approved_brief is not None:
        initial_metadata["approved_brief"] = request.approved_brief
    state = runtime_service.start_run(
        project=request.project,
        issue_id=request.issue_id,
        initial_metadata=initial_metadata or None,
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
