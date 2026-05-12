import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "apps" / "orchestrator-api"
CONVERSATIONS_PACKAGE_DIR = ROOT_DIR / "packages" / "conversations"
SESSIONS_PACKAGE_DIR = ROOT_DIR / "packages" / "sessions"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(CONVERSATIONS_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(CONVERSATIONS_PACKAGE_DIR))
if str(SESSIONS_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(SESSIONS_PACKAGE_DIR))


@pytest.fixture(autouse=True)
def reset_default_registries():
    from lummevia_conversations import ConversationRegistry
    from lummevia_evaluations import PromptBaselineRegistry
    from lummevia_reviews import HumanReviewRegistry
    from lummevia_sessions import SessionRegistry

    ConversationRegistry.default().reset()
    PromptBaselineRegistry.default().reset()
    HumanReviewRegistry.default().reset()
    SessionRegistry.default().reset()
    yield
    ConversationRegistry.default().reset()
    PromptBaselineRegistry.default().reset()
    HumanReviewRegistry.default().reset()
    SessionRegistry.default().reset()
