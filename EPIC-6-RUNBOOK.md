# EPIC-6 Runbook: Research Corpus

Status: verified locally on 2026-10-01. Offline acceptance does not depend on network access or API keys.

## What this proves

`collect_source` fetches one clean URL, extracts it, and writes exactly one immutable source file, returning metadata only. `build_index` rebuilds `research/index.md` from those files. A failed URL is recorded and skipped; it never aborts the run or leaves a partial file.

The offline demo collects 10 fixture URLs and shows:

- 5 sources written, ranks 1, 2, 7, 8, and 10, with gaps at 3, 4, 5, 6, and 9
- front-matter (`source_id`, `url`, `title`, `author`, `published`, `fetched`, `word_count`) and a body that starts with the title heading
- a non-ASCII title falling back to the URL slug: `research/010_fixture-test-non-ascii.md`
- an index whose rows match the front-matter, with `|` escaped in titles
- agent `write_file`, `edit_file`, and `delete` refused on an existing source file
- one unreachable URL and one thin page contained, so the run still completes

## Setup

```sh
make setup
```

## Commands that passed

```sh
make check          # ruff, format, mypy --strict, 417 offline tests, 95.12% coverage
make demo-epic-6    # offline corpus demo; prints the workspace and evidence
make demo-epic-2 && make demo-epic-3 && make demo-epic-4 && make demo-epic-5
make hooks          # pre-commit on all files
make build          # sdist and wheel
sh scripts/verify-epic-6-package.sh   # installed wheel, outside the checkout
```

`make check` is `uv lock --check`, `ruff check`, `ruff format --check`, `mypy --strict`, and `pytest -m 'not live'`.

## Demo for a PM

Offline, no keys, deterministic:

```sh
make demo-epic-6
uv run --locked python scripts/inspect-corpus.py runs/<printed-run-id>
```

Open `research/index.md` and any `research/NNN_*.md` in that run. The transcript and a copy of the workspace are in `docs/evidence/epic-6/`.

Corpus-only on an existing search workspace:

```sh
uv run --locked deep-research-blog --corpus-only --workspace runs/<search-run>
```

`--corpus-only` without `--workspace` exits 2.

Live, optional, needs `CRAWLER_CONTACT` in `.env`:

```sh
uv run --locked python scripts/create-live-corpus-workspace.py
uv run --locked deep-research-blog --corpus-only --workspace runs/<seeded-run>
```

## Evidence of done

| Check | Result |
| --- | --- |
| Offline tests | 417 passed, 3 live deselected |
| Coverage | 95.12% (gate is 80%) |
| `mypy --strict` | clean, 78 source files |
| Prior demos | EPIC-2, EPIC-3, EPIC-4, EPIC-5 pass |
| Installed wheel | corpus demo, rank gaps, immutability, exit 2 |
| Stories | US-6.1, US-6.2, US-6.3 and their tasks marked DONE in `SPECS.md` |

Transcripts, the offline snapshot, `coverage.xml`, and `commands.jsonl` are in `docs/evidence/epic-6/`.

## Out of scope

Synthesis, blog drafting, citation validation, the run report, and SQLite resume stay in later epics. Skipping a URL whose source file already exists is implemented now because source files are immutable.
