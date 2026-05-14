from __future__ import annotations

from lummevia_strategy.heuristics import build_reasoning, resolve_strategy_event
from lummevia_strategy.policies import (
    DEFAULT_HIGH_DIFF_THRESHOLD,
    DEFAULT_LOW_CONFIDENCE_THRESHOLD,
    DEFAULT_RECOVERY_RETRY_THRESHOLD,
)
from lummevia_strategy.schemas import (
    AutonomyLevel,
    ExecutionStrategy,
    ExecutionStrategyContext,
    QALevel,
    RiskLevel,
    SandboxLevel,
    StrategyType,
)


def evaluate_execution_strategy(context: ExecutionStrategyContext) -> ExecutionStrategy:
    strategy_type = StrategyType.BALANCED
    qa_level = QALevel.STANDARD
    sandbox_level = SandboxLevel.BASIC
    risk_level = RiskLevel.MEDIUM
    autonomy_level = AutonomyLevel.ASSISTED
    retry_policy = "standard_retry"
    reasons: list[str] = []
    cost_control_status = str(context.metadata.get("cost_control_status", "")).upper()

    if context.project_is_new:
        strategy_type = StrategyType.SAFE
        qa_level = QALevel.BASIC
        risk_level = RiskLevel.LOW
        autonomy_level = AutonomyLevel.MANUAL
        reasons.append("New project contexts default to SAFE for traceable rollout.")

    if context.history_is_stable and strategy_type == StrategyType.BALANCED:
        reasons.append("Stable history supports BALANCED execution.")

    if context.files_changed_count <= 2:
        strategy_type = StrategyType.SAFE
        qa_level = QALevel.BASIC
        risk_level = RiskLevel.LOW
        autonomy_level = AutonomyLevel.MANUAL
        reasons.append("Small changes default to SAFE with basic QA.")

    if context.files_changed_count >= DEFAULT_HIGH_DIFF_THRESHOLD:
        strategy_type = StrategyType.VALIDATION_HEAVY
        qa_level = QALevel.STRICT
        risk_level = RiskLevel.HIGH
        autonomy_level = AutonomyLevel.MANUAL
        retry_policy = "validation_heavy_retry"
        reasons.append("Large diffs require validation-heavy handling and strict QA.")

    if context.qa_fail_count >= 2 or context.prior_qa_issue_count >= 2:
        strategy_type = StrategyType.VALIDATION_HEAVY
        qa_level = QALevel.PARANOID if context.prior_qa_issue_count >= 3 else QALevel.STRICT
        risk_level = RiskLevel.HIGH
        autonomy_level = AutonomyLevel.MANUAL
        retry_policy = "qa_recheck_retry"
        reasons.append("Repeated QA failures tighten QA depth before more execution.")

    if context.retry_count >= DEFAULT_RECOVERY_RETRY_THRESHOLD or context.prior_failure_count >= 2:
        strategy_type = StrategyType.RECOVERY
        qa_level = QALevel.STRICT
        risk_level = RiskLevel.HIGH
        autonomy_level = AutonomyLevel.MANUAL
        retry_policy = "recovery_retry"
        reasons.append("High retry pressure moves execution into recovery mode.")

    if context.confidence is not None and context.confidence < DEFAULT_LOW_CONFIDENCE_THRESHOLD:
        strategy_type = StrategyType.SAFE
        qa_level = max_qa_level(qa_level, QALevel.STANDARD)
        risk_level = max_risk_level(risk_level, RiskLevel.MEDIUM)
        autonomy_level = AutonomyLevel.MANUAL
        reasons.append("Low confidence forces SAFE handling.")

    if context.dead_letter_risk or context.prior_dead_letter_count > 0:
        strategy_type = StrategyType.RECOVERY
        qa_level = QALevel.PARANOID
        risk_level = RiskLevel.CRITICAL
        autonomy_level = AutonomyLevel.MANUAL
        retry_policy = "dead_letter_guard"
        reasons.append("Dead-letter risk escalates the strategy to CRITICAL recovery.")

    if context.sandbox_real:
        sandbox_level = SandboxLevel.STRICT
        risk_level = max_risk_level(risk_level, RiskLevel.HIGH)
        reasons.append("Real sandbox execution requires strict sandbox policy.")
    elif context.execution_layer == "KILO":
        sandbox_level = SandboxLevel.ISOLATED
        reasons.append("Kilo execution stays isolated even in fake mode.")

    if context.cost_pressure_high and not context.dead_letter_risk and context.retry_count == 0:
        strategy_type = StrategyType.COST_OPTIMIZED
        qa_level = min_qa_level(qa_level, QALevel.STANDARD)
        risk_level = min_risk_level(risk_level, RiskLevel.MEDIUM)
        autonomy_level = AutonomyLevel.ASSISTED
        retry_policy = "cost_optimized_retry"
        reasons.append("High cost pressure prefers a cost-optimized recommendation.")

    if cost_control_status == "WARN" and not context.dead_letter_risk:
        strategy_type = StrategyType.COST_OPTIMIZED
        qa_level = min_qa_level(qa_level, QALevel.STANDARD)
        risk_level = min_risk_level(risk_level, RiskLevel.MEDIUM)
        autonomy_level = AutonomyLevel.ASSISTED
        retry_policy = "cost_warning_retry"
        reasons.append("Budget warning pressure recommends COST_OPTIMIZED execution.")

    if cost_control_status == "DEGRADE" and not context.dead_letter_risk:
        strategy_type = StrategyType.COST_OPTIMIZED
        qa_level = min_qa_level(qa_level, QALevel.STANDARD)
        risk_level = min_risk_level(risk_level, RiskLevel.MEDIUM)
        autonomy_level = AutonomyLevel.ASSISTED
        retry_policy = "cost_degrade_retry"
        reasons.append("Cost degradation pressure recommends lite or fake model profiles.")

    if cost_control_status == "BLOCK":
        strategy_type = StrategyType.COST_OPTIMIZED
        qa_level = min_qa_level(qa_level, QALevel.STANDARD)
        risk_level = max_risk_level(risk_level, RiskLevel.MEDIUM)
        autonomy_level = AutonomyLevel.MANUAL
        retry_policy = "cost_block_retry"
        reasons.append("Budget block recommends avoiding real-provider execution.")

    if (
        context.history_is_stable
        and not context.project_is_new
        and context.confidence is not None
        and context.confidence >= 0.95
        and context.retry_count == 0
        and context.qa_fail_count == 0
        and context.files_changed_count <= 1
        and not context.cost_pressure_high
    ):
        strategy_type = StrategyType.AGGRESSIVE
        qa_level = QALevel.STANDARD
        risk_level = RiskLevel.MEDIUM
        autonomy_level = AutonomyLevel.SUPERVISED
        reasons.append("Very stable and high-confidence contexts can be recommended as AGGRESSIVE.")

    if not reasons:
        reasons.append("No high-risk heuristic fired, so BALANCED remains the default.")

    selected_provider, selected_model = _resolve_model_recommendation(
        context=context,
        strategy_type=strategy_type,
    )
    execution_mode = _resolve_execution_mode(context)
    strategy_event = resolve_strategy_event(
        context=context,
        strategy_type=strategy_type,
        risk_level=risk_level,
        qa_level=qa_level,
        sandbox_level=sandbox_level,
    )

    return ExecutionStrategy(
        workflow_run_id=context.workflow_run_id,
        session_id=context.session_id,
        strategy_type=strategy_type,
        autonomy_level=autonomy_level,
        selected_model=selected_model,
        selected_provider=selected_provider,
        execution_mode=execution_mode,
        qa_level=qa_level,
        sandbox_level=sandbox_level,
        retry_policy=retry_policy,
        risk_level=risk_level,
        reasoning=build_reasoning(reasons),
        metadata={
            "project": context.project,
            "issue_id": context.issue_id,
            "role": context.role,
            "step_name": context.step_name,
            "task_id": context.task_id,
            "workflow_state": context.workflow_state,
            "execution_layer": context.execution_layer,
            "files_changed_count": context.files_changed_count,
            "retry_count": context.retry_count,
            "qa_fail_count": context.qa_fail_count,
            "prior_failure_count": context.prior_failure_count,
            "prior_qa_issue_count": context.prior_qa_issue_count,
            "prior_review_count": context.prior_review_count,
            "prior_dead_letter_count": context.prior_dead_letter_count,
            "confidence": context.confidence,
            "project_is_new": context.project_is_new,
            "history_is_stable": context.history_is_stable,
            "sandbox_real": context.sandbox_real,
            "sandbox_target": "real" if context.sandbox_real else "fake",
            "cost_pressure_high": context.cost_pressure_high,
            "cost_control_status": cost_control_status or None,
            "cost_recommendation": context.metadata.get("cost_recommendation"),
            "dead_letter_risk": context.dead_letter_risk,
            "strategy_event": strategy_event,
            "previous_strategy_type": (
                context.previous_strategy_type.value
                if context.previous_strategy_type is not None
                else None
            ),
            "previous_risk_level": (
                context.previous_risk_level.value
                if context.previous_risk_level is not None
                else None
            ),
            **context.metadata,
        },
    )


def max_risk_level(first: RiskLevel, second: RiskLevel) -> RiskLevel:
    order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
    return order[max(order.index(first), order.index(second))]


def min_risk_level(first: RiskLevel, second: RiskLevel) -> RiskLevel:
    order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
    return order[min(order.index(first), order.index(second))]


def max_qa_level(first: QALevel, second: QALevel) -> QALevel:
    order = [QALevel.BASIC, QALevel.STANDARD, QALevel.STRICT, QALevel.PARANOID]
    return order[max(order.index(first), order.index(second))]


def min_qa_level(first: QALevel, second: QALevel) -> QALevel:
    order = [QALevel.BASIC, QALevel.STANDARD, QALevel.STRICT, QALevel.PARANOID]
    return order[min(order.index(first), order.index(second))]


def _resolve_model_recommendation(
    *,
    context: ExecutionStrategyContext,
    strategy_type: StrategyType,
) -> tuple[str, str]:
    cost_control_status = str(context.metadata.get("cost_control_status", "")).upper()
    if cost_control_status == "BLOCK":
        return "FAKE", "fake-provider"
    if cost_control_status == "DEGRADE":
        if context.role in {"PM", "PO", "QC"}:
            return "DEEPSEEK", "deepseek-lite"
        return "FAKE", "fake-provider"
    if context.execution_layer == "KILO" and not context.sandbox_real:
        return "FAKE", "fake-sandbox"
    if bool(context.metadata.get("simulation_only", False)):
        return "FAKE", "fake-provider"
    if strategy_type == StrategyType.COST_OPTIMIZED:
        return "DEEPSEEK", "deepseek-lite"
    if context.role in {"PM", "PO", "QC"} and strategy_type != StrategyType.COST_OPTIMIZED:
        return "DEEPSEEK", "deepseek-strong"
    return "DEEPSEEK", "deepseek-lite"


def _resolve_execution_mode(context: ExecutionStrategyContext) -> str:
    if context.execution_mode:
        return context.execution_mode
    if context.execution_layer == "KILO":
        return "KILO_SEQUENTIAL"
    if context.role == "PM":
        return "PM_ITERATION"
    if context.role == "PO":
        return "PO_STRUCTURED"
    if context.role == "QA":
        return "VALIDATION"
    return "SEQUENTIAL"
