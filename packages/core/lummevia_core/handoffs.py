from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import uuid4

from pydantic import Field

from lummevia_core.validation import CoreArtifactModel


def _handoff_id() -> str:
    return f"handoff-{uuid4()}"


class ApprovedProjectHandoff(CoreArtifactModel):
    handoff_id: str = Field(default_factory=_handoff_id)
    thread_id: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    approved_brief: dict[str, Any] = Field(default_factory=dict)
    brief_version: int = Field(ge=0)
    founder_summary: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovedProjectHandoffRegistry:
    _default_instance: ClassVar["ApprovedProjectHandoffRegistry" | None] = None

    def __init__(self) -> None:
        self._handoffs: dict[str, ApprovedProjectHandoff] = {}
        self._persistence = None

    @classmethod
    def default(cls) -> "ApprovedProjectHandoffRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._handoffs.clear()

    def configure_persistence(self, persistence) -> None:
        self._persistence = persistence

    def rehydrate(self, handoffs: list[ApprovedProjectHandoff]) -> None:
        self._handoffs = {handoff.handoff_id: handoff for handoff in handoffs}

    def save_handoff(self, handoff: ApprovedProjectHandoff) -> ApprovedProjectHandoff:
        self._handoffs[handoff.handoff_id] = handoff
        self._persist_handoff(handoff)
        return handoff

    def get_handoff(self, handoff_id: str) -> ApprovedProjectHandoff | None:
        return self._handoffs.get(handoff_id)

    def list_handoffs(self, *, project: str | None = None) -> list[ApprovedProjectHandoff]:
        handoffs = list(self._handoffs.values())
        if project is not None:
            handoffs = [handoff for handoff in handoffs if handoff.project == project]
        return sorted(
            handoffs,
            key=lambda handoff: (handoff.created_at, handoff.handoff_id),
            reverse=True,
        )

    def find_by_thread_version(
        self,
        *,
        thread_id: str,
        brief_version: int,
    ) -> ApprovedProjectHandoff | None:
        for handoff in self._handoffs.values():
            if handoff.thread_id == thread_id and handoff.brief_version == brief_version:
                return handoff
        return None

    def _persist_handoff(self, handoff: ApprovedProjectHandoff) -> None:
        if self._persistence is None:
            return
        try:
            self._persistence.save_handoff(handoff)
        except Exception:
            return
