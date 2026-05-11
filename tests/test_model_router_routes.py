from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_model_router_roles_returns_supported_roles() -> None:
    response = client.get("/model-router/roles")

    assert response.status_code == 200
    assert response.json() == {"roles": ["PM", "PO", "DEV", "QA", "QC"]}


def test_model_router_resolve_returns_pm_configuration() -> None:
    response = client.post(
        "/model-router/resolve",
        json={
            "role": "PM",
            "project": "lummevia-os",
            "environment": "development",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "role": "PM",
        "provider": "DEEPSEEK",
        "model": "deepseek-v4-strong-placeholder",
        "temperature": 0.1,
        "max_tokens": 4096,
        "source": "default",
    }


def test_model_router_resolve_returns_dev_project_configuration() -> None:
    response = client.post(
        "/model-router/resolve",
        json={
            "role": "DEV",
            "project": "lummevia-os",
            "environment": "development",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "role": "DEV",
        "provider": "DEEPSEEK",
        "model": "deepseek-v4-lite-placeholder",
        "temperature": 0.05,
        "max_tokens": 6144,
        "source": "project",
    }


def test_model_router_resolve_rejects_invalid_role() -> None:
    response = client.post(
        "/model-router/resolve",
        json={
            "role": "INVALID",
            "project": "lummevia-os",
            "environment": "development",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "role"]
