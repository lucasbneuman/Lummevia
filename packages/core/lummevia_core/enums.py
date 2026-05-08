from enum import Enum


class ArtifactStatus(str, Enum):
    DRAFT = "DRAFT"
    COMPLETED = "COMPLETED"


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ValidationStatus(str, Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"


class WorkflowRunStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Kept local to core to avoid coupling artifact contracts to model routing internals.
class AgentRole(str, Enum):
    FOUNDER = "FOUNDER"
    PM = "PM"
    PO = "PO"
    DEV = "DEV"
    QA = "QA"
    QC = "QC"
