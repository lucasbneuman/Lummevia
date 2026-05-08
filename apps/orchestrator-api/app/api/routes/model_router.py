from fastapi import APIRouter, HTTPException, status

from model_router import (
    AgentRole,
    InvalidEnvironmentOverrideError,
    ModelRouterError,
    RoutingRequest,
    RoutingResolution,
    UnknownRoleError,
    resolve_model,
)


router = APIRouter(prefix="/model-router", tags=["model-router"])


@router.get("/roles")
def list_supported_roles() -> dict[str, list[str]]:
    return {"roles": [role.value for role in AgentRole]}


@router.post(
    "/resolve",
    response_model=RoutingResolution,
    response_model_exclude={"project", "environment"},
)
def resolve_model_route(request: RoutingRequest) -> RoutingResolution:
    try:
        return resolve_model(request)
    except UnknownRoleError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidEnvironmentOverrideError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ModelRouterError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
