from __future__ import annotations

import json
from datetime import datetime

from pydantic import Field

from lummevia_core import (
    AgentRole,
    BusinessBrief,
    ExecutionPackage,
    ImplementationPackage,
    QualityApproval,
    TaskPackage,
    TaskPlan,
    ValidationPackage,
)
from lummevia_core.validation import CoreArtifactModel

from lummevia_agents.prompts.context import PromptContext
from lummevia_agents.schemas import AgentBaseSchema


class PromptTemplate(AgentBaseSchema):
    template_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    role: AgentRole
    target_artifact: str = Field(min_length=1)
    artifact_model: type[CoreArtifactModel]
    system_prompt: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    created_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)

    def render(self, context: PromptContext) -> str:
        artifacts_json = json.dumps(
            context.available_artifacts,
            ensure_ascii=True,
            sort_keys=True,
        )
        metadata_json = json.dumps(
            context.metadata,
            ensure_ascii=True,
            sort_keys=True,
        )
        return (
            f"Role: {self.role.value}\n"
            f"Target artifact: {self.target_artifact}\n"
            f"Project: {context.project}\n"
            f"Issue ID: {context.issue_id}\n"
            f"Instructions: {self.instructions}\n"
            f"Available artifacts: {artifacts_json}\n"
            f"Metadata: {metadata_json}\n"
            "Return a structured artifact payload."
        )


def build_default_templates() -> list[PromptTemplate]:
    return [
        PromptTemplate(
            template_id="pm_business_brief",
            version="v1",
            role=AgentRole.PM,
            target_artifact="BusinessBrief",
            artifact_model=BusinessBrief,
            system_prompt="You are the PM role in Lummevia OS.",
            instructions=(
                "Summarize the business need into a concise brief without "
                "making implementation decisions."
            ),
        ),
        PromptTemplate(
            template_id="po_execution_package",
            version="v1",
            role=AgentRole.PO,
            target_artifact="ExecutionPackage",
            artifact_model=ExecutionPackage,
            system_prompt="You are the PO role in Lummevia OS.",
            instructions=(
                "Translate the brief into a technical execution package with "
                "scope, tests, and decomposition guidance."
            ),
        ),
        PromptTemplate(
            template_id="po_task_plan",
            version="v1",
            role=AgentRole.PO,
            target_artifact="TaskPlan",
            artifact_model=TaskPlan,
            system_prompt="You are the PO role in Lummevia OS.",
            instructions=(
                "Break the execution package into a small TaskPlan with "
                "sequenced workstreams and task package identifiers."
            ),
        ),
        PromptTemplate(
            template_id="po_task_package",
            version="v1",
            role=AgentRole.PO,
            target_artifact="TaskPackage",
            artifact_model=TaskPackage,
            system_prompt="You are the PO role in Lummevia OS.",
            instructions=(
                "Produce one small TaskPackage for DEV and QA with clear "
                "constraints, acceptance criteria, and expected artifacts."
            ),
        ),
        PromptTemplate(
            template_id="dev_implementation_package",
            version="v1",
            role=AgentRole.DEV,
            target_artifact="ImplementationPackage",
            artifact_model=ImplementationPackage,
            system_prompt="You are the DEV role in Lummevia OS.",
            instructions=(
                "Describe the implementation evidence, files, tests, and "
                "residual risks for the assigned task."
            ),
        ),
        PromptTemplate(
            template_id="qa_validation_package",
            version="v1",
            role=AgentRole.QA,
            target_artifact="ValidationPackage",
            artifact_model=ValidationPackage,
            system_prompt="You are the QA role in Lummevia OS.",
            instructions=(
                "Validate acceptance criteria and edge cases, then return the "
                "testing outcome and any discovered risks."
            ),
        ),
        PromptTemplate(
            template_id="qc_quality_approval",
            version="v1",
            role=AgentRole.QC,
            target_artifact="QualityApproval",
            artifact_model=QualityApproval,
            system_prompt="You are the QC role in Lummevia OS.",
            instructions=(
                "Assess architecture, standards, and PR readiness for final "
                "technical approval."
            ),
        ),
    ]
