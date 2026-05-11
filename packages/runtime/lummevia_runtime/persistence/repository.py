from __future__ import annotations

import logging
from typing import Protocol

from pydantic import ValidationError
from sqlalchemy.orm import sessionmaker

from lummevia_runtime.persistence.exceptions import PersistedRunNotFoundError
from lummevia_runtime.persistence.models import WorkflowRunRecord
from lummevia_runtime.state import RuntimeState


logger = logging.getLogger(__name__)


class WorkflowRunRepository(Protocol):
    def save_run(self, state: RuntimeState) -> RuntimeState: ...

    def get_run(self, run_id: str) -> RuntimeState: ...

    def list_runs(self, limit: int = 50) -> list[RuntimeState]: ...


class SqlAlchemyWorkflowRunRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def save_run(self, state: RuntimeState) -> RuntimeState:
        payload = state.model_dump(mode="json")

        with self._session_factory() as session:
            record = session.get(WorkflowRunRecord, state.run.run_id)

            if record is None:
                record = WorkflowRunRecord(
                    run_id=state.run.run_id,
                    workflow_name=state.run.workflow_name,
                    project=state.run.project,
                    issue_id=state.run.issue_id,
                    status=state.run.status.value,
                    current_step=state.run.current_step,
                    payload=payload,
                )
                session.add(record)
            else:
                record.workflow_name = state.run.workflow_name
                record.project = state.run.project
                record.issue_id = state.run.issue_id
                record.status = state.run.status.value
                record.current_step = state.run.current_step
                record.payload = payload

            session.commit()

        return state

    def get_run(self, run_id: str) -> RuntimeState:
        with self._session_factory() as session:
            record = session.get(WorkflowRunRecord, run_id)

            if record is None:
                raise PersistedRunNotFoundError(
                    f"Persisted runtime run '{run_id}' not found."
                )

            try:
                return RuntimeState.model_validate(record.payload)
            except ValidationError as exc:
                raise PersistedRunNotFoundError(
                    f"Persisted runtime run '{run_id}' could not be hydrated."
                ) from exc

    def list_runs(self, limit: int = 50) -> list[RuntimeState]:
        with self._session_factory() as session:
            records = (
                session.query(WorkflowRunRecord)
                .order_by(WorkflowRunRecord.updated_at.desc())
                .limit(limit)
                .all()
            )

            hydrated_runs: list[RuntimeState] = []

            for record in records:
                try:
                    hydrated_runs.append(RuntimeState.model_validate(record.payload))
                except ValidationError as exc:
                    logger.warning(
                        "Skipping incompatible persisted workflow run '%s': %s",
                        record.run_id,
                        exc,
                    )

            return hydrated_runs
