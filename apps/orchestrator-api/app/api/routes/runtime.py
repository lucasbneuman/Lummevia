from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from lummevia_runtime import DevelopmentRuntime, RuntimeNotFoundError, RuntimeState


router = APIRouter(prefix="/runtime", tags=["runtime"])

runtime_service = DevelopmentRuntime()


class DevelopmentRunRequest(BaseModel):
    project: str
    issue_id: str


@router.post("/development/run", response_model=RuntimeState)
def create_development_run(request: DevelopmentRunRequest) -> RuntimeState:
    return runtime_service.start_run(
        project=request.project,
        issue_id=request.issue_id,
    )


@router.get("/development/run/{run_id}", response_model=RuntimeState)
def get_development_run(run_id: str) -> RuntimeState:
    try:
        return runtime_service.get_run(run_id)
    except RuntimeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
