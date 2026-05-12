from __future__ import annotations

from typing import Any

from sqlalchemy.orm import sessionmaker

from lummevia_persistence.repositories.capabilities import CapabilitySnapshotRepository
from lummevia_persistence.repositories.conversations import ConversationSnapshotRepository
from lummevia_persistence.repositories.memory import MemorySnapshotRepository
from lummevia_persistence.repositories.planning import AdaptivePlanSnapshotRepository
from lummevia_persistence.repositories.queues import QueueSnapshotRepository
from lummevia_persistence.repositories.resources import ResourceSnapshotRepository
from lummevia_persistence.repositories.reviews import ReviewSnapshotRepository
from lummevia_persistence.repositories.sessions import SessionSnapshotRepository
from lummevia_persistence.repositories.supervisor import SupervisorSnapshotRepository
from lummevia_persistence.schemas import PersistenceHealth


class OperationalPersistenceService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self.queues = QueueSnapshotRepository(session_factory, repository_name="queues")
        self.sessions = SessionSnapshotRepository(session_factory, repository_name="sessions")
        self.supervisor = SupervisorSnapshotRepository(session_factory, repository_name="supervisor")
        self.memory = MemorySnapshotRepository(session_factory, repository_name="memory")
        self.planning = AdaptivePlanSnapshotRepository(session_factory, repository_name="planning")
        self.reviews = ReviewSnapshotRepository(session_factory, repository_name="reviews")
        self.conversations = ConversationSnapshotRepository(session_factory, repository_name="conversations")
        self.resources = ResourceSnapshotRepository(session_factory, repository_name="resources")
        self.capabilities = CapabilitySnapshotRepository(session_factory, repository_name="capabilities")

    def health(self) -> list[PersistenceHealth]:
        repositories = [
            self.queues,
            self.sessions,
            self.supervisor,
            self.memory,
            self.planning,
            self.reviews,
            self.conversations,
            self.resources,
            self.capabilities,
        ]
        return [
            PersistenceHealth(
                repository=repo.repository_name,
                status="degraded" if repo.error_count else "ok",
                last_write_at=repo.last_write_at,
                last_read_at=repo.last_read_at,
                error_count=repo.error_count,
            )
            for repo in repositories
        ]

    def snapshot_version_for(self, entity_type: str, entity_id: str) -> int | None:
        repository_by_type: dict[str, Any] = {
            "queue": self.queues,
            "session": self.sessions,
            "watchdog": self.supervisor,
            "recovery_action": self.supervisor,
            "supervisor_event": self.supervisor,
            "memory_record": self.memory,
            "adaptive_plan": self.planning,
            "review": self.reviews,
            "conversation": self.conversations,
            "resource_lock": self.resources,
            "workspace": self.resources,
            "dead_letter": self.supervisor,
            "capability_state": self.capabilities,
        }
        repository = repository_by_type.get(entity_type)
        if repository is None:
            return None
        latest = [
            snapshot
            for snapshot in repository.list_latest_snapshots(entity_type)
            if snapshot.entity_id == entity_id
        ]
        if not latest:
            return None
        return latest[-1].version
