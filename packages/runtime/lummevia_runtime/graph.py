from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from functools import partial
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from lummevia_core import WorkflowRun, WorkflowRunStatus
from lummevia_agents import DevAgent, PMAgent, POAgent, QAAgent, QCAgent
from lummevia_kilo import KiloExecutionClient

from lummevia_runtime.exceptions import RuntimeNotFoundError
from lummevia_runtime.economics import initialize_economics_runtime_state
from lummevia_runtime.intelligence import initialize_intelligence_runtime_state
from lummevia_runtime.learning import (
    analyze_learning_for_runtime,
    initialize_learning_runtime_state,
)
from lummevia_runtime.observability import NoopRuntimeObserver, RuntimeObserver
from lummevia_runtime.planning import initialize_adaptive_planning_runtime_state
from lummevia_runtime.persistence.repository import WorkflowRunRepository
from lummevia_runtime.strategy import initialize_strategy_runtime_state
from lummevia_runtime.supervisor import initialize_supervisor_runtime_state
from lummevia_runtime.nodes import (
    dev_implementation_node,
    dev_qa_iteration_node,
    founder_business_approval_node,
    founder_input_node,
    founder_pm_conversation_node,
    github_pr_node,
    pm_business_brief_node,
    po_execution_package_node,
    po_final_validation_node,
    po_task_packages_node,
    po_task_plan_node,
    qa_validation_node,
    qc_quality_approval_node,
)
from lummevia_runtime.state import RuntimeState
from lummevia_runtime.transitions import get_next_step_after_qa


logger = logging.getLogger(__name__)
DEFAULT_REPO_PATH = str(Path(__file__).resolve().parents[3])


class RuntimeRegistry:
    def __init__(self) -> None:
        self._runs: dict[str, RuntimeState] = {}

    def create(self, run_state: RuntimeState) -> RuntimeState:
        self._runs[run_state.run.run_id] = run_state
        return run_state

    def upsert(self, run_state: RuntimeState) -> RuntimeState:
        self._runs[run_state.run.run_id] = run_state
        return run_state

    def get(self, run_id: str) -> RuntimeState:
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise RuntimeNotFoundError(f"Runtime run '{run_id}' not found.") from exc

    def list_active(self) -> list[RuntimeState]:
        return [
            run_state
            for run_state in self._runs.values()
            if run_state.run.status in {
                WorkflowRunStatus.CREATED,
                WorkflowRunStatus.RUNNING,
                WorkflowRunStatus.WAITING,
            }
        ]


class DevelopmentRuntime:
    def __init__(
        self,
        registry: RuntimeRegistry | None = None,
        repository: WorkflowRunRepository | None = None,
        observer: RuntimeObserver | None = None,
        kilo_client: KiloExecutionClient | None = None,
        founder_pm_agent: PMAgent | None = None,
        persistence_metadata_resolver: Callable[[RuntimeState], dict[str, object]] | None = None,
        context_loader: Callable[..., dict | None] | None = None,
        artifact_publisher: Callable[[str, str, dict], None] | None = None,
    ) -> None:
        self.registry = registry or RuntimeRegistry()
        self.repository = repository
        self.observer = observer or NoopRuntimeObserver()
        self.kilo_client = kilo_client or KiloExecutionClient()
        self.persistence_metadata_resolver = persistence_metadata_resolver
        self.graph = build_development_graph(
            observer=self.observer,
            kilo_client=self.kilo_client,
            founder_pm_agent=founder_pm_agent,
            pm_agent=PMAgent(),
            po_agent=POAgent(),
            dev_agent=DevAgent(),
            qa_agent=QAAgent(),
            qc_agent=QCAgent(),
            context_loader=context_loader,
            artifact_publisher=artifact_publisher,
        )

    def start_run(
        self,
        project: str,
        issue_id: str,
        *,
        initial_metadata: dict[str, object] | None = None,
    ) -> RuntimeState:
        from lummevia_runtime.queue import sync_task_queue_state

        runtime_metadata = {
            "workflow": "development_loop",
            "repo_path": DEFAULT_REPO_PATH,
        }
        if initial_metadata is not None:
            runtime_metadata.update(initial_metadata)
        initial_state = RuntimeState(
            run=WorkflowRun(
                workflow_name="development_loop",
                project=project,
                issue_id=issue_id,
                status=WorkflowRunStatus.CREATED,
                current_step=None,
                events=[],
                metadata=initial_metadata or {},
            ),
            metadata=runtime_metadata,
        )
        initialize_supervisor_runtime_state(initial_state)
        initialize_strategy_runtime_state(initial_state)
        initialize_economics_runtime_state(initial_state)
        initialize_intelligence_runtime_state(initial_state)
        initialize_adaptive_planning_runtime_state(initial_state)
        initialize_learning_runtime_state(initial_state)
        if self.persistence_metadata_resolver is not None:
            initial_state.metadata.update(self.persistence_metadata_resolver(initial_state))
        self.registry.create(initial_state)
        with _observe_workflow_run(self.observer, initial_state):
            final_state = RuntimeState.model_validate(self.graph.invoke(initial_state))
            if final_state.run.status == WorkflowRunStatus.COMPLETED:
                queue_id = str(final_state.metadata.get("queue_id", "")).strip()
                queue_item_id = str(final_state.metadata.get("current_queue_item_id", "")).strip()
                if queue_id and queue_item_id:
                    from lummevia_queue import TaskQueueRegistry

                    queue = TaskQueueRegistry.default().get_queue(queue_id)
                    if queue is not None:
                        current_item = next(
                            (
                                item
                                for item in queue.items
                                if item.queue_item_id == queue_item_id
                            ),
                            None,
                        )
                        if current_item is not None and current_item.status != "COMPLETED":
                            TaskQueueRegistry.default().mark_completed(queue_id, queue_item_id)
            sync_task_queue_state(final_state)
            analyze_learning_for_runtime(final_state)
            initial_state.run = final_state.run
            initial_state.current_role = final_state.current_role
            initial_state.artifacts = final_state.artifacts
            initial_state.kilo_executions = final_state.kilo_executions
            initial_state.metadata = final_state.metadata
            initial_state.loop_count = final_state.loop_count
            initial_state.max_loop_count = final_state.max_loop_count
            if self.persistence_metadata_resolver is not None:
                initial_state.metadata.update(self.persistence_metadata_resolver(initial_state))
        self.registry.upsert(final_state)

        if self.repository is not None:
            self.repository.save_run(final_state)
        if self.persistence_metadata_resolver is not None:
            final_state.metadata.update(self.persistence_metadata_resolver(final_state))

        return final_state

    def get_run(self, run_id: str) -> RuntimeState:
        return self.registry.get(run_id)

    def list_runs(self) -> list[RuntimeState]:
        return self.registry.list_active()


def build_development_graph(
    observer: RuntimeObserver | None = None,
    *,
    founder_pm_agent: PMAgent | None = None,
    pm_agent: PMAgent | None = None,
    po_agent: POAgent | None = None,
    dev_agent: DevAgent | None = None,
    qa_agent: QAAgent | None = None,
    qc_agent: QCAgent | None = None,
    kilo_client: KiloExecutionClient | None = None,
    context_loader: Callable[..., dict | None] | None = None,
    artifact_publisher: Callable[[str, str, dict], None] | None = None,
):
    runtime_observer = observer or NoopRuntimeObserver()
    founder_pm_agent = founder_pm_agent or PMAgent()
    pm_agent = pm_agent or PMAgent()
    po_agent = po_agent or POAgent()
    dev_agent = dev_agent or DevAgent()
    qa_agent = qa_agent or QAAgent()
    qc_agent = qc_agent or QCAgent()
    kilo_client = kilo_client or KiloExecutionClient()
    graph = StateGraph(RuntimeState)
    graph.add_node(
        "founder_input",
        _instrument_node(runtime_observer, "founder_input", founder_input_node),
    )
    graph.add_node(
        "pm_business_brief",
        _instrument_node(
            runtime_observer,
            "pm_business_brief",
            partial(
                pm_business_brief_node,
                agent=pm_agent,
                context_loader=context_loader,
                artifact_publisher=artifact_publisher,
            ),
        ),
    )
    graph.add_node(
        "founder_pm_conversation",
        _instrument_node(
            runtime_observer,
            "founder_pm_conversation",
            partial(
                founder_pm_conversation_node,
                agent=founder_pm_agent,
                artifact_publisher=artifact_publisher,
            ),
        ),
    )
    graph.add_node(
        "founder_business_approval",
        _instrument_node(
            runtime_observer,
            "founder_business_approval",
            partial(
                founder_business_approval_node,
                artifact_publisher=artifact_publisher,
            ),
        ),
    )
    graph.add_node(
        "po_execution_package",
        _instrument_node(
            runtime_observer,
            "po_execution_package",
            partial(
                po_execution_package_node,
                agent=po_agent,
                context_loader=context_loader,
                artifact_publisher=artifact_publisher,
            ),
        ),
    )
    graph.add_node(
        "po_task_plan",
        _instrument_node(
            runtime_observer,
            "po_task_plan",
            partial(
                po_task_plan_node,
                agent=po_agent,
                kilo_client=kilo_client,
                artifact_publisher=artifact_publisher,
            ),
        ),
    )
    graph.add_node(
        "po_task_packages",
        _instrument_node(
            runtime_observer,
            "po_task_packages",
            partial(
                po_task_packages_node,
                agent=po_agent,
                kilo_client=kilo_client,
                context_loader=context_loader,
                artifact_publisher=artifact_publisher,
            ),
        ),
    )
    graph.add_node(
        "dev_implementation",
        _instrument_node(
            runtime_observer,
            "dev_implementation",
            partial(
                dev_implementation_node,
                agent=dev_agent,
                kilo_client=kilo_client,
                artifact_publisher=artifact_publisher,
            ),
        ),
    )
    graph.add_node(
        "qa_validation",
        _instrument_node(
            runtime_observer,
            "qa_validation",
            partial(
                qa_validation_node,
                agent=qa_agent,
                kilo_client=kilo_client,
                artifact_publisher=artifact_publisher,
            ),
        ),
    )
    graph.add_node(
        "dev_qa_iteration",
        _instrument_node(runtime_observer, "dev_qa_iteration", dev_qa_iteration_node),
    )
    graph.add_node(
        "github_pr",
        _instrument_node(
            runtime_observer,
            "github_pr",
            partial(github_pr_node, artifact_publisher=artifact_publisher),
        ),
    )
    graph.add_node(
        "qc_quality_approval",
        _instrument_node(
            runtime_observer,
            "qc_quality_approval",
            partial(
                qc_quality_approval_node,
                agent=qc_agent,
                artifact_publisher=artifact_publisher,
            ),
        ),
    )
    graph.add_node(
        "po_final_validation",
        _instrument_node(
            runtime_observer,
            "po_final_validation",
            partial(
                po_final_validation_node,
                artifact_publisher=artifact_publisher,
            ),
        ),
    )

    graph.add_edge(START, "founder_input")
    graph.add_edge("founder_input", "founder_pm_conversation")
    graph.add_edge("founder_pm_conversation", "pm_business_brief")
    graph.add_edge("pm_business_brief", "founder_business_approval")
    graph.add_edge("founder_business_approval", "po_execution_package")
    graph.add_edge("po_execution_package", "po_task_plan")
    graph.add_edge("po_task_plan", "po_task_packages")
    graph.add_edge("po_task_packages", "dev_implementation")
    graph.add_edge("dev_implementation", "qa_validation")
    graph.add_conditional_edges(
        "qa_validation",
        get_next_step_after_qa,
        {
            "dev_qa_iteration": "dev_qa_iteration",
            "github_pr": "github_pr",
        },
    )
    graph.add_edge("dev_qa_iteration", "dev_implementation")
    graph.add_edge("github_pr", "qc_quality_approval")
    graph.add_edge("qc_quality_approval", "po_final_validation")
    graph.add_edge("po_final_validation", END)
    return graph.compile()


def _instrument_node(
    observer: RuntimeObserver,
    step_name: str,
    node: Callable[[RuntimeState], RuntimeState],
) -> Callable[[RuntimeState], RuntimeState]:
    def instrumented_node(state: RuntimeState) -> RuntimeState:
        with _observe_step(observer, state, step_name):
            return node(state)

    return instrumented_node


class _ObserverContext(AbstractContextManager[None]):
    def __init__(
        self,
        observer: RuntimeObserver,
        state: RuntimeState,
        *,
        step_name: str | None = None,
        kind: str,
    ) -> None:
        self._observer = observer
        self._state = state
        self._step_name = step_name
        self._kind = kind
        self._context: AbstractContextManager[None] | None = None

    def __enter__(self) -> None:
        try:
            if self._step_name is None:
                self._context = self._observer.observe_workflow_run(self._state)
            else:
                self._context = self._observer.observe_step(self._state, self._step_name)
            self._context.__enter__()
        except Exception:
            self._context = None
            logger.exception(
                "Runtime %s instrumentation failed to start for run '%s'%s.",
                self._kind,
                self._state.run.run_id,
                (
                    ""
                    if self._step_name is None
                    else f" at step '{self._step_name}'"
                ),
            )
        return None

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if exc is not None:
            _record_runtime_error(
                self._observer,
                self._state,
                exc,
                step_name=self._step_name,
            )

        if self._context is not None:
            try:
                self._context.__exit__(exc_type, exc, traceback)
            except Exception:
                logger.exception(
                    "Runtime %s instrumentation failed to finish for run '%s'%s.",
                    self._kind,
                    self._state.run.run_id,
                    (
                        ""
                        if self._step_name is None
                        else f" at step '{self._step_name}'"
                    ),
                )
        return False


def _observe_workflow_run(
    observer: RuntimeObserver,
    state: RuntimeState,
) -> _ObserverContext:
    return _ObserverContext(observer, state, kind="workflow")


def _observe_step(
    observer: RuntimeObserver,
    state: RuntimeState,
    step_name: str,
) -> _ObserverContext:
    return _ObserverContext(
        observer,
        state,
        step_name=step_name,
        kind="step",
    )


def _record_runtime_error(
    observer: RuntimeObserver,
    state: RuntimeState,
    error: Exception,
    *,
    step_name: str | None = None,
) -> None:
    try:
        observer.record_runtime_error(state, error, step_name=step_name)
    except Exception:
        logger.exception(
            "Runtime error instrumentation failed for run '%s'%s.",
            state.run.run_id,
            "" if step_name is None else f" at step '{step_name}'",
        )
