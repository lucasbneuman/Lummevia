import os
import sys
from pathlib import Path

import pytest

for _env_var in (
    "MODEL_PM",
    "MODEL_DEV",
    "MODEL_QA",
    "MODEL_PO",
    "MODEL_QC",
    "MODEL_PM_NAME",
    "MODEL_PM_PROVIDER",
    "MODEL_PM_TEMPERATURE",
    "MODEL_PM_MAX_TOKENS",
    "MODEL_PO_NAME",
    "MODEL_PO_PROVIDER",
    "MODEL_PO_TEMPERATURE",
    "MODEL_PO_MAX_TOKENS",
    "MODEL_DEV_NAME",
    "MODEL_DEV_PROVIDER",
    "MODEL_DEV_TEMPERATURE",
    "MODEL_DEV_MAX_TOKENS",
    "MODEL_QA_NAME",
    "MODEL_QA_PROVIDER",
    "MODEL_QA_TEMPERATURE",
    "MODEL_QA_MAX_TOKENS",
    "MODEL_QC_NAME",
    "MODEL_QC_PROVIDER",
    "MODEL_QC_TEMPERATURE",
    "MODEL_QC_MAX_TOKENS",
):
    os.environ.setdefault(_env_var, "")

os.environ.setdefault("PHOENIX_ENABLED", "false")
os.environ.setdefault("DEEPSEEK_ENABLED", "false")

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "apps" / "orchestrator-api"
CONVERSATIONS_PACKAGE_DIR = ROOT_DIR / "packages" / "conversations"
MEMORY_PACKAGE_DIR = ROOT_DIR / "packages" / "memory"
SESSIONS_PACKAGE_DIR = ROOT_DIR / "packages" / "sessions"
TIMELINE_PACKAGE_DIR = ROOT_DIR / "packages" / "timeline"
QUEUE_PACKAGE_DIR = ROOT_DIR / "packages" / "queue"
RESOURCES_PACKAGE_DIR = ROOT_DIR / "packages" / "resources"
CAPABILITIES_PACKAGE_DIR = ROOT_DIR / "packages" / "capabilities"
SUPERVISOR_PACKAGE_DIR = ROOT_DIR / "packages" / "supervisor"
PERSISTENCE_PACKAGE_DIR = ROOT_DIR / "packages" / "persistence"
CODE_CHANGES_PACKAGE_DIR = ROOT_DIR / "packages" / "code-changes"
INTELLIGENCE_PACKAGE_DIR = ROOT_DIR / "packages" / "intelligence"
PLANNING_PACKAGE_DIR = ROOT_DIR / "packages" / "planning"
STRATEGY_PACKAGE_DIR = ROOT_DIR / "packages" / "strategy"
ECONOMICS_PACKAGE_DIR = ROOT_DIR / "packages" / "economics"
LEARNING_PACKAGE_DIR = ROOT_DIR / "packages" / "learning"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(CONVERSATIONS_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(CONVERSATIONS_PACKAGE_DIR))
if str(MEMORY_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(MEMORY_PACKAGE_DIR))
if str(SESSIONS_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(SESSIONS_PACKAGE_DIR))
if str(TIMELINE_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(TIMELINE_PACKAGE_DIR))
if str(QUEUE_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(QUEUE_PACKAGE_DIR))
if str(RESOURCES_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(RESOURCES_PACKAGE_DIR))
if str(CAPABILITIES_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(CAPABILITIES_PACKAGE_DIR))
if str(SUPERVISOR_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(SUPERVISOR_PACKAGE_DIR))
if str(PERSISTENCE_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PERSISTENCE_PACKAGE_DIR))
if str(CODE_CHANGES_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_CHANGES_PACKAGE_DIR))
if str(INTELLIGENCE_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(INTELLIGENCE_PACKAGE_DIR))
if str(PLANNING_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PLANNING_PACKAGE_DIR))
if str(STRATEGY_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(STRATEGY_PACKAGE_DIR))
if str(ECONOMICS_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(ECONOMICS_PACKAGE_DIR))
if str(LEARNING_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(LEARNING_PACKAGE_DIR))


@pytest.fixture(autouse=True)
def reset_default_registries():
    from lummevia_conversations import ConversationRegistry
    from lummevia_evaluations import PromptBaselineRegistry
    from lummevia_intelligence import DecisionRegistry
    from lummevia_learning import LearningRegistry
    from lummevia_memory import ProjectMemoryRegistry
    from lummevia_planning import AdaptivePlanRegistry
    from lummevia_queue import TaskQueueRegistry
    from lummevia_capabilities import CapabilityRegistry
    from lummevia_code_changes import CodeChangeRegistry
    from lummevia_core import ApprovedProjectHandoffRegistry
    from lummevia_economics import EconomicsRegistry
    from lummevia_resources import ResourceRegistry
    from lummevia_reviews import HumanReviewRegistry
    from lummevia_sessions import SessionRegistry
    from lummevia_strategy import StrategyRegistry
    from lummevia_supervisor import SupervisorRegistry
    from lummevia_timeline import TimelineRegistry
    from app.core.persistence import configure_operational_persistence
    from app.core.youtrack import set_youtrack_client_override
    from app.api.routes import runtime as runtime_routes
    from app.api.routes.telegram import clear_pending_telegram_starts

    configure_operational_persistence(None)
    set_youtrack_client_override(None)
    clear_pending_telegram_starts()
    runtime_routes.runtime_service = runtime_routes._build_runtime_service()
    runtime_routes.runtime_repository = None
    runtime_routes._published_runtime_updates.clear()
    ConversationRegistry.default().reset()
    ApprovedProjectHandoffRegistry.default().reset()
    PromptBaselineRegistry.default().reset()
    ProjectMemoryRegistry.default().reset()
    DecisionRegistry.default().reset()
    AdaptivePlanRegistry.default().reset()
    TaskQueueRegistry.default().reset()
    CapabilityRegistry.default().reset()
    CodeChangeRegistry.default().reset()
    EconomicsRegistry.default().reset()
    LearningRegistry.default().reset()
    ResourceRegistry.default().reset()
    HumanReviewRegistry.default().reset()
    SessionRegistry.default().reset()
    StrategyRegistry.default().reset()
    SupervisorRegistry.default().reset()
    TimelineRegistry.default().reset()
    yield
    configure_operational_persistence(None)
    set_youtrack_client_override(None)
    clear_pending_telegram_starts()
    runtime_routes.runtime_service = runtime_routes._build_runtime_service()
    runtime_routes.runtime_repository = None
    runtime_routes._published_runtime_updates.clear()
    ConversationRegistry.default().reset()
    ApprovedProjectHandoffRegistry.default().reset()
    PromptBaselineRegistry.default().reset()
    ProjectMemoryRegistry.default().reset()
    DecisionRegistry.default().reset()
    AdaptivePlanRegistry.default().reset()
    TaskQueueRegistry.default().reset()
    CapabilityRegistry.default().reset()
    CodeChangeRegistry.default().reset()
    EconomicsRegistry.default().reset()
    LearningRegistry.default().reset()
    ResourceRegistry.default().reset()
    HumanReviewRegistry.default().reset()
    SessionRegistry.default().reset()
    StrategyRegistry.default().reset()
    SupervisorRegistry.default().reset()
    TimelineRegistry.default().reset()
