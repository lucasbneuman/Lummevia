from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from lummevia_runtime.persistence.models import Base


def create_database_engine(database_url: str) -> Engine:
    connect_args: dict[str, object] = {}
    engine_kwargs: dict[str, object] = {
        "pool_pre_ping": True,
    }

    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

        if ":memory:" in database_url:
            engine_kwargs["poolclass"] = StaticPool

    return create_engine(
        database_url,
        connect_args=connect_args,
        **engine_kwargs,
    )


def create_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def create_tables(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)
