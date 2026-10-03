"""The shared exception hierarchy for domain, application, and adapter errors.

Every project exception derives from :class:`ResearchError` and declares one
:class:`ErrorCategory`. Transports map the category, not the concrete class, to an
outcome: the API picks an HTTP status, the CLI picks an exit code, and the worker
picks a terminal job reason. That keeps error semantics in one place and means a
new error type needs no new handler.

Concrete errors also keep their original builtin base (``ValueError``,
``RuntimeError``, ``FileNotFoundError``, ...) so existing ``except`` clauses and
callers keep working while code migrates to category-based handling.

Messages must be safe to show a client: no secrets, provider bodies, request
URLs with credentials, or absolute server paths.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar


class ErrorCategory(StrEnum):
    """What kind of failure an error is, independent of who reports it.

    Attributes:
        INVALID_INPUT: The caller sent something the contract rejects.
        NOT_FOUND: A named run, job, or artifact does not exist or is hidden.
        CONFLICT: The request is valid but clashes with current state.
        LIMIT_EXCEEDED: A bound was hit (queue size, artifact size, budget).
        UNAVAILABLE: A dependency or credential is missing or unreachable.
        CONTRACT_VIOLATION: Our own code or a provider broke a typed contract.
        INTERNAL: An invariant failed; this is a bug, not a caller mistake.
    """

    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    LIMIT_EXCEEDED = "limit_exceeded"
    UNAVAILABLE = "unavailable"
    CONTRACT_VIOLATION = "contract_violation"
    INTERNAL = "internal"


class ResearchError(Exception):
    """Base class for every exception this project raises on purpose.

    Subclasses set ``category`` and ``code`` as class attributes. ``code`` is a
    stable, machine-readable identifier; clients may branch on it, so renaming one
    is a breaking change.

    Args:
        message: A safe, human-readable explanation.
        code: Overrides the class-level ``code`` for one instance, for errors that
            carry several stable codes (for example admission rejections).
    """

    category: ClassVar[ErrorCategory] = ErrorCategory.INTERNAL
    code: str = "internal_error"

    def __init__(self, message: str = "", *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code

    @property
    def message(self) -> str:
        """The safe message passed at construction."""
        return str(self)


class InvalidInputError(ResearchError, ValueError):
    """The caller supplied input that violates a contract or a rule."""

    category = ErrorCategory.INVALID_INPUT
    code = "invalid_input"


class NotFoundError(ResearchError, LookupError):
    """A requested run, job, or artifact does not exist or is not exposed."""

    category = ErrorCategory.NOT_FOUND
    code = "not_found"


class ConflictError(ResearchError, RuntimeError):
    """A valid request that conflicts with the current state of a resource."""

    category = ErrorCategory.CONFLICT
    code = "conflict"


class LimitExceededError(ResearchError, RuntimeError):
    """A configured bound was reached; retrying later or with less may succeed."""

    category = ErrorCategory.LIMIT_EXCEEDED
    code = "limit_exceeded"


class UnavailableError(ResearchError, RuntimeError):
    """A required dependency, credential, or store is missing or unreachable."""

    category = ErrorCategory.UNAVAILABLE
    code = "unavailable"


class ContractViolationError(ResearchError, TypeError):
    """A component returned data outside its declared typed contract."""

    category = ErrorCategory.CONTRACT_VIOLATION
    code = "contract_violation"


__all__ = [
    "ConflictError",
    "ContractViolationError",
    "ErrorCategory",
    "InvalidInputError",
    "LimitExceededError",
    "NotFoundError",
    "ResearchError",
    "UnavailableError",
]
