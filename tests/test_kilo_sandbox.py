from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from lummevia_core import AgentRole, TaskPackage
from lummevia_kilo import (
    ControlledSubprocessExecutor,
    KiloExecutionClient,
    KiloExecutionMode,
    KiloExecutionRequest,
    KiloRuntimeSettings,
    KiloSafetyValidator,
    KiloSafetyViolation,
    KiloSubprocessResult,
)
from main import app


def _build_task_package(task_id: str = "OS-900-T1") -> TaskPackage:
    return TaskPackage(
        task_id=task_id,
        issue_id="OS-900",
        project="lummevia-os",
        title="Sandbox execution",
        objective="Validate controlled sandbox execution.",
        target_repo="lummevia-os",
        context_refs=["docs/03-workflows/loop-desarrollo.md"],
        acceptance_criteria=["Execution stays inside sandbox"],
        constraints=["Do not touch productive repos"],
        prompt="Run the sandbox task.",
        expected_artifacts=["ImplementationPackage"],
        status="planned",
    )


def _build_request(repo_path: str) -> KiloExecutionRequest:
    return KiloExecutionRequest(
        run_id="run-sandbox-001",
        role=AgentRole.DEV,
        mode=KiloExecutionMode.CODE,
        project="lummevia-os",
        repo_path=repo_path,
        task_package=_build_task_package(),
        metadata={"step_name": "sandbox_run"},
    )


def _build_settings(tmp_path: Path, **overrides) -> KiloRuntimeSettings:
    cli_path = tmp_path / "kilo-cli"
    cli_path.write_text("echo kilo", encoding="utf-8")
    workspace_root = tmp_path / "sandbox-root"
    workspace_root.mkdir()
    values = {
        "enabled": True,
        "dry_run": False,
        "cli_path": cli_path,
        "workspace_root": workspace_root,
        "default_timeout_seconds": 120,
        "allowed_repos": ("lummevia-os",),
        "max_output_bytes": 64,
    }
    values.update(overrides)
    return KiloRuntimeSettings(**values)


def test_safety_blocks_repo_not_in_allowlist(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path, allowed_repos=("sandbox-only",))
    validator = KiloSafetyValidator(settings)
    request = _build_request(repo_path=str(tmp_path / "repo"))

    result = validator.validate(request)

    assert result.allowed is False
    assert result.status == "BLOCKED"
    assert "allowlist" in (result.reason or "").lower()


def test_safety_blocks_path_traversal(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    validator = KiloSafetyValidator(settings)
    request = _build_request(repo_path="../escape")

    result = validator.validate(request)

    assert result.allowed is False
    assert result.status == "BLOCKED"
    assert "traversal" in (result.reason or "").lower()


def test_dry_run_uses_fake_execution(tmp_path: Path) -> None:
    client = KiloExecutionClient(settings=_build_settings(tmp_path, dry_run=True))

    result = client.execute(_build_request(repo_path=str(tmp_path / "repo")))

    assert result.status.value == "SUCCESS"
    assert result.metadata["real_execution"] is False
    assert result.metadata["adapter"] == "kilo_fake"
    assert result.metadata["safety_status"] == "DRY_RUN"


def test_disabled_uses_fake_execution(tmp_path: Path) -> None:
    client = KiloExecutionClient(settings=_build_settings(tmp_path, enabled=False))

    result = client.execute(_build_request(repo_path=str(tmp_path / "repo")))

    assert result.status.value == "SUCCESS"
    assert result.metadata["real_execution"] is False
    assert result.metadata["safety_status"] == "DISABLED"


def test_controlled_subprocess_executor_runs_without_shell_true(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _build_settings(tmp_path)
    request = _build_request(repo_path=str(tmp_path / "repo"))
    executor = ControlledSubprocessExecutor(settings=settings)
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            args=kwargs["args"],
            returncode=0,
            stdout="stdout-ok",
            stderr="stderr-ok",
        )

    monkeypatch.setattr("lummevia_kilo.subprocess_executor.subprocess.run", fake_run)

    result = executor.execute(request)

    assert isinstance(result, KiloSubprocessResult)
    assert result.exit_code == 0
    assert captured["kwargs"]["shell"] is False
    assert isinstance(captured["kwargs"]["args"], list)
    assert result.stdout_preview == "stdout-ok"
    assert result.stderr_preview == "stderr-ok"


def test_controlled_subprocess_executor_times_out(tmp_path: Path, monkeypatch) -> None:
    settings = _build_settings(tmp_path, default_timeout_seconds=3)
    request = _build_request(repo_path=str(tmp_path / "repo"))
    executor = ControlledSubprocessExecutor(settings=settings)

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=kwargs["args"], timeout=kwargs["timeout"])

    monkeypatch.setattr("lummevia_kilo.subprocess_executor.subprocess.run", fake_run)

    result = executor.execute(request)

    assert result.exit_code == -1
    assert result.timed_out is True
    assert "timed out" in result.stderr_preview.lower()


def test_controlled_subprocess_executor_truncates_output(tmp_path: Path, monkeypatch) -> None:
    settings = _build_settings(tmp_path, max_output_bytes=12)
    request = _build_request(repo_path=str(tmp_path / "repo"))
    executor = ControlledSubprocessExecutor(settings=settings)

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=kwargs["args"],
            returncode=0,
            stdout="1234567890ABCDEFGHIJ",
            stderr="abcdefghij1234567890",
        )

    monkeypatch.setattr("lummevia_kilo.subprocess_executor.subprocess.run", fake_run)

    result = executor.execute(request)

    assert result.stdout_bytes > len(result.stdout_preview.encode("utf-8"))
    assert result.stderr_bytes > len(result.stderr_preview.encode("utf-8"))
    assert result.stdout_preview.endswith("...")
    assert result.stderr_preview.endswith("...")


def test_metadata_marks_real_execution_when_subprocess_runs(tmp_path: Path) -> None:
    request = _build_request(repo_path=str(tmp_path / "repo"))
    settings = _build_settings(tmp_path)

    class StubExecutor:
        def execute(self, incoming_request: KiloExecutionRequest) -> KiloSubprocessResult:
            assert incoming_request.task_package.task_id == request.task_package.task_id
            assert incoming_request.metadata["execution_id"].startswith("kilo-")
            return KiloSubprocessResult(
                exit_code=0,
                stdout_preview="done",
                stderr_preview="",
                stdout_bytes=4,
                stderr_bytes=0,
                duration_ms=9,
                timed_out=False,
                command_preview="kilo --mode code --task OS-900-T1",
                workspace_path=str(settings.workspace_root / "run-sandbox-001"),
            )

    client = KiloExecutionClient(settings=settings, subprocess_executor=StubExecutor())

    result = client.execute(request)

    assert result.metadata["real_execution"] is True
    assert result.metadata["exit_code"] == 0
    assert result.metadata["stdout_preview"] == "done"
    assert result.metadata["workspace_path"]
    assert result.metadata["command_preview"].startswith("kilo")
    assert result.metadata["safety_status"] == "ALLOWED"


def test_sandbox_endpoint_fake_mode_returns_result(monkeypatch) -> None:
    from app.api.routes import kilo as kilo_routes

    client = TestClient(app)
    monkeypatch.setattr(
        kilo_routes,
        "sandbox_client",
        KiloExecutionClient(
            settings=KiloRuntimeSettings(
                enabled=False,
                dry_run=True,
                cli_path=None,
                workspace_root=None,
                default_timeout_seconds=120,
                allowed_repos=(),
                max_output_bytes=1024,
            )
        ),
    )

    response = client.post(
        "/kilo/sandbox/run",
        json={
            "project": "lummevia-os",
            "repo_path": "C:/sandbox/lummevia-os",
            "task_id": "OS-900-T1",
            "prompt": "Run fake sandbox validation.",
            "mode": "CODE",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["real_execution"] is False
    assert body["metadata"]["safety_status"] in {"DISABLED", "DRY_RUN"}
    assert body["status"] == "SUCCESS"


def test_safety_validator_raises_on_explicit_enforcement(tmp_path: Path) -> None:
    settings = _build_settings(tmp_path, enabled=False)
    validator = KiloSafetyValidator(settings)

    try:
        validator.ensure_allowed(_build_request(repo_path=str(tmp_path / "repo")))
    except KiloSafetyViolation as exc:
        assert exc.result.status == "DISABLED"
    else:
        raise AssertionError("Expected disabled execution to be blocked.")
