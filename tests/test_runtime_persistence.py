from pathlib import Path

from lummevia_core import WorkflowRunStatus
from lummevia_runtime import DevelopmentRuntime, RuntimeState
from lummevia_runtime.persistence import (
    SqlAlchemyWorkflowRunRepository,
    create_database_engine,
    create_session_factory,
    create_tables,
)


def test_repository_save_and_get_run(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'runtime.db'}"
    engine = create_database_engine(database_url)
    create_tables(engine)
    repository = SqlAlchemyWorkflowRunRepository(create_session_factory(engine))
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-201")
    repository.save_run(state)

    recovered = repository.get_run(state.run.run_id)

    assert isinstance(recovered, RuntimeState)
    assert recovered.run.run_id == state.run.run_id
    assert recovered.run.status == WorkflowRunStatus.COMPLETED
    assert recovered.artifacts.pull_request is not None
    assert recovered.metadata["thread_id"].startswith("thread-")
    assert recovered.metadata["current_session_id"].startswith("session-")
    assert recovered.metadata["sessions"][recovered.metadata["current_session_id"]]["status"] == (
        "COMPLETED"
    )
    assert recovered.run.metadata["persistence"]["thread_id"] == recovered.metadata["thread_id"]


def test_repository_list_runs_returns_latest_first(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'runtime.db'}"
    engine = create_database_engine(database_url)
    create_tables(engine)
    repository = SqlAlchemyWorkflowRunRepository(create_session_factory(engine))
    runtime = DevelopmentRuntime()

    first = runtime.start_run(project="lummevia-os", issue_id="OS-202")
    second = runtime.start_run(project="lummevia-os", issue_id="OS-203")

    repository.save_run(first)
    repository.save_run(second)

    runs = repository.list_runs(limit=50)

    assert [run.run.issue_id for run in runs[:2]] == ["OS-203", "OS-202"]
