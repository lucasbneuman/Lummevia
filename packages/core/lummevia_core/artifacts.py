from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import Field

from .enums import Priority, ValidationStatus
from .validation import CoreArtifactModel


class BusinessBrief(CoreArtifactModel):
    issue_id: str
    project: str
    objective: str
    problem: str
    expected_impact: str
    priority: Priority
    constraints: list[str]
    non_goals: list[str]
    kpis: list[str]
    business_brief_status: Literal["draft", "approved"]
    founder_approved: bool


class ExecutionPackage(CoreArtifactModel):
    issue_id: str
    project: str
    technical_story: str
    acceptance_criteria: list[str]
    edge_cases: list[str]
    testing_scenarios: list[str]
    architecture_decisions: list[str]
    task_checklist: list[str]
    dev_prompts: list[str]


class ImplementationPackage(CoreArtifactModel):
    issue_id: str
    project: str
    task_id: str | None = None
    branch: str
    commits: list[str]
    files_changed: list[str]
    tests_run: list[str]
    summary: str
    risks: list[str]
    implementation_notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TaskPlan(CoreArtifactModel):
    issue_id: str
    project: str
    workstreams: list[str]
    task_packages: list[str]
    sequencing_notes: list[str]
    risks: list[str]


class TaskPackage(CoreArtifactModel):
    task_id: str
    issue_id: str
    project: str
    title: str
    description: str = "Contractual task package"
    objective: str
    target_repo: str
    context_refs: list[str]
    acceptance_criteria: list[str]
    constraints: list[str]
    prompt: str
    expected_artifacts: list[str]
    status: Literal["planned", "in_progress", "completed", "validated"]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationPackage(CoreArtifactModel):
    issue_id: str
    project: str
    task_id: str | None = None
    status: ValidationStatus
    bugs_found: list[str]
    scenarios_validated: list[str]
    feedback: str
    risks: list[str]
    findings: list[str] = Field(default_factory=list)
    recommendation: str | None = None


class QualityApproval(CoreArtifactModel):
    issue_id: str
    project: str
    status: ValidationStatus
    architecture_ok: bool
    standards_ok: bool
    pr_ok: bool
    observations: list[str]
