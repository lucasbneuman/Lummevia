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


@pytest.fixture(autouse=True)
def reset_default_registries():
    from lummevia_conversations import ConversationRegistry
    from lummevia_evaluations import PromptBaselineRegistry
    from lummevia_memory import ProjectMemoryRegistry
    from lummevia_queue import TaskQueueRegistry
    from lummevia_reviews import HumanReviewRegistry
    from lummevia_sessions import SessionRegistry
    from lummevia_timeline import TimelineRegistry

    ConversationRegistry.default().reset()
    PromptBaselineRegistry.default().reset()
    ProjectMemoryRegistry.default().reset()
    TaskQueueRegistry.default().reset()
    HumanReviewRegistry.default().reset()
    SessionRegistry.default().reset()
    TimelineRegistry.default().reset()
    yield
    ConversationRegistry.default().reset()
    PromptBaselineRegistry.default().reset()
    ProjectMemoryRegistry.default().reset()
    TaskQueueRegistry.default().reset()
    HumanReviewRegistry.default().reset()
    SessionRegistry.default().reset()
    TimelineRegistry.default().reset()
