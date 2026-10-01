# EPIC-6 delivery evidence

See [EPIC-6-RUNBOOK.md](../../../EPIC-6-RUNBOOK.md) for setup, the commands that passed, and the PM demo.

`01-demo.txt` is the offline demo transcript. `offline/workspace` is the run it produced: five source files, rank gaps at 3, 4, 5, 6, and 9, and `research/index.md`. Timing is virtual monotonic seconds and no network was used.

`02-check.txt` is the passing quality gate (417 tests, 95.12% coverage). `03-prior-demos.txt` reruns EPIC-2 through EPIC-5. `04-hooks.txt`, `05-build.txt`, and `06-wheel.txt` are the pre-commit hooks, the build, and the installed-wheel check run outside the checkout.

`coverage.xml` is the passing offline suite. `commands.jsonl` records the commands with UTC timestamps. `source-manifest.json` hashes the delivered source and is verified by `scripts/verify-source-manifest.py`.
