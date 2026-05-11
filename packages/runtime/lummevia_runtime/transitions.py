from __future__ import annotations

from lummevia_core import ValidationStatus

from lummevia_runtime.state import RuntimeState


def should_reenter_dev_loop(state: RuntimeState) -> bool:
    validation_package = state.artifacts.validation_package

    if validation_package is None:
        return False

    return (
        validation_package.status == ValidationStatus.FAILED
        and state.loop_count < state.max_loop_count
    )


def get_next_step_after_qa(state: RuntimeState) -> str:
    if should_reenter_dev_loop(state):
        return "dev_qa_iteration"

    return "github_pr"
