# EPIC-5 delivery evidence

See [EPIC-5-RUNBOOK.md](../../../EPIC-5-RUNBOOK.md) for setup, successful commands, PM steps and scope.

Command transcripts contain the exact commands, actual stdout/stderr and exit status. `commands.jsonl` adds UTC timestamps/durations. `07-check.txt` is a historical formatting failure; `11-check.txt` is its successful replacement.

`offline/` is the original mock HTTP/real parser demo workspace; request times are explicit virtual monotonic seconds. `live-cli/` contains artifacts from real public HTTP, seeded with one typed URL rather than a new search request. `live-smoke.json` separately captures real request starts, crawler identity and extraction metadata. Public content may change. No API credentials or raw page HTML are saved here.

`coverage.xml` captures the passing offline suite. Final verification passes 401 offline tests with 97.50% coverage. [33-fresh-checkout.txt](33-fresh-checkout.txt) captures setup, all gates/hooks/demos, build and installed-wheel checks at source revision `11225f2`. [source-manifest.json](source-manifest.json) and [35-verify-source.txt](35-verify-source.txt) record and verify 112 source/configuration/fixture hashes. Publication metadata was corrected after the first live checks; [26-metadata-live-smoke.txt](26-metadata-live-smoke.txt) and [27-live-cli.txt](27-live-cli.txt) capture the accepted behavior. Hosted CI was not executed as part of this local verification.
