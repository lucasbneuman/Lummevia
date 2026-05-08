from fastapi import APIRouter

from app.core.config import settings


router = APIRouter()


@router.get("/health", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/info", tags=["system"])
def info() -> dict[str, str]:
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }
