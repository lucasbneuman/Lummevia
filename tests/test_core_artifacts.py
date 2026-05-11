import json

import pytest
from pydantic import ValidationError

from lummevia_core import (
    AgentRole,
    ArtifactStatus,
    BusinessBrief,
    ExecutionPackage,
    ImplementationPackage,
    Priority,
    QualityApproval,
    TaskPackage,
    TaskPlan,
    ValidationPackage,
    ValidationStatus,
    WorkflowRun,
    WorkflowRunEvent,
    WorkflowRunStatus,
)


def test_business_brief_accepts_valid_payload() -> None:
    artifact = BusinessBrief(
        issue_id="LUM-101",
        project="lummevia-os",
        objective="Reduce manual triage time",
        problem="Briefs arrive with inconsistent structure",
        expected_impact="Faster handoff from PM to PO",
        priority=Priority.HIGH,
        constraints=["No external integrations"],
        non_goals=["Implement runtime agents"],
        kpis=["Triage time under 10 minutes"],
        business_brief_status="draft",
        founder_approved=False,
    )

    assert artifact.issue_id == "LUM-101"
    assert artifact.priority == Priority.HIGH
    assert artifact.business_brief_status == "draft"
    assert artifact.founder_approved is False


def test_execution_package_accepts_valid_payload() -> None:
    artifact = ExecutionPackage(
        issue_id="LUM-102",
        project="lummevia-os",
        technical_story="Model core workflow artifacts as shared contracts",
        acceptance_criteria=["Artifacts can be instantiated"],
        edge_cases=["Missing required fields raise validation errors"],
        testing_scenarios=["Serialize each artifact to JSON"],
        architecture_decisions=["Keep schemas independent from router"],
        task_checklist=["Create models", "Create tests"],
        dev_prompts=["Implement Pydantic models"],
    )

    assert artifact.project == "lummevia-os"
    assert artifact.task_checklist == ["Create models", "Create tests"]


def test_implementation_package_accepts_valid_payload() -> None:
    artifact = ImplementationPackage(
        issue_id="LUM-103",
        project="lummevia-os",
        branch="feature/core-artifacts",
        commits=["abc1234"],
        files_changed=["packages/core/lummevia_core/artifacts.py"],
        tests_run=["pytest tests/test_core_artifacts.py"],
        summary="Implemented artifact schemas",
        risks=["Future integration contract may evolve"],
    )

    assert artifact.branch == "feature/core-artifacts"
    assert artifact.commits == ["abc1234"]


def test_task_plan_accepts_valid_payload() -> None:
    artifact = TaskPlan(
        issue_id="LUM-103A",
        project="lummevia-os",
        workstreams=["runtime", "docs"],
        task_packages=["TASK-1", "TASK-2"],
        sequencing_notes=["Start with runtime scaffolding"],
        risks=["Fake pipeline may drift from future real behavior"],
    )

    assert artifact.workstreams == ["runtime", "docs"]
    assert artifact.task_packages == ["TASK-1", "TASK-2"]


def test_task_package_accepts_valid_payload() -> None:
    artifact = TaskPackage(
        task_id="TASK-1",
        issue_id="LUM-103B",
        project="lummevia-os",
        title="Add PO task decomposition state",
        objective="Represent PO phases in runtime state",
        target_repo="lummevia-os",
        context_refs=["docs/03-workflows/loop-desarrollo.md"],
        acceptance_criteria=["Runtime stores task packages"],
        constraints=["Keep runtime sequential"],
        prompt="Implement the first task package only.",
        expected_artifacts=["TaskPlan", "TaskPackage"],
        status="planned",
    )

    assert artifact.task_id == "TASK-1"
    assert artifact.status == "planned"


def test_validation_package_accepts_valid_payload() -> None:
    artifact = ValidationPackage(
        issue_id="LUM-104",
        project="lummevia-os",
        status=ValidationStatus.PASSED,
        bugs_found=[],
        scenarios_validated=["BusinessBrief serialization"],
        feedback="Validation completed successfully",
        risks=[],
    )

    assert artifact.status == ValidationStatus.PASSED
    assert artifact.bugs_found == []


def test_quality_approval_accepts_valid_payload() -> None:
    artifact = QualityApproval(
        issue_id="LUM-105",
        project="lummevia-os",
        status=ValidationStatus.PASSED,
        architecture_ok=True,
        standards_ok=True,
        pr_ok=True,
        observations=["Aligned with documented workflow"],
    )

    assert artifact.pr_ok is True
    assert artifact.observations == ["Aligned with documented workflow"]


def test_workflow_run_event_accepts_valid_payload() -> None:
    event = WorkflowRunEvent(
        event_id="evt-001",
        step_name="founder_input",
        status=WorkflowRunStatus.CREATED,
        message="Workflow run created for diagnostic purposes.",
        metadata={"source": "mock-endpoint"},
    )

    assert event.step_name == "founder_input"
    assert event.status == WorkflowRunStatus.CREATED


def test_workflow_run_accepts_valid_payload() -> None:
    run = WorkflowRun(
        run_id="run-001",
        workflow_name="development",
        project="lummevia-os",
        issue_id="OS-1",
        status=WorkflowRunStatus.CREATED,
        current_step="founder_input",
        events=[
            WorkflowRunEvent(
                event_id="evt-001",
                step_name="founder_input",
                status=WorkflowRunStatus.CREATED,
                message="Workflow run created for diagnostic purposes.",
                metadata={"source": "mock-endpoint"},
            )
        ],
        metadata={"diagnostic": True},
    )

    assert run.workflow_name == "development"
    assert run.events[0].event_id == "evt-001"


@pytest.mark.parametrize(
    ("artifact_cls", "payload"),
    [
        (
            BusinessBrief,
            {
                "project": "lummevia-os",
                "objective": "Objective",
                "problem": "Problem",
                "expected_impact": "Impact",
                "priority": Priority.MEDIUM,
                "constraints": [],
                "non_goals": [],
                "kpis": [],
                "business_brief_status": "draft",
                "founder_approved": False,
            },
        ),
        (
            ExecutionPackage,
            {
                "project": "lummevia-os",
                "technical_story": "Story",
                "acceptance_criteria": [],
                "edge_cases": [],
                "testing_scenarios": [],
                "architecture_decisions": [],
                "task_checklist": [],
                "dev_prompts": [],
            },
        ),
        (
            ImplementationPackage,
            {
                "project": "lummevia-os",
                "branch": "feature/test",
                "commits": [],
                "files_changed": [],
                "tests_run": [],
                "summary": "Summary",
                "risks": [],
            },
        ),
        (
            TaskPlan,
            {
                "project": "lummevia-os",
                "workstreams": [],
                "task_packages": [],
                "sequencing_notes": [],
                "risks": [],
            },
        ),
        (
            TaskPackage,
            {
                "task_id": "TASK-REQ",
                "project": "lummevia-os",
                "title": "Title",
                "objective": "Objective",
                "target_repo": "lummevia-os",
                "context_refs": [],
                "acceptance_criteria": [],
                "constraints": [],
                "prompt": "Prompt",
                "expected_artifacts": [],
                "status": "planned",
            },
        ),
        (
            ValidationPackage,
            {
                "project": "lummevia-os",
                "status": ValidationStatus.PENDING,
                "bugs_found": [],
                "scenarios_validated": [],
                "feedback": "Pending validation",
                "risks": [],
            },
        ),
        (
            QualityApproval,
            {
                "project": "lummevia-os",
                "status": ValidationStatus.PENDING,
                "architecture_ok": False,
                "standards_ok": False,
                "pr_ok": False,
                "observations": [],
            },
        ),
    ],
)
def test_artifacts_require_issue_id(artifact_cls, payload) -> None:
    with pytest.raises(ValidationError):
        artifact_cls(**payload)


def test_business_brief_rejects_invalid_priority() -> None:
    with pytest.raises(ValidationError):
        BusinessBrief(
            issue_id="LUM-106",
            project="lummevia-os",
            objective="Objective",
            problem="Problem",
            expected_impact="Impact",
            priority="URGENT",
            constraints=[],
            non_goals=[],
            kpis=[],
            business_brief_status="draft",
            founder_approved=False,
        )


def test_business_brief_rejects_invalid_approval_status() -> None:
    with pytest.raises(ValidationError):
        BusinessBrief(
            issue_id="LUM-106A",
            project="lummevia-os",
            objective="Objective",
            problem="Problem",
            expected_impact="Impact",
            priority=Priority.HIGH,
            constraints=[],
            non_goals=[],
            kpis=[],
            business_brief_status="submitted",
            founder_approved=False,
        )


def test_validation_package_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        ValidationPackage(
            issue_id="LUM-107",
            project="lummevia-os",
            status="DONE",
            bugs_found=[],
            scenarios_validated=[],
            feedback="Feedback",
            risks=[],
        )


def test_workflow_run_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        WorkflowRun(
            run_id="run-002",
            workflow_name="development",
            project="lummevia-os",
            issue_id="OS-2",
            status="DONE",
            current_step=None,
            events=[],
            metadata={},
        )


def test_artifact_status_rejects_invalid_value() -> None:
    with pytest.raises(ValueError):
        ArtifactStatus("ARCHIVED")


def test_agent_role_rejects_invalid_value() -> None:
    with pytest.raises(ValueError):
        AgentRole("INVALID")


def test_agent_role_accepts_founder_value() -> None:
    assert AgentRole("FOUNDER") == AgentRole.FOUNDER


def test_models_export_to_dict_and_json() -> None:
    artifact = QualityApproval(
        issue_id="LUM-108",
        project="lummevia-os",
        status=ValidationStatus.PASSED,
        architecture_ok=True,
        standards_ok=True,
        pr_ok=True,
        observations=["Ready for final PO review"],
    )

    exported = artifact.model_dump(mode="json")
    exported_json = artifact.model_dump_json()

    assert exported["status"] == "PASSED"
    assert json.loads(exported_json)["status"] == "PASSED"


def test_workflow_run_exports_to_dict_and_json() -> None:
    run = WorkflowRun(
        run_id="run-003",
        workflow_name="development",
        project="lummevia-os",
        issue_id="OS-3",
        status=WorkflowRunStatus.CREATED,
        current_step=None,
        events=[],
        metadata={"diagnostic": True},
    )

    exported = run.model_dump(mode="json")
    exported_json = run.model_dump_json()

    assert exported["status"] == "CREATED"
    assert json.loads(exported_json)["workflow_name"] == "development"
