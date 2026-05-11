from __future__ import annotations

from typing import Any

from pydantic import Field

from lummevia_core import (
    AgentRole,
    BusinessBrief,
    ExecutionPackage,
    ImplementationPackage,
    QualityApproval,
    ValidationPackage,
    WorkflowRun,
)
from lummevia_core.validation import CoreArtifactModel


class RuntimeArtifacts(CoreArtifactModel):
    business_brief: BusinessBrief | None = None
    execution_package: ExecutionPackage | None = None
    implementation_package: ImplementationPackage | None = None
    validation_package: ValidationPackage | None = None
    pull_request: dict[str, Any] | None = None
    quality_approval: QualityApproval | None = None
    final_validation: dict[str, Any] | None = None


class RuntimeState(CoreArtifactModel):
    run: WorkflowRun
    current_role: AgentRole | None = None
    artifacts: RuntimeArtifacts = Field(default_factory=RuntimeArtifacts)
    metadata: dict[str, Any] = Field(default_factory=dict)
    loop_count: int = 0
    max_loop_count: int = 1
