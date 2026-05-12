from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _snapshot_id() -> str:
    return f"snapshot-{uuid4()}"


class PersistenceBaseModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class PersistedSnapshot(PersistenceBaseModel):
    snapshot_id: str = Field(default_factory=_snapshot_id)
    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PersistenceHealth(PersistenceBaseModel):
    repository: str = Field(min_length=1)
    status: str = Field(min_length=1)
    last_write_at: datetime | None = None
    last_read_at: datetime | None = None
    error_count: int = Field(default=0, ge=0)
