# EPIC-4 execution evidence

The [runbook](../../../EPIC-4-RUNBOOK.md) contains installation, configuration, successful command outputs, a PM demonstration, story acceptance, and observed failures. The [plan](../../../EPIC-4.md) was created before implementation.

- [Final quality gates](13-check.txt): 294 offline tests pass, 2 live tests deselected, 97.73% coverage, strict typing and Ruff pass.
- [Batched actual-agent demo](11-batch-demo.txt): five search calls, 50 raw / 30 topic / 30 clean results; stable merge, normalization, replay, and budget assertions.
- [Live SerpApi page 2](03-live-serpapi.txt) and [live pytest](09-live-pytest.txt): actual results ranked 11–20.
- [Production planner/API CLI](05-live-search-cli.txt): three model-derived variants, 51 raw / 30 clean results during implementation.
- [Final provider-only CLI](19-live-repeatable-cli.txt): 50 raw / 30 clean on the final implementation with explicit repeatable variants.
- [All hooks](21-hooks.txt), [implementation commit with hooks](22-implementation-commit.txt), [installed wheel](18-wheel.txt), and [committed fresh checkout](23-fresh-checkout.txt).
- [coverage.xml](coverage.xml) and [source/build hash manifest](source-manifest.json).
- [Offline artifacts](offline/search_plan.json), [production-planner artifacts](live-planner/search_plan.json), and [final live artifacts](live-repeatable/search_plan.json), each with request/raw/clean files beside the plan.
- [Command ledger](commands.jsonl): exact argv rendered as commands, UTC timestamps, durations, actual/expected exit codes, and transcript filenames.

Files numbered 02, 04, 10, 12, and 14 record unsuccessful attempts. Their causes and subsequent successful checks are documented in the runbook; they are not represented as completed acceptance runs. Offline demos explicitly use fake models/providers. Live snapshots contain application result contracts, with no provider request metadata or API credentials. Local `runs/` workspaces are ignored by Git; the reviewed snapshots remain inspectable from a fresh checkout.

The fresh checkout verifies implementation commit `f350effee023b49c0bd12e896880259165b65f68`. Final documentation-only changes preserve the source hashes. Hosted CI execution and later-epic blog production are outside this evidence.
