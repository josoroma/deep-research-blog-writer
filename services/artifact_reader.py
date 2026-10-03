"""Authorized, bounded reads of run workspace artifacts.

Run IDs are resolved through trusted metadata, never by joining client input onto
a path. Every resolved path is checked for containment under the configured
workspace root, and symlinks are rejected rather than followed. Raw HTML caches,
checkpoint databases and the ownership lock are not downloadable artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from schemas.responses import RunReport

LOG_ARTIFACT = "logs/execution.log"
TELEMETRY_ARTIFACT = "logs/telemetry.json"
# Only these paths are served. A directory listing of runs/ is never exposed.
ALLOWED_PREFIXES: tuple[str, ...] = (
    "output/",
    "research/",
    "logs/",
    "fetch_state.json",
    "fetch_outcomes.json",
    "extraction_results.json",
    "search_state.json",
    "search_plan.json",
    "search_results.json",
    "clean_results.json",
    "corpus_state.json",
    "request.json",
    "job.json",
)
EXCLUDED_PREFIXES: tuple[str, ...] = ("logs/checkpoints", "checkpoints.sqlite")
MEDIA_TYPES = {
    ".md": ("markdown", "text/markdown; charset=utf-8"),
    ".json": ("json", "application/json; charset=utf-8"),
    ".log": ("log", "application/x-ndjson; charset=utf-8"),
    ".txt": ("other", "text/plain; charset=utf-8"),
    ".html": ("other", "text/html; charset=utf-8"),
}


class ArtifactNotFound(FileNotFoundError):
    """The run or artifact does not exist, or is not downloadable."""


class ArtifactTooLarge(ValueError):
    """The artifact exceeds the configured download bound."""


class UnsafePath(ValueError):
    """A requested path escaped the workspace root or followed a symlink."""


class ArtifactReader:
    def __init__(self, runs_root: Path, *, max_bytes: int, log_page_limit: int) -> None:
        self.runs_root = runs_root.resolve()
        self.max_bytes = max_bytes
        self.log_page_limit = log_page_limit

    # -- run resolution --------------------------------------------------------
    def run_root(self, run_id: str) -> Path:
        """Resolve a run id to its directory, enforcing containment.

        Raises :class:`ArtifactNotFound` for an unknown run and :class:`UnsafePath`
        when the resolved path would leave the workspace root.
        """
        if not run_id or "/" in run_id or "\\" in run_id or run_id in {".", ".."}:
            raise ArtifactNotFound(f"Unknown run: {run_id}")
        candidate = (self.runs_root / run_id).resolve()
        if candidate != self.runs_root and self.runs_root not in candidate.parents:
            raise UnsafePath("Run path escapes the workspace root")
        if not candidate.is_dir():
            raise ArtifactNotFound(f"Unknown run: {run_id}")
        return candidate

    _run_root = run_root

    def _resolve(self, run_id: str, relative: str) -> Path:
        if not self._is_allowed(relative):
            raise ArtifactNotFound(f"Unknown artifact: {relative}")
        root = self.run_root(run_id)
        target = root / relative
        # Reject symlinks at every level before resolving, so a link cannot escape.
        probe = root
        for part in Path(relative).parts:
            probe = probe / part
            if probe.is_symlink():
                raise UnsafePath(f"Artifact path uses a symlink: {relative}")
        resolved = target.resolve()
        if resolved != root and root not in resolved.parents:
            raise UnsafePath("Artifact path escapes the run workspace")
        return resolved

    def _is_allowed(self, relative: str) -> bool:
        cleaned = relative.strip("/")
        if not cleaned or ".." in Path(cleaned).parts:
            return False
        if any(cleaned.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
            return False
        return any(cleaned.startswith(prefix) for prefix in ALLOWED_PREFIXES)

    # -- reads -----------------------------------------------------------------
    def list_artifacts(self, run_id: str) -> list[dict[str, object]]:
        root = self.run_root(run_id)
        entries: list[dict[str, object]] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(root).as_posix()
            if not self._is_allowed(relative):
                continue
            if path.stat().st_size > self.max_bytes:
                continue
            kind, media = _describe(relative)
            entries.append(
                {
                    "artifact_id": relative,
                    "path": relative,
                    "kind": kind,
                    "media_type": media,
                    "size_bytes": path.stat().st_size,
                    "download_url": f"/v1/runs/{quote(run_id)}/artifacts/{quote(relative)}",
                }
            )
        return entries

    def read_bytes(self, run_id: str, artifact_id: str) -> tuple[str, str, bytes]:
        path = self._resolve(run_id, artifact_id)
        if not path.is_file():
            raise ArtifactNotFound(f"Unknown artifact: {artifact_id}")
        size = path.stat().st_size
        if size > self.max_bytes:
            raise ArtifactTooLarge(f"Artifact exceeds {self.max_bytes} bytes")
        _, media = _describe(artifact_id)
        return artifact_id.rsplit("/", 1)[-1], media, path.read_bytes()

    def read_log_page(
        self, run_id: str, *, cursor: int, limit: int
    ) -> tuple[list[dict[str, object]], int | None]:
        path = self._resolve(run_id, LOG_ARTIFACT)
        if not path.is_file():
            return [], None
        bounded = max(1, min(limit, self.log_page_limit))
        records: list[dict[str, object]] = []
        with path.open("r", encoding="utf-8") as stream:
            for index, line in enumerate(stream):
                if index < cursor:
                    continue
                if len(records) >= bounded:
                    return records, index
                text = line.strip()
                if not text:
                    continue
                records.append(_project(text))
        return records, None

    # -- reports ---------------------------------------------------------------
    def read_report(self, run_id: str) -> RunReport | None:
        path = self._resolve(run_id, "output/run.json")
        if not path.is_file():
            return None
        return RunReport.model_validate_json(path.read_text(encoding="utf-8"))

    def read_run_state(self, run_id: str) -> dict[str, object]:
        """Best-effort progress snapshot from the newest milestone state file."""
        for name in ("corpus_state.json", "fetch_state.json", "search_state.json"):
            path = self._resolve(run_id, name)
            if path.is_file():
                loaded = json.loads(path.read_text(encoding="utf-8"))
                return loaded if isinstance(loaded, dict) else {}
        return {}

    def run_topic(self, run_id: str) -> str:
        path = self._resolve(run_id, "request.json")
        if not path.is_file():
            return run_id
        loaded = json.loads(path.read_text(encoding="utf-8"))
        topic = loaded.get("topic") if isinstance(loaded, dict) else None
        return str(topic) if topic else run_id


def _describe(relative: str) -> tuple[str, str]:
    suffix = Path(relative).suffix.lower()
    return MEDIA_TYPES.get(suffix, ("other", "application/octet-stream"))


def _project(text: str) -> dict[str, object]:
    """Project one log line onto a small, already-redacted public shape."""
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        return {"event": "[unparseable]"}
    if not isinstance(loaded, dict):
        return {"event": "[unparseable]"}
    reserved = {"timestamp", "level", "phase", "event"}
    return {
        "timestamp": _string(loaded.get("timestamp")),
        "level": _string(loaded.get("level")),
        "phase": _string(loaded.get("phase")),
        "event": _string(loaded.get("event")),
        "fields": {key: value for key, value in loaded.items() if key not in reserved},
    }


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None
