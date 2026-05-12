from __future__ import annotations

from pathlib import Path

from lummevia_code_changes import (
    CodeArtifact,
    CodeChangeRegistry,
    CodeChangeStatus,
    capture_workspace_snapshot,
    compare_workspace_snapshots,
    create_artifact_from_file,
)


def test_snapshot_diff_detects_new_file(tmp_path: Path) -> None:
    before = capture_workspace_snapshot(tmp_path)
    created = tmp_path / "src" / "new_file.py"
    created.parent.mkdir(parents=True, exist_ok=True)
    created.write_text("print('hello')\n", encoding="utf-8")

    after = capture_workspace_snapshot(tmp_path)
    result = compare_workspace_snapshots(before=before, after=after)

    assert len(result.files_changed) == 1
    assert result.files_changed[0].path.endswith("src/new_file.py")
    assert result.files_changed[0].change_type == "ADDED"
    assert result.files_changed[0].lines_added >= 1
    assert result.lines_added >= 1


def test_diff_ignores_git_and_node_modules(tmp_path: Path) -> None:
    ignored_git = tmp_path / ".git" / "config"
    ignored_modules = tmp_path / "node_modules" / "lib.js"
    ignored_git.parent.mkdir(parents=True, exist_ok=True)
    ignored_modules.parent.mkdir(parents=True, exist_ok=True)
    ignored_git.write_text("secret\n", encoding="utf-8")
    ignored_modules.write_text("ignored\n", encoding="utf-8")

    snapshot = capture_workspace_snapshot(tmp_path)

    assert snapshot.files == {}


def test_checksum_is_stable_for_same_file(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.txt"
    artifact_path.write_text("stable-content\n", encoding="utf-8")

    first = create_artifact_from_file(artifact_path, artifact_type="sandbox_output")
    second = create_artifact_from_file(artifact_path, artifact_type="sandbox_output")

    assert first.checksum == second.checksum
    assert first.size_bytes == second.size_bytes


def test_change_set_registry_create_list_get_and_update() -> None:
    registry = CodeChangeRegistry()
    change_set = registry.create_change_set(
        execution_id="kilo-001",
        session_id="session-001",
        task_id="OS-910-T1",
        project="lummevia-os",
        repo="lummevia-os",
        workspace_id="workspace-001",
        files_changed=[],
        diff_summary={"files_changed_count": 0, "lines_added": 0, "lines_removed": 0},
        artifacts=[],
        metadata={"run_id": "run-001"},
    )

    artifact = CodeArtifact(
        artifact_type="validation_snapshot",
        path="/tmp/report.json",
        checksum="abc123",
        size_bytes=32,
        metadata={"simulated": True},
    )
    registry.add_artifact(change_set.change_set_id, artifact)
    registry.update_status(
        change_set.change_set_id,
        status=CodeChangeStatus.VALIDATED,
        metadata={"validation_status": "PASSED"},
    )

    recovered = registry.get_change_set(change_set.change_set_id)

    assert recovered is not None
    assert recovered.status == CodeChangeStatus.VALIDATED
    assert recovered.metadata["validation_status"] == "PASSED"
    assert recovered.artifacts[0].artifact_type == "validation_snapshot"
    assert registry.list_change_sets()[0].change_set_id == change_set.change_set_id
