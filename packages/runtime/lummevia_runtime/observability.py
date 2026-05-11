from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol

from lummevia_runtime.state import RuntimeState


class RuntimeObserver(Protocol):
    @contextmanager
    def observe_workflow_run(self, state: RuntimeState) -> Iterator[None]:
        yield

    @contextmanager
    def observe_step(self, state: RuntimeState, step_name: str) -> Iterator[None]:
        yield

    def record_runtime_error(
        self,
        state: RuntimeState,
        error: Exception,
        *,
        step_name: str | None = None,
    ) -> None: ...


class NoopRuntimeObserver:
    @contextmanager
    def observe_workflow_run(self, state: RuntimeState) -> Iterator[None]:
        yield

    @contextmanager
    def observe_step(self, state: RuntimeState, step_name: str) -> Iterator[None]:
        yield

    def record_runtime_error(
        self,
        state: RuntimeState,
        error: Exception,
        *,
        step_name: str | None = None,
    ) -> None:
        return None
