from __future__ import annotations

from pathlib import Path

from lummevia_code_changes.schemas import (
    CodeArtifact,
    checksum_for_bytes,
    checksum_for_text,
    normalize_artifact_path,
)


def create_artifact_from_file(
    path: str | Path,
    *,
    artifact_type: str,
) -> CodeArtifact:
    artifact_path = Path(path)
    raw = artifact_path.read_bytes()
    return CodeArtifact(
        artifact_type=artifact_type,
        path=normalize_artifact_path(artifact_path),
        checksum=checksum_for_bytes(raw),
        size_bytes=len(raw),
        metadata={"source": "filesystem"},
    )


def create_simulated_artifact(
    *,
    artifact_type: str,
    path: str,
    content_hint: str,
    metadata: dict[str, object] | None = None,
) -> CodeArtifact:
    return CodeArtifact(
        artifact_type=artifact_type,
        path=path,
        checksum=checksum_for_text(content_hint),
        size_bytes=len(content_hint.encode("utf-8")),
        metadata=metadata or {},
    )
