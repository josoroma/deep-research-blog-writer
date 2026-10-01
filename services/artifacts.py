"""Atomic JSON artifact writes; reject symlinks instead of following them."""

import json
import os
import tempfile
from pathlib import Path


def write_json(path: Path, payload: object) -> None:
    if path.is_symlink():
        raise ValueError(f"Artifact destination is a symlink: {path.name}")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
