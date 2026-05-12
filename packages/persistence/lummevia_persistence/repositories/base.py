from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from lummevia_persistence.models import OperationalSnapshotRecord
from lummevia_persistence.schemas import PersistedSnapshot


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SnapshotRepository:
    def __init__(self, session_factory: sessionmaker, *, repository_name: str) -> None:
        self._session_factory = session_factory
        self.repository_name = repository_name
        self._last_write_at: datetime | None = None
        self._last_read_at: datetime | None = None
        self._error_count = 0

    @property
    def last_write_at(self) -> datetime | None:
        return self._last_write_at

    @property
    def last_read_at(self) -> datetime | None:
        return self._last_read_at

    @property
    def error_count(self) -> int:
        return self._error_count

    def _track_write(self) -> None:
        self._last_write_at = utcnow()

    def _track_read(self) -> None:
        self._last_read_at = utcnow()

    def _track_error(self) -> None:
        self._error_count += 1

    def save_snapshot(
        self,
        *,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> PersistedSnapshot:
        try:
            with self._session_factory() as session:
                current_version = (
                    session.query(func.max(OperationalSnapshotRecord.version))
                    .filter(
                        OperationalSnapshotRecord.entity_type == entity_type,
                        OperationalSnapshotRecord.entity_id == entity_id,
                    )
                    .scalar()
                )
                version = int(current_version or 0) + 1
                snapshot = PersistedSnapshot(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    version=version,
                    payload=payload,
                    metadata=metadata or {},
                )
                session.add(
                    OperationalSnapshotRecord(
                        snapshot_id=snapshot.snapshot_id,
                        entity_type=snapshot.entity_type,
                        entity_id=snapshot.entity_id,
                        version=snapshot.version,
                        created_at=snapshot.created_at,
                        payload=snapshot.payload,
                        snapshot_metadata=snapshot.metadata,
                    )
                )
                session.commit()
            self._track_write()
            return snapshot
        except Exception:
            self._track_error()
            raise

    def list_latest_snapshots(self, entity_type: str) -> list[PersistedSnapshot]:
        try:
            with self._session_factory() as session:
                records = session.query(OperationalSnapshotRecord).filter(
                    OperationalSnapshotRecord.entity_type == entity_type
                ).all()
            self._track_read()
        except Exception:
            self._track_error()
            raise

        latest_by_entity: dict[str, PersistedSnapshot] = {}
        for record in records:
            snapshot = PersistedSnapshot(
                snapshot_id=record.snapshot_id,
                entity_type=record.entity_type,
                entity_id=record.entity_id,
                version=record.version,
                created_at=record.created_at,
                payload=dict(record.payload),
                metadata=dict(record.snapshot_metadata),
            )
            existing = latest_by_entity.get(snapshot.entity_id)
            if existing is None or snapshot.version > existing.version:
                latest_by_entity[snapshot.entity_id] = snapshot

        return sorted(
            latest_by_entity.values(),
            key=lambda item: (item.created_at, item.snapshot_id),
        )
