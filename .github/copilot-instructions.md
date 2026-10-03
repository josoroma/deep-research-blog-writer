# Repository instructions

Python 3.12, uv, DeepAgents on LangGraph, FastAPI for the server path.
`docs/ENGINEERING.md` is the coding standard. Follow it; the rules there are
enforced by `make check`.

- Run `make check` before calling a change done. It runs lock, Ruff, format,
  `mypy --strict`, and the offline tests with coverage.
- Raise a subclass of `schemas.errors.ResearchError` with a `category` and a stable
  `code`. Never pick an HTTP status outside `api/errors.py`.
- Keep entry points thin: parse, call one use case, translate the result.
  Split a function rather than add it to a Ruff ratchet list.
- Write Google-style docstrings for public code. Say what the signature cannot:
  `Raises:`, side effects, and why.
- Every network call needs a timeout, a bounded retry, and a row in the
  "Network calls" table in `docs/ENGINEERING.md`.
- `except Exception` needs `# noqa: BLE001 - <reason>`.
- Agents never import HTTP clients (`make boundary`).
