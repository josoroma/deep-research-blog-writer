# EPIC-7 Runbook: Synthesis and Blog Authoring

Status: verified offline on 2026-10-01. The analyst writes a cited summary, the
writer drafts the blog, and a deterministic citation gate checks every `[S-NN]`
against the corpus and the References section. A draft outside 2000–5000 words
is kept and recorded; dangling citations get at most two repair passes.

## What a PM sees

- `research/summary.md` with the six required sections and a theme that cites a
  real source.
- `output/blog.md` with the seven required headings, inline `[S-NN]` citations,
  and a References line carrying the source title and URL.
- `output/run.json` recording the gate: citations checked, dangling ids, and
  the reason when the run fails.
- A source file that the writer cannot overwrite.

## Commands that passed

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy --strict
uv run --locked pytest -q -m 'not live' -p no:cacheprovider
make demo-epic-7
make hooks
make build
sh scripts/verify-epic-7-package.sh
```

Result: 432 offline tests passed, coverage 93.76%, strict typing clean, and the
installed wheel reproduced the citation gate outside the checkout.

## Demo

```sh
make setup
make demo-epic-7
uv run --locked python scripts/inspect-authoring.py runs/<run-id>
```

`make demo-epic-7` builds an offline corpus, writes a cited summary and a draft
with the required headings, confirms every citation resolves, then shows that a
dangling `S-31` is detected. No model and no network are used.

## Evidence

| Check | Result |
| --- | --- |
| Summary sections and theme citation | passed |
| Blog headings in required order | passed |
| Citations resolve to corpus and References | passed |
| Dangling `S-31` detected | passed |
| Short draft kept with `blog_length` | passed (unit) |
| Two failed repairs end `dangling_citations` | passed (unit) |
| Writer has no network tool | passed (unit) |
| Source overwrite refused | passed (unit) |
| Installed wheel, exit 2 without workspace | passed |
