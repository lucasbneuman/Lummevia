from __future__ import annotations

from collections.abc import Callable

from lummevia_core import AgentRole

from lummevia_runtime.events import complete_step, start_step
from lummevia_runtime.state import RuntimeState


def github_pr_node(
    state: RuntimeState,
    *,
    artifact_publisher: Callable[[str, str, dict], None] | None = None,
) -> RuntimeState:
    step_name = "github_pr"
    state = start_step(state, step_name=step_name, role=AgentRole.DEV)

    implementation_package = state.artifacts.implementation_package
    branch = (
        implementation_package.branch
        if implementation_package is not None
        else f"runtime/{state.run.issue_id.lower()}"
    )
    pr_number = 1000 + state.loop_count + 1
    state.artifacts.pull_request = {
        "pr_number": pr_number,
        "branch": branch,
        "url": f"https://github.com/lummevia/{state.run.project}/pull/{pr_number}",
        "status": "OPEN",
    }
    state.metadata["pull_request_created"] = True
    if artifact_publisher is not None:
        artifact_publisher(
            state.run.issue_id,
            "PullRequest",
            state.artifacts.pull_request,
        )
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.DEV,
        metadata={"artifact": "PullRequest", "pr_number": pr_number},
    )
