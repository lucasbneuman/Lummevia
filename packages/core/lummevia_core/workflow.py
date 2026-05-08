from __future__ import annotations

from pydantic import Field

from lummevia_core.enums import AgentRole
from lummevia_core.validation import CoreArtifactModel
from lummevia_core.workflow_steps import WorkflowStep


class WorkflowDefinition(CoreArtifactModel):
    name: str
    description: str
    steps: list[WorkflowStep] = Field(default_factory=list)


class DevelopmentWorkflowDefinition(WorkflowDefinition):
    name: str = "development_loop"
    description: str = (
        "Contractual skeleton for the main Lummevia OS development workflow."
    )
    steps: list[WorkflowStep] = Field(
        default_factory=lambda: [
            WorkflowStep(
                name="founder_input",
                responsible_role=AgentRole.FOUNDER,
                consumes=["founder_intent"],
                produces=["founder_input"],
                description=(
                    "Capture founder intent as the initial handoff that PM uses "
                    "to produce the BusinessBrief."
                ),
            ),
            WorkflowStep(
                name="pm_business_brief",
                responsible_role=AgentRole.PM,
                consumes=["founder_input"],
                produces=["BusinessBrief"],
                description="Transform founder input into a BusinessBrief.",
            ),
            WorkflowStep(
                name="po_execution_package",
                responsible_role=AgentRole.PO,
                consumes=["BusinessBrief"],
                produces=["ExecutionPackage"],
                description="Translate the BusinessBrief into an ExecutionPackage.",
            ),
            WorkflowStep(
                name="dev_implementation",
                responsible_role=AgentRole.DEV,
                consumes=["ExecutionPackage"],
                produces=["ImplementationPackage"],
                description=(
                    "Implement the assigned technical work and produce an "
                    "ImplementationPackage."
                ),
            ),
            WorkflowStep(
                name="qa_validation",
                responsible_role=AgentRole.QA,
                consumes=["ImplementationPackage"],
                produces=["ValidationPackage"],
                description=(
                    "Validate behavior, acceptance criteria, and edge cases for "
                    "the implementation."
                ),
            ),
            WorkflowStep(
                name="dev_qa_iteration",
                responsible_role=AgentRole.QA,
                consumes=["ImplementationPackage", "ValidationPackage"],
                produces=["ValidationPackage"],
                description=(
                    "Represent the explicit DEV-QA iteration loop until the "
                    "implementation is validated."
                ),
            ),
            WorkflowStep(
                name="github_pr",
                responsible_role=AgentRole.DEV,
                consumes=["ImplementationPackage"],
                produces=["PullRequest"],
                description="Publish the implementation evidence as a GitHub pull request.",
            ),
            WorkflowStep(
                name="qc_quality_approval",
                responsible_role=AgentRole.QC,
                consumes=["PullRequest", "ValidationPackage", "ExecutionPackage"],
                produces=["QualityApproval"],
                description=(
                    "Review the pull request for architectural and technical "
                    "quality before final validation."
                ),
            ),
            WorkflowStep(
                name="po_final_validation",
                responsible_role=AgentRole.PO,
                consumes=["PullRequest", "ValidationPackage", "QualityApproval"],
                produces=["final_validation"],
                description=(
                    "Perform the final functional validation before merge or closure."
                ),
            ),
        ]
    )
