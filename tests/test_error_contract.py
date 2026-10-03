"""Contract tests for the shared exception hierarchy and its HTTP mapping.

These guard the rules in docs/ENGINEERING.md: every project exception derives
from ResearchError, declares a category and a stable code, keeps its legacy
builtin base, and maps to exactly one HTTP status.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

import pytest

from api.errors import STATUS_BY_CATEGORY, STATUS_BY_CODE, ApiError, status_for
from application.job_service import InvalidSubmission
from schemas.errors import ErrorCategory, ResearchError

PACKAGES = ("agents", "api", "application", "schemas", "services", "tools", "workers", "workflows")


def _project_exceptions() -> list[type[BaseException]]:
    found: dict[str, type[BaseException]] = {}
    for package_name in PACKAGES:
        package = importlib.import_module(package_name)
        for info in pkgutil.walk_packages(package.__path__, prefix=f"{package_name}."):
            module = importlib.import_module(info.name)
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, BaseException)
                    and obj.__module__ == module.__name__
                    and obj.__module__.split(".")[0] in PACKAGES
                ):
                    found[f"{obj.__module__}.{obj.__qualname__}"] = obj
    return sorted(found.values(), key=lambda cls: f"{cls.__module__}.{cls.__qualname__}")


EXCEPTIONS = _project_exceptions()


def test_the_scan_found_the_hierarchy() -> None:
    names = {cls.__name__ for cls in EXCEPTIONS}
    assert {"ResearchError", "JobStoreError", "ArtifactNotFound", "AdmissionError"} <= names


@pytest.mark.parametrize("cls", EXCEPTIONS, ids=lambda cls: cls.__qualname__)
def test_every_project_exception_derives_from_research_error(cls: type[BaseException]) -> None:
    assert issubclass(cls, ResearchError), (
        f"{cls.__module__}.{cls.__qualname__} must derive from schemas.errors.ResearchError"
    )


@pytest.mark.parametrize("cls", EXCEPTIONS, ids=lambda cls: cls.__qualname__)
def test_every_project_exception_has_a_docstring(cls: type[BaseException]) -> None:
    assert cls.__doc__ and cls.__doc__.strip(), f"{cls.__qualname__} needs a docstring"


@pytest.mark.parametrize(
    "cls",
    [cls for cls in EXCEPTIONS if issubclass(cls, ResearchError) and cls is not ApiError],
    ids=lambda cls: cls.__qualname__,
)
def test_every_error_maps_to_a_status(cls: type[ResearchError]) -> None:
    assert isinstance(cls.category, ErrorCategory)
    assert cls.code and cls.code == cls.code.lower() and " " not in cls.code
    status = STATUS_BY_CODE.get(cls.code, STATUS_BY_CATEGORY[cls.category])
    assert 400 <= status <= 599


def test_every_category_has_a_status() -> None:
    assert set(STATUS_BY_CATEGORY) == set(ErrorCategory)


@pytest.mark.parametrize(
    ("dotted", "builtin"),
    [
        ("services.artifact_reader.ArtifactNotFound", FileNotFoundError),
        ("services.artifact_reader.ArtifactTooLarge", ValueError),
        ("services.artifact_reader.UnsafePath", ValueError),
        ("services.corpus.SourceExistsError", FileExistsError),
        ("services.search_provider.SearchProviderError", ValueError),
        ("services.llm_service.MissingOpenRouterKey", ValueError),
        ("services.fetch_service.MissingCrawlerContact", ValueError),
        ("services.workspace_lock.WorkspaceBusy", RuntimeError),
        ("application.ports.JobStoreError", RuntimeError),
        ("application.migrations.MigrationError", RuntimeError),
        ("application.job_service.AdmissionError", ValueError),
        ("tools.registry.ToolOutputError", TypeError),
        ("agents.search_planner.SearchPlanningError", ValueError),
        ("agents.deep_research.UnsupportedModelProvider", ValueError),
    ],
)
def test_legacy_builtin_bases_are_preserved(dotted: str, builtin: type[Exception]) -> None:
    # Callers written before the hierarchy still catch these by builtin type.
    module_name, _, name = dotted.rpartition(".")
    cls = getattr(importlib.import_module(module_name), name)
    assert issubclass(cls, builtin)


@pytest.mark.parametrize(
    ("dotted", "kwargs", "status"),
    [
        ("application.job_service.InvalidSubmission", {"code": "missing_idempotency_key"}, 422),
        ("application.job_service.BudgetExceeded", {}, 422),
        ("application.job_service.SubmissionConflict", {}, 409),
        ("application.job_service.QueueSaturated", {"retry_after": 1}, 429),
        ("application.ports.JobStoreError", {}, 503),
        ("services.artifact_reader.ArtifactNotFound", {}, 404),
        ("services.artifact_reader.UnsafePath", {}, 404),
        ("services.artifact_reader.ArtifactTooLarge", {}, 413),
        ("services.workspace_lock.WorkspaceBusy", {}, 409),
        ("tools.registry.ToolOutputError", {}, 500),
    ],
)
def test_status_for_known_errors(dotted: str, kwargs: dict[str, object], status: int) -> None:
    module_name, _, name = dotted.rpartition(".")
    cls = getattr(importlib.import_module(module_name), name)
    assert status_for(cls("message", **kwargs)) == status


def test_api_error_category_is_per_instance() -> None:
    error = ApiError(ErrorCategory.CONFLICT, "custom", "message")
    assert status_for(error) == 409
    assert ApiError.category is ErrorCategory.INTERNAL


def test_code_override_is_per_instance() -> None:
    custom = InvalidSubmission("m", code="missing_idempotency_key")
    assert custom.code == "missing_idempotency_key"
    assert InvalidSubmission("m").code == "invalid_submission"
