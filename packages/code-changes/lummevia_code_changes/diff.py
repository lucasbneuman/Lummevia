from __future__ import annotations

import difflib
from pathlib import Path

from lummevia_code_changes.schemas import (
    ChangedFile,
    FileSnapshot,
    WorkspaceDiffResult,
    WorkspaceSnapshot,
    checksum_for_bytes,
)


IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    ".venv",
    "__pycache__",
    "dist",
    "build",
}
DEFAULT_MAX_FILE_BYTES = 1024 * 1024


def capture_workspace_snapshot(
    workspace_path: str | Path,
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> WorkspaceSnapshot:
    root = Path(workspace_path)
    files: dict[str, FileSnapshot] = {}
    if not root.exists():
        return WorkspaceSnapshot(root_path=str(root.resolve(strict=False)), files={})

    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if _should_ignore(file_path, root):
            continue
        size_bytes = file_path.stat().st_size
        if size_bytes > max_file_bytes:
            continue
        raw = file_path.read_bytes()
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            content = None
        relative_path = file_path.relative_to(root).as_posix()
        files[relative_path] = FileSnapshot(
            path=relative_path,
            checksum=checksum_for_bytes(raw),
            size_bytes=size_bytes,
            line_count=0 if content is None else len(content.splitlines()),
            content=content,
            metadata={"binary": content is None},
        )

    return WorkspaceSnapshot(
        root_path=str(root.resolve(strict=False)),
        files=files,
        metadata={"max_file_bytes": max_file_bytes},
    )


def compare_workspace_snapshots(
    *,
    before: WorkspaceSnapshot,
    after: WorkspaceSnapshot,
) -> WorkspaceDiffResult:
    changed_files: list[ChangedFile] = []
    lines_added = 0
    lines_removed = 0

    all_paths = sorted(set(before.files) | set(after.files))
    for relative_path in all_paths:
        previous = before.files.get(relative_path)
        current = after.files.get(relative_path)
        if previous is None and current is not None:
            changed_files.append(
                ChangedFile(
                    path=relative_path,
                    change_type="ADDED",
                    lines_added=current.line_count,
                    lines_removed=0,
                )
            )
            lines_added += current.line_count
            continue
        if previous is not None and current is None:
            changed_files.append(
                ChangedFile(
                    path=relative_path,
                    change_type="REMOVED",
                    lines_added=0,
                    lines_removed=previous.line_count,
                )
            )
            lines_removed += previous.line_count
            continue
        if previous is None or current is None:
            continue
        if previous.checksum == current.checksum:
            continue
        file_lines_added, file_lines_removed = _count_line_changes(previous.content, current.content)
        changed_files.append(
            ChangedFile(
                path=relative_path,
                change_type="MODIFIED",
                lines_added=file_lines_added,
                lines_removed=file_lines_removed,
            )
        )
        lines_added += file_lines_added
        lines_removed += file_lines_removed

    return WorkspaceDiffResult(
        files_changed=changed_files,
        diff_summary={
            "files_changed_count": len(changed_files),
            "lines_added": lines_added,
            "lines_removed": lines_removed,
        },
        lines_added=lines_added,
        lines_removed=lines_removed,
    )


def _count_line_changes(before: str | None, after: str | None) -> tuple[int, int]:
    before_lines = [] if before is None else before.splitlines()
    after_lines = [] if after is None else after.splitlines()
    added = 0
    removed = 0
    for line in difflib.ndiff(before_lines, after_lines):
        if line.startswith("+ "):
            added += 1
        elif line.startswith("- "):
            removed += 1
    return added, removed


def _should_ignore(file_path: Path, root: Path) -> bool:
    parts = file_path.relative_to(root).parts[:-1]
    return any(part in IGNORED_DIRECTORIES for part in parts)
