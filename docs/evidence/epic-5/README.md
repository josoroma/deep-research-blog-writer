# EPIC-5 delivery evidence

See [EPIC-5-RUNBOOK.md](../../../EPIC-5-RUNBOOK.md) for setup, successful commands, PM steps and scope.

Command transcripts contain the exact commands, actual stdout/stderr and exit status. `commands.jsonl` adds UTC timestamps/durations. `07-check.txt` is a historical formatting failure; `11-check.txt` is its successful replacement.

`offline/` is the original mock HTTP/real parser demo workspace; request times are explicit virtual monotonic seconds. `live-cli/` contains artifacts from real public HTTP, seeded with one typed URL rather than a new search request. `live-smoke.json` separately captures real request starts, crawler identity and extraction metadata. Public content may change. No API credentials or raw page HTML are saved here.

`coverage.xml` captures the passing offline suite. Final hook, committed checkout and source-hash evidence will be linked when verification finishes. Hosted CI was not executed as part of this local verification.
