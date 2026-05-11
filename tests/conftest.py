import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "apps" / "orchestrator-api"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


@pytest.fixture(autouse=True)
def reset_default_registries():
    from lummevia_evaluations import PromptBaselineRegistry
    from lummevia_reviews import HumanReviewRegistry

    PromptBaselineRegistry.default().reset()
    HumanReviewRegistry.default().reset()
    yield
    PromptBaselineRegistry.default().reset()
    HumanReviewRegistry.default().reset()
