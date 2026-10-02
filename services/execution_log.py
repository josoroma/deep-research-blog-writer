"""Thread-safe, run-scoped JSON Lines with an intentionally small safe payload."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

LOG_PATH = "logs/execution.log"
SECRET_KEYS = re.compile(r"api.?key|token|password|secret|authorization|credential", re.I)


def safe_url(value: str) -> str:
    parts = urlsplit(value)
    netloc = parts.netloc.rsplit("@", 1)[-1]
    query = [
        (key, "[REDACTED]" if SECRET_KEYS.search(key) else val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit((parts.scheme, netloc, parts.path, urlencode(query), ""))


class ExecutionLog:
    def __init__(self, workspace: Path, run_id: str) -> None:
        self.path = workspace / LOG_PATH
        self.run_id = run_id
        self._lock = RLock()
        if self.path.parent.is_symlink() or self.path.is_symlink():
            raise ValueError("Execution log must not be a symlink")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, phase: str, event: str, *, level: str = "INFO", **fields: object) -> None:
        record: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level,
            "run_id": self.run_id,
            "phase": phase,
            "event": event,
        }
        for key, value in fields.items():
            if key in record:
                continue
            if SECRET_KEYS.search(key) and key not in {
                "tokens_used",
                "input_tokens",
                "output_tokens",
            }:
                record[key] = "[REDACTED]"
            elif key == "url" and isinstance(value, str):
                record[key] = safe_url(value)
            elif isinstance(value, (str, int, float, bool)) or value is None:
                record[key] = value
        encoded = json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n"
        with self._lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(encoded)
