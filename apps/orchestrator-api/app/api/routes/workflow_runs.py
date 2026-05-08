from pydantic import BaseModel
from fastapi import APIRouter

from lummevia_core import WorkflowRun, WorkflowRunStatus


router = APIRouter(prefix="/workflow-runs", tags=["workflow-runs"])


class MockWorkflowRunRequest(BaseModel):
    workflow_name: str
    project: str
    issue_id: str


@router.post("/mock", response_model=WorkflowRun)
def create_mock_workflow_run(request: MockWorkflowRunRequest) -> WorkflowRun:
    return WorkflowRun(
        workflow_name=request.workflow_name,
        project=request.project,
        issue_id=request.issue_id,
        status=WorkflowRunStatus.CREATED,
        current_step=None,
        events=[],
        metadata={"diagnostic": True, "mock": True},
    )
