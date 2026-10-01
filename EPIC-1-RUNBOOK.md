# EPIC-1 Runbook: Installation, Quality Gates, and PM Demo

Date: 2026-09-30 (America/Costa_Rica)

EPIC-1 is implemented: all four stories and eleven tasks are complete. The foundation installs with uv, passes 48 tests at 100.00% coverage, enforces all four pre-commit hooks, installs as a wheel outside the repository, and passes a fresh-checkout verification. The implementation and `uv.lock` were committed in `72d2751dda03f49c3ae3bf6b01819bbfad4d1500` with the Git hook active.

Full command output, exit codes, and UTC recording timestamps are in [docs/evidence/epic-1/](docs/evidence/epic-1/README.md). The outputs below are excerpts from those actual runs. Local paths and timings will vary on another machine.

## Install, set up, and start

Use macOS or Linux with Git, Make, and uv. uv 0.11.14 was already installed on this machine; its installation was not part of the recorded work. If uv is missing, follow the [official installation instructions](https://docs.astral.sh/uv/getting-started/installation/).

From the repository root:

```sh
cd /Users/josoroma/sites/langchain
uv python install 3.12
make setup
make demo
```

All three operational commands above ran successfully. [Python installation output](docs/evidence/epic-1/18-python-install.txt):

```text
Installed Python 3.12.9 in 88ms
 + cpython-3.12.9-macos-aarch64-none (python3.12)
```

[`make setup` output](docs/evidence/epic-1/06-setup.txt):

```text
uv sync --locked
Resolved 80 packages in 3ms
Checked 78 packages in 1ms
uv run --locked pre-commit install
pre-commit installed at .git/hooks/pre-commit
```

uv creates `.venv/` and installs both application and development dependencies from `uv.lock`. Activate it only if you prefer; every Make target uses `uv run --locked` automatically. The first hook run installs separate pinned Ruff and mypy environments and needs network access. Tests and the foundation demo make no provider calls and need no API keys. Installation may download dependencies.

`make demo` starts the foundation demonstration. EPIC-1 has no web server, research workflow, or `deep-research-blog` command; those are later stories. `.env.example` documents the future `OPENROUTER_API_KEY` and `SERPER_API_KEY` variables with blank values. Creating `.env` is unnecessary for this epic.

## Successful setup commands used to create the project

These are the one-time bootstrap commands already executed, preserved for understanding how the scaffold was created. A developer using this checkout should use `make setup`, rather than initialize it again.

```sh
git init -b main
uv init --bare --name deep-research-blog-writer --python 3.12 --vcs none
uv python pin 3.12
uv add 'langchain>=1,<2' 'langgraph>=1,<2' 'deepagents>=0.7,<0.8' 'langchain-openrouter>=0.2,<1' 'pydantic>=2,<3'
uv add --dev 'ruff==0.13.0' 'mypy==1.18.1' 'pytest>=9,<10' 'pytest-cov>=7,<8' 'pre-commit>=4,<5'
```

The project files, package directories, quality configuration, and ADRs were then written as described in [EPIC-1.md](EPIC-1.md). See [Git initialization](docs/evidence/epic-1/01-git-init.txt), [uv initialization](docs/evidence/epic-1/02-uv-init.txt), [Python pinning](docs/evidence/epic-1/03-python-pin.txt), [runtime dependency installation](docs/evidence/epic-1/04-runtime-dependencies.txt), and [development dependency installation](docs/evidence/epic-1/05-dev-dependencies.txt) for the full successful outputs.

The acceptance command `uv sync` also ran successfully:

```text
Resolved 80 packages in 3ms
Checked 78 packages in 17ms
```

Source: [uv sync output](docs/evidence/epic-1/16-uv-sync.txt). Automation uses `--locked` to fail when project metadata and the lockfile disagree, as documented by [uv](https://docs.astral.sh/uv/concepts/projects/sync/).

## Verified versions

| Component | Installed version |
| --- | --- |
| Python | 3.12.9 |
| uv | 0.11.14 |
| LangChain | 1.4.3 |
| LangGraph | 1.2.12 |
| DeepAgents | 0.7.21 |
| langchain-openrouter | 0.2.9 |
| Pydantic | 2.12.5 |
| Ruff | 0.13.0 |
| mypy | 1.18.1 |
| pytest | 9.1.1 |
| pytest-cov | 7.1.0 |
| pre-commit | 4.6.2 |

These versions come from installation output and [`make demo`](docs/evidence/epic-1/11-foundation-demo.txt). Exact dependency resolutions are committed in `uv.lock`; `.python-version` selects Python 3.12 and project metadata requires Python >=3.12. Ruff and mypy match the hook revisions required by US-1.2.

## Run the quality gates

```sh
make check
make hooks
```

`make check` checks the lockfile, Ruff linting, Ruff formatting, `mypy --strict`, and pytest with branch coverage. Selected [actual output](docs/evidence/epic-1/07-quality-check.txt):

```text
All checks passed!
11 files already formatted
Success: no issues found in 11 source files
collected 48 items
TOTAL                              47      0     18      0  100.00%
Coverage XML written to file coverage.xml
Required test coverage of 80% reached. Total coverage: 100.00%
============================== 48 passed in 0.12s ==============================
```

Coverage is measured over the seven application packages, including the architecture checker. Tests do not count as application coverage. Most scaffold packages are documented placeholders; the current executable foundation has 47 statements and 18 branches. The 100% result describes this foundation, not future pipeline behavior. The [saved XML report](docs/evidence/epic-1/coverage.xml) preserves the line and branch results.

`make hooks` runs the same pinned hooks installed for commits. [Actual output](docs/evidence/epic-1/10-pre-commit.txt):

```text
ruff check...............................................................Passed
ruff format..............................................................Passed
mypy.....................................................................Passed
pytest (offline, coverage >=80%, agent boundary).........................Passed
```

The mypy and pytest hooks run over the complete configured packages/test suite on every commit, including documentation-only commits. Ruff checks staged Python files. The isolated mypy hook reads type information from `.venv/bin/python`, so run setup before attempting a commit.

## Prove that bad changes cannot pass

```sh
sh scripts/demo-quality-gates.sh
```

This successful command creates a temporary local clone, installs its environment and hooks, introduces intentional bad changes, and requires each rejection to return exit code 1. It restores the clone, reruns passing checks, and deletes the temporary checkout. Your working checkout is untouched. Allow about a minute with a warm dependency cache.

The [complete recorded demo](docs/evidence/epic-1/19-all-hook-rejections.txt) proves eleven rejections:

| Probe | Actual diagnostic/result |
| --- | --- |
| Unused import, direct Ruff check and commit | `F401` for `agents/demo_lint.py`; Ruff hook fails |
| Unformatted code, direct format check and commit | `Would reformat: agents/demo_format.py`; format hook changes the file and rejects the commit |
| Untyped function, direct strict mypy check and commit | `Function is missing a type annotation [no-untyped-def]`; mypy hook fails |
| Nested HTTP import, boundary CLI, repository test, and commit | `agents/demo_nested/bad_agent.py:1: forbidden HTTP import 'httpx'`; pytest hook fails |
| Untested application code, pytest and commit | All 48 tests pass, but coverage falls to 13.98%; pytest hook fails |

The coverage rejection uses the actual configured 80% threshold, without raising it artificially:

```text
ERROR: Coverage failure: total of 13.98 is less than fail-under=80.00
FAIL Required test coverage of 80% not reached. Total coverage: 13.98%
```

The script exits 0 only when all expected rejections and the final restored checks succeed:

```text
All rejection probes passed; the disposable checkout is restored.
```

The boundary regression suite covers all six PD-001 modules, aliases, `from` imports, imports through parent packages, submodules, nested scopes, package initializers, and recursively nested directories. It also verifies allowed imports, file/line diagnostics, missing directories, and syntax errors. This is the specified static import rule; computed dynamic imports and indirect network access are outside its scope.

## Build, install, and verify a fresh checkout

```sh
make build
sh scripts/verify-package.sh
sh scripts/verify-fresh-checkout.sh
```

All three commands succeeded. [Build output](docs/evidence/epic-1/08-build.txt):

```text
Successfully built dist/deep_research_blog_writer-0.1.0.tar.gz
Successfully built dist/deep_research_blog_writer-0.1.0-py3-none-any.whl
```

The wheel verifier installs only the application wheel into a temporary isolated environment and imports its packages from outside the checkout. [Selected output](docs/evidence/epic-1/12-wheel-install.txt):

```text
Wheel 0.1.0 installed; all seven packages import outside the checkout.
Tests and documentation are excluded from the application wheel.
```

The fresh-checkout verifier clones committed HEAD, creates a new `.venv`, and runs setup, demo, all hooks, and distribution build. It uses a warm download cache but does not reuse the working checkout's environment. [Final output](docs/evidence/epic-1/15-fresh-checkout.txt):

```text
Fresh-checkout installation and all foundation checks passed.
```

The clone verifier checks committed files. Commit any changes you intend to demonstrate before running it.

## PM walkthrough and evidence of done

Use this sequence for a five-to-ten-minute review:

1. Open [EPIC-1.md](EPIC-1.md) and the EPIC-1 section of [SPECS.md](SPECS.md#epic-1-project-foundation-and-quality-gates). Show the four completed stories and eleven completed tasks. Show the nine package directories and `uv.lock`.
2. Run `make demo`. Show Python 3.12.9, all five required framework dependencies, `Agent boundary passed: agents`, strict typing success, 48 passing tests, and 100.00% coverage.
3. Run `make hooks`. Show all four hooks passing, then open [the implementation commit transcript](docs/evidence/epic-1/13-implementation-commit.txt) to show they ran during a real successful commit.
4. Run `sh scripts/demo-quality-gates.sh`. Show a forbidden nested module named in the output, an untyped-function rejection, and a coverage failure even when all tests pass. Show each corresponding commit rejection and the final successful restoration.
5. Open [ADR 0001](docs/adr/0001-deepagents-on-langgraph.md) and [the ADR template](docs/adr/template.md). Review Context, Decision, and positive/negative Consequences.
6. Open [the fresh-checkout transcript](docs/evidence/epic-1/15-fresh-checkout.txt), [wheel installation transcript](docs/evidence/epic-1/12-wheel-install.txt), and [coverage XML](docs/evidence/epic-1/coverage.xml). Use `git status --short` to show the delivered working tree is clean.

| Story | Evidence of done |
| --- | --- |
| US-1.1 | Git initialized; lockfile committed; framework versions/imports demonstrated; all nine directories exist; fresh checkout and wheel install pass; `.env` and `runs/` ignored |
| US-1.2 | Ruff 0.13.0 and mypy 1.18.1 match hooks; strict typing rejects untyped code; 80% coverage enforced; all four hooks pass good commits and reject intentional failures |
| US-1.3 | Repository-wide recursive agent scan passes; all six forbidden modules tested; nested violations name the module and fail pytest/commit |
| US-1.4 | Numbered accepted ADR 0001 and reusable template include Context, Decision, and pros/cons under Consequences |

[`git check-ignore` output](docs/evidence/epic-1/09-secret-ignore.txt) demonstrates that `.env`, `.env.production`, `runs/demo/output/blog.md`, the virtual environment, and generated coverage reports are ignored. A specific exception permits the saved evidence XML to be versioned.

GitHub Actions is configured in [.github/workflows/quality.yml](.github/workflows/quality.yml) to run the same locked checks, hooks, and build. Hosted CI was not executed because this workspace has no configured remote. The evidence here proves local acceptance. Later epics deliver the actual model/search integrations and blog pipeline.

## Troubleshooting

| Symptom | Resolution |
| --- | --- |
| `uv` is missing | Install it using the official link above, then run `uv python install 3.12` and `make setup`. |
| Missing `.venv` or mypy hook cannot locate its Python executable | Run `make setup` from the repository root. |
| Lockfile is out of date | For an intentional dependency edit, resolve it with `uv lock`, review/commit both metadata and lockfile, then run `make setup`. |
| Ruff format hook modifies files and rejects the commit | Run `make format`, review and stage the formatted files, then retry the commit. |
| Agent boundary fails | Move HTTP access into tools/services and have the agent orchestrate the tool. The failure names the file and line. |
| Tests pass but coverage fails | Add meaningful tests for the uncovered application behavior; the minimum remains 80%. |
| Git hook is missing after cloning | Hooks are local Git configuration; run `make setup` in every new checkout. |
| Fresh-checkout verifier cannot clone HEAD | Ensure the repository has a commit. This delivery already does. |
