from __future__ import annotations

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
    branch: str
    commits: list[str]
    files_changed: list[str]
    tests_run: list[str]
    summary: str
    risks: list[str]


class ValidationPackage(CoreArtifactModel):
    issue_id: str
    project: str
    status: ValidationStatus
    bugs_found: list[str]
    scenarios_validated: list[str]
    feedback: str
    risks: list[str]


class QualityApproval(CoreArtifactModel):
    issue_id: str
    project: str
    status: ValidationStatus
    architecture_ok: bool
    standards_ok: bool
    pr_ok: bool
    observations: list[str]
