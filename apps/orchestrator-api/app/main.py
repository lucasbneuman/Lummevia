from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import runtime as runtime_routes
from app.api.router import api_router
from app.core.config import settings
from app.core.persistence import configure_operational_persistence, rehydrate_registries
from lummevia_persistence import (
    OperationalPersistenceService,
    create_database_engine as create_operational_database_engine,
    create_session_factory as create_operational_session_factory,
    create_tables as create_operational_tables,
)
from lummevia_runtime import (
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
        operational_engine = create_operational_database_engine(
            settings.runtime_persistence.database_url
        )
        create_operational_tables(operational_engine)
        repository = SqlAlchemyWorkflowRunRepository(create_session_factory(engine))
        configure_operational_persistence(
            OperationalPersistenceService(
                create_operational_session_factory(operational_engine)
            )
        )
        rehydrate_registries()
        runtime_routes.runtime_repository = repository
        runtime_routes.runtime_service = runtime_routes._build_runtime_service()
        runtime_routes.runtime_service.repository = repository
    elif not settings.runtime_persistence.enabled:
        configure_operational_persistence(None)

    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)
app.include_router(api_router)
