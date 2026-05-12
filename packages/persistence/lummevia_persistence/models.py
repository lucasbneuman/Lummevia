from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class OperationalSnapshotRecord(Base):
    __tablename__ = "operational_snapshots"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "version", name="uq_operational_snapshot_version"),
    )

    snapshot_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    snapshot_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False, default=dict)
