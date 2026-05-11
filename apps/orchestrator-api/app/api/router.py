from fastapi import APIRouter

from app.api.routes.evaluations import router as evaluations_router
from app.api.routes.model_execution import router as model_execution_router
from app.api.routes.model_router import router as model_router_api_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.runtime import router as runtime_router
from app.api.routes.system import router as system_router
from app.api.routes.workflow_runs import router as workflow_runs_router
from app.api.routes.workflows import router as workflows_router


api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(evaluations_router)
api_router.include_router(model_execution_router)
api_router.include_router(model_router_api_router)
api_router.include_router(reviews_router)
api_router.include_router(runtime_router)
api_router.include_router(workflow_runs_router)
api_router.include_router(workflows_router)
