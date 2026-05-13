from __future__ import annotations

from fastapi.testclient import TestClient

from lummevia_strategy import StrategyRegistry
from main import app


client = TestClient(app)


def test_strategy_endpoints_list_get_and_evaluate() -> None:
    runtime_response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-STRAT-301"},
    )
    assert runtime_response.status_code == 200
    strategy_id = runtime_response.json()["metadata"]["strategy_id"]

    list_response = client.get("/strategy")
    assert list_response.status_code == 200
    assert any(strategy["strategy_id"] == strategy_id for strategy in list_response.json())

    get_response = client.get(f"/strategy/{strategy_id}")
    assert get_response.status_code == 200
    assert get_response.json()["strategy_id"] == strategy_id

    before = len(StrategyRegistry.default().list_strategies())
    evaluate_response = client.post(
        "/strategy/evaluate",
        json={
            "workflow_run_id": "run-strategy-eval",
            "project": "lummevia-os",
            "issue_id": "OS-STRAT-EVAL",
            "role": "QA",
            "step_name": "qa_validation",
            "qa_fail_count": 2,
        },
    )
    after = len(StrategyRegistry.default().list_strategies())

    assert evaluate_response.status_code == 200
    assert evaluate_response.json()["strategy_type"] == "VALIDATION_HEAVY"
    assert before == after
