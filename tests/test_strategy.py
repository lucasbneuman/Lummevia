from __future__ import annotations

from lummevia_strategy import (
    ExecutionStrategyContext,
    QALevel,
    RiskLevel,
    SandboxLevel,
    StrategyRegistry,
    StrategyType,
    evaluate_execution_strategy,
)


def test_low_risk_context_selects_safe_strategy() -> None:
    strategy = evaluate_execution_strategy(
        ExecutionStrategyContext(
            workflow_run_id="run-strategy-001",
            project="lummevia-os",
            issue_id="OS-STRAT-001",
            role="DEV",
            step_name="dev_implementation",
            files_changed_count=1,
            confidence=0.92,
            project_is_new=True,
        )
    )

    assert strategy.strategy_type == StrategyType.SAFE
    assert strategy.qa_level == QALevel.BASIC
    assert strategy.risk_level == RiskLevel.LOW


def test_repeated_qa_fail_selects_validation_heavy_strategy() -> None:
    strategy = evaluate_execution_strategy(
        ExecutionStrategyContext(
            workflow_run_id="run-strategy-002",
            project="lummevia-os",
            issue_id="OS-STRAT-002",
            role="QA",
            step_name="qa_validation",
            qa_fail_count=2,
            prior_qa_issue_count=3,
        )
    )

    assert strategy.strategy_type == StrategyType.VALIDATION_HEAVY
    assert strategy.qa_level in {QALevel.STRICT, QALevel.PARANOID}


def test_retry_escalation_selects_recovery_strategy() -> None:
    strategy = evaluate_execution_strategy(
        ExecutionStrategyContext(
            workflow_run_id="run-strategy-003",
            project="lummevia-os",
            issue_id="OS-STRAT-003",
            role="DEV",
            step_name="dev_implementation",
            retry_count=3,
            prior_failure_count=2,
        )
    )

    assert strategy.strategy_type == StrategyType.RECOVERY
    assert strategy.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}


def test_high_diff_enforces_strict_qa() -> None:
    strategy = evaluate_execution_strategy(
        ExecutionStrategyContext(
            workflow_run_id="run-strategy-004",
            project="lummevia-os",
            issue_id="OS-STRAT-004",
            role="DEV",
            step_name="dev_implementation",
            files_changed_count=12,
            confidence=0.8,
        )
    )

    assert strategy.qa_level in {QALevel.STRICT, QALevel.PARANOID}


def test_cost_pressure_selects_cost_optimized_strategy() -> None:
    strategy = evaluate_execution_strategy(
        ExecutionStrategyContext(
            workflow_run_id="run-strategy-005",
            project="lummevia-os",
            issue_id="OS-STRAT-005",
            role="PO",
            step_name="po_task_plan",
            cost_pressure_high=True,
            history_is_stable=True,
        )
    )

    assert strategy.strategy_type == StrategyType.COST_OPTIMIZED


def test_degrade_status_recommends_lite_or_fake_model() -> None:
    strategy = evaluate_execution_strategy(
        ExecutionStrategyContext(
            workflow_run_id="run-strategy-005b",
            project="lummevia-os",
            issue_id="OS-STRAT-005B",
            role="DEV",
            step_name="dev_implementation",
            metadata={"cost_control_status": "DEGRADE"},
        )
    )

    assert strategy.strategy_type == StrategyType.COST_OPTIMIZED
    assert strategy.selected_model in {"deepseek-lite", "fake-provider"}


def test_block_status_recommends_fake_provider() -> None:
    strategy = evaluate_execution_strategy(
        ExecutionStrategyContext(
            workflow_run_id="run-strategy-005c",
            project="lummevia-os",
            issue_id="OS-STRAT-005C",
            role="PM",
            step_name="pm_business_brief",
            metadata={"cost_control_status": "BLOCK"},
        )
    )

    assert strategy.strategy_type == StrategyType.COST_OPTIMIZED
    assert strategy.selected_provider == "FAKE"


def test_real_sandbox_requires_strict_sandbox_level() -> None:
    strategy = evaluate_execution_strategy(
        ExecutionStrategyContext(
            workflow_run_id="run-strategy-006",
            project="lummevia-os",
            issue_id="OS-STRAT-006",
            role="DEV",
            step_name="dev_implementation",
            sandbox_real=True,
        )
    )

    assert strategy.sandbox_level == SandboxLevel.STRICT


def test_registry_stores_and_lists_strategies() -> None:
    registry = StrategyRegistry()
    strategy = registry.create_strategy(
        evaluate_execution_strategy(
            ExecutionStrategyContext(
                workflow_run_id="run-strategy-007",
                project="lummevia-os",
                issue_id="OS-STRAT-007",
                role="PM",
                step_name="pm_business_brief",
            )
        )
    )

    assert registry.get_strategy(strategy.strategy_id) is not None
    assert registry.list_strategies(workflow_run_id="run-strategy-007")[0].strategy_id == strategy.strategy_id
