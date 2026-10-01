"""Filesystem backend that refuses to mutate an existing source file.

BR-003 makes a source immutable once it is written. The stock backend overwrites
on `write` and rewrites on `edit`, so this subclass narrows exactly those paths.
Reads, listings, and every other file stay available to the analyst and writer.
"""

from __future__ import annotations

from pathlib import Path

from deepagents.backends.filesystem import FilesystemBackend
from deepagents.backends.protocol import DeleteResult, EditResult, WriteResult

from services.corpus import SOURCE_FILE

IMMUTABLE = "source files are immutable and cannot be changed after they are written"


def is_source_file(path: str) -> bool:
    """A rank-numbered source, whatever slash or leading slash the caller used."""
    candidate = Path(path)
    return candidate.parent.name == "research" and SOURCE_FILE.match(candidate.name) is not None


class ImmutableSourceBackend(FilesystemBackend):
    """Real-disk workspace backend with immutable `research/NNN_<slug>.md` files."""

    def _refuse(self, file_path: str) -> bool:
        try:
            resolved = self._resolve_path(file_path)
        except (OSError, RuntimeError, ValueError):
            return False
        return is_source_file(self._display_path(resolved)) and resolved.exists()

    def write(self, file_path: str, content: str) -> WriteResult:
        if self._refuse(file_path):
            return WriteResult(error=f"Error writing file '{file_path}': {IMMUTABLE}")
        return super().write(file_path, content)

    def edit(
        self, file_path: str, old_string: str, new_string: str, replace_all: bool = False
    ) -> EditResult:
        if self._refuse(file_path):
            return EditResult(error=f"Error editing file '{file_path}': {IMMUTABLE}")
        return super().edit(file_path, old_string, new_string, replace_all)

    def delete(self, file_path: str) -> DeleteResult:
        if self._refuse(file_path):
            return DeleteResult(error=f"Error deleting file '{file_path}': {IMMUTABLE}")
        return super().delete(file_path)
