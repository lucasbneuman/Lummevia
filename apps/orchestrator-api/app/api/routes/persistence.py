from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core import persistence as persistence_runtime


router = APIRouter(prefix="/persistence", tags=["persistence"])


@router.get("/health")
def get_persistence_health():
    if persistence_runtime.operational_persistence is None:
        return {
            "enabled": False,
            "repositories": [],
        }
    return {
        "enabled": True,
        "repositories": [
            health.model_dump(mode="json")
            for health in persistence_runtime.operational_persistence.health()
        ],
    }


@router.post("/rehydrate")
def rehydrate_persistence():
    if persistence_runtime.operational_persistence is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operational persistence is disabled.",
        )

    results = persistence_runtime.rehydrate_registries()
    return {
        "status": "ok",
        "results": results,
    }
