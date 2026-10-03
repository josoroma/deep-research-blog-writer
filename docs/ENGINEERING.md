# Engineering standard

This is the Python standard for this repository. Each rule says what is
expected, why, and **what enforces it**. A rule with no enforcement is a
guideline; say so rather than pretend.

`make check` runs everything marked *CI*. A pull request that fails it does not
merge.

## Quick reference

| Area | Rule | Enforced by |
| --- | --- | --- |
| Formatting | Ruff format, 100 columns | `ruff format --check` (CI) |
| Lint | `E F I UP B` plus the families below | `ruff check` (CI) |
| Types | `mypy --strict` over every package and the tests | mypy (CI) |
| Docstrings | Public modules, classes, functions, methods | Ruff `D1`, Google style (CI, ratcheted) |
| Complexity | McCabe ≤ 10, ≤ 12 branches, ≤ 6 returns, ≤ 50 statements | Ruff `C90`, `PLR09xx` (CI, ratcheted) |
| Exceptions | Derive from `ResearchError`, declare a category and code | `tests/test_error_contract.py` (CI) |
| Blind `except` | Forbidden unless a `noqa: BLE001 - <reason>` explains it | Ruff `BLE`, `RUF100` (CI) |
| Security | Bandit rules: SQL strings, subprocess, asserts, randomness | Ruff `S` (CI, ratcheted) |
| Dependencies | No known vulnerabilities in locked runtime packages | `make audit` (CI) |
| Tests | Offline, sockets blocked, ≥ 80% branch coverage | pytest + coverage (CI) |
| Agent boundary | Agents never import HTTP clients | `make boundary`, `tests/` (CI) |
| Build | Wheel and sdist build from the lock | `make build` (CI) |

## Docstrings

Write a docstring for every public module, class, function, and method.
Private helpers (`_name`) need one only when the *why* is not obvious.

A useful docstring says what a reader cannot see in the signature:

- the contract, such as "returns `None` when the queue is empty or the store is down"
- every exception a caller should handle, under `Raises:`
- side effects, such as "acquires the workspace lock", "writes `output/run.json`", or "never raises"
- why a non-obvious choice was made

Do not restate the signature. `"""Return the job."""` on `get_job(job_id) -> Job`
adds nothing. Use Google style (`Args:`, `Returns:`, `Raises:`). Document a class's
constructor arguments on the class, and mark `__init__` with
`# noqa: D107 - documented on the class`.

**Ratchet.** `api/`, `application/`, and `workers/` are fully enforced. The
older packages are listed in `[tool.ruff.lint.per-file-ignores]` under
"Ratchet". Remove a package's line once it is documented. Never add one for new
code.

## Comments

Comment the *why*, not the *what*. Good comments record a constraint, an
invariant, a trade-off, or a link to the ADR that decided it:

```python
# Escapes are reported as "not found" so a probe cannot learn the layout.
```

Delete comments that narrate the next line. A `noqa` or `type: ignore` must
carry a reason after ` - ` unless the code is self-evident from the rule name.

## Types and domain models

- `mypy --strict` passes with no new `type: ignore`. When one is unavoidable,
  scope it to the error code: `# type: ignore[attr-defined]`.
- Data crossing a boundary (HTTP, files, tools, providers, the job store) is a
  Pydantic `Contract` from `schemas/`. Do not use `dict[str, Any]` for anything
  with a known shape.
- Use `Literal` or `StrEnum` for closed sets of states and codes, not bare `str`.
- External providers sit behind a `Protocol` in `application/ports.py` or
  `services/`. Use cases depend on the protocol, never on `psycopg`, `httpx`, or
  an SDK.

## Errors

All project exceptions live in one hierarchy, in `schemas/errors.py`:

```text
ResearchError                      category        HTTP
├── InvalidInputError (ValueError)  invalid_input   422
├── NotFoundError (LookupError)     not_found       404
├── ConflictError (RuntimeError)    conflict        409
├── LimitExceededError              limit_exceeded  429
├── UnavailableError                unavailable     503
└── ContractViolationError          contract_violation 500
```

Rules:

1. **Raise a domain error, never an HTTP status.** Code in `application/`,
   `services/`, and `workers/` raises a `ResearchError` subclass. Only
   `api/errors.py` turns a category into a status, through `STATUS_BY_CATEGORY`.
   `STATUS_BY_CODE` is the short list of exceptions: `budget_exceeded` (422,
   because retrying never helps), `artifact_too_large` (413), and `unauthorized` (401).
2. **Every class sets `category` and `code`.** `code` is a stable public
   identifier; renaming one is a breaking API change.
3. **Keep the builtin base when you re-parent.** `ArtifactNotFound` stays a
   `FileNotFoundError`, `SearchProviderError` stays a `ValueError`, and so on, so
   existing `except` clauses keep working. `tests/test_error_contract.py` pins
   this list.
4. **Messages are safe.** No secrets, DSNs, provider bodies, credential-bearing
   URLs, or absolute server paths. 5xx responses replace the message entirely
   and log the type with the request id.
5. **Hide existence where it matters.** Path escapes (`UnsafePath`) are
   `not_found`, never `forbidden`, so a probe cannot map the filesystem.
6. **Validate input before state.** A malformed request reports the malformed
   field (422) even when the target resource is also missing.
7. **Catch narrowly.** `except Exception` is allowed only at an isolation
   boundary, such as one URL out of thirty, tracing that must never fail a run, or
   the worker's last-resort handler. Each one carries `# noqa: BLE001 - <why>`.
   Prefer `contextlib.suppress(...)` with a comment over `try/except/pass`.

## Orchestration stays thin

Entry points (`workflows/cli.py:main`, routers, `ResearchWorker._execute`) route.
They parse, call one use case, and translate the result. They do not:

- validate more than one rule inline. Extract `_topic_request`, `validate_idempotency_key`, and so on.
- branch on a mode more than once. Dispatch to one function per mode.
- build provider clients. Inject them or build them in a factory.

Ruff's complexity limits catch a regression. If a change pushes a function over
the limit, split it; do not add it to the ratchet list. The functions already on
that list (`services/fetch_service.py`, `services/observability.py`,
`tools/corpus_tools.py`, ...) should be split the next time they are edited.

## Network calls: timeout, retry, backoff

Every network call has an explicit timeout, a bounded retry count, and a backoff
policy, all as named constants or settings:

| Call | Timeout | Retries | Backoff | Where |
| --- | --- | --- | --- | --- |
| Page fetch | 15 s per page, a budget for the whole body | 3 | `2^(n-1)` s with up to 0.25 s jitter | `services/fetch_service.py` |
| Search provider | `SEARCH_TIMEOUT_SECONDS` (15) | none; one failure fails search | — | `services/search_provider.py` |
| Model | `MODEL_TIMEOUT_SECONDS` (30) | `MODEL_MAX_RETRIES` (2) | SDK backoff | `services/llm_service.py` |
| Telemetry flush | `TELEMETRY_TIMEOUT_SECONDS` (3) | none; failure is recorded | — | `services/observability.py` |
| PostgreSQL connect | `CONNECT_TIMEOUT_SECONDS` (5) | none; fails as 503 | — | `services/postgres_jobs.py` |
| Whole phase | — | retry once | none | `services/reliability.py:run_phase` |

Do not add a network call without a row in this table.

## Idempotency

- `POST /v1/runs` and `POST /v1/runs/{id}/resume` require an `Idempotency-Key`.
  The same key and normalized payload return the original job; a changed payload
  is `409 idempotency_conflict`. See ADR 0009.
- Admission is one transaction: idempotency check, queue bound, insert.
- Source files are immutable (`SourceExistsError`). Resume continues the same
  run and never rewrites a source.
- Timestamps come from an injected `Clock` called per operation, never captured
  once at construction.

## Logging and correlation

- Every HTTP request has an `X-Request-ID`, either from the client or generated,
  echoed on the response and included in every error envelope.
- Each run writes structured JSON Lines to `logs/execution.log`, keyed by `run_id`.
  The worker binds `job_id` and `attempt` to that observer (ADR 0008).
- Use `logging.getLogger(__name__)` with `extra={...}` fields, not formatted
  strings, so fields stay queryable. Never log secrets or provider bodies.

## Tests

- The offline suite blocks sockets and needs no keys. Live checks are marked
  `@pytest.mark.live` and excluded by default.
- Every error path a client can reach has a test that asserts the status, the
  `code`, and that no secret appears in the body. See `tests/test_api_http.py`.
- Contract tests pin public shapes: `tests/test_error_contract.py` for errors,
  and the schema tests for Pydantic contracts.
- Prefer a fake behind the real `Protocol` over `monkeypatch` of internals.

## Security

- Ruff `S` runs on all production code. `S608` (SQL built from strings) is allowed
  only in `services/postgres_jobs.py` and the migration tracker, where the only
  interpolated value is a module constant; every value is a bound `%s` parameter.
- Compare secrets with `hmac.compare_digest`.
- `make audit` scans `uv.lock` runtime dependencies with `pip-audit` in CI.
- Bearer tokens, DSNs, and provider keys are `SecretStr` and never appear in
  `repr`, logs, responses, or artifacts.

## Adding to the ratchet, or removing from it

The ratchet lists in `pyproject.toml` only shrink. To pay one down:

1. Remove the path's line.
2. Run `uv run ruff check <path>` and fix the findings.
3. Run `make check`.
