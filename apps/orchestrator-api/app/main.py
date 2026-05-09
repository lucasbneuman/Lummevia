from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import runtime as runtime_routes
from app.api.router import api_router
from app.core.config import settings
from lummevia_runtime import (
    DevelopmentRuntime,
    SqlAlchemyWorkflowRunRepository,
    create_database_engine,
    create_session_factory,
    create_tables,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if (
        settings.runtime_persistence.enabled
        and runtime_routes.runtime_repository is None
        and getattr(runtime_routes.runtime_service, "repository", None) is None
    ):
        engine = create_database_engine(settings.runtime_persistence.database_url)
        create_tables(engine)
        repository = SqlAlchemyWorkflowRunRepository(create_session_factory(engine))
        runtime_routes.runtime_repository = repository
        runtime_routes.runtime_service = DevelopmentRuntime(repository=repository)

    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)
app.include_router(api_router)
