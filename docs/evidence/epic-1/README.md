# EPIC-1 execution evidence

These files contain actual combined stdout/stderr from local commands run on 2026-09-30 in America/Costa_Rica. A temporary recorder wrote the command, working directory, unedited output, and exit status to each transcript. [commands.jsonl](commands.jsonl) records command strings, completion timestamps in UTC, expected/actual exit codes, durations, and log filenames. A UTC date of 2026-10-01 in the manifest corresponds to the late evening of 2026-09-30 in Costa Rica.

Every recorded outer command exited 0. The rejection demos intentionally run failing subcommands and return 0 only if their exit status is exactly 1 and the restored checks pass. Temporary paths in transcripts belong to disposable verification directories, which have been removed.

The implementation baseline was committed as `72d2751dda03f49c3ae3bf6b01819bbfad4d1500`. The later documentation commit preserves this evidence, marks the epic done, allows the evidence coverage XML through `.gitignore`, and extends the demo script to exercise format/coverage commit rejection. [verification.json](verification.json) records the verified versions, coverage totals, and current source hashes. Use [EPIC-1-RUNBOOK.md](../../../EPIC-1-RUNBOOK.md) for the PM walkthrough and reproduction commands.

| Evidence | Recorded command / result |
| --- | --- |
| [01](01-git-init.txt) | `git init -b main` |
| [02](02-uv-init.txt) | Initialize the uv project on Python >=3.12 |
| [03](03-python-pin.txt) | `uv python pin 3.12` |
| [04](04-runtime-dependencies.txt) | Add/install the five required runtime dependencies |
| [05](05-dev-dependencies.txt) | Add/install pinned Ruff/mypy and test/hook tooling |
| [06](06-setup.txt) | `make setup`: locked environment and installed Git hook |
| [07](07-quality-check.txt) | `make check`: lint/format/typing/tests; 48 passed, 100% coverage |
| [08](08-build.txt) | `make build`: source distribution and wheel |
| [09](09-secret-ignore.txt) | `git check-ignore`: local credentials, runs, and generated files ignored |
| [10](10-pre-commit.txt) | `make hooks`: all four hooks pass |
| [11](11-foundation-demo.txt) | `make demo`: installed versions, boundary and quality checks |
| [12](12-wheel-install.txt) | Wheel installed/imported outside the checkout |
| [13](13-implementation-commit.txt) | Successful implementation commit with actual hooks running |
| [14](14-gate-rejection-demo.txt) | Initial nine rejection probes and passing restoration |
| [15](15-fresh-checkout.txt) | Fresh committed checkout: setup/demo/hooks/build pass |
| [16](16-uv-sync.txt) | Acceptance command `uv sync` succeeds |
| [17](17-uv-version.txt) | uv 0.11.14 |
| [18](18-python-install.txt) | Successful `uv python install 3.12` |
| [19](19-all-hook-rejections.txt) | Eleven rejection probes, including real commit rejection for every hook |
| [coverage.xml](coverage.xml) | Snapshot of 47 covered statements and 18 covered branches |
| [verification.json](verification.json) | Versions, acceptance results, and source SHA-256 hashes |

Hosted GitHub Actions was configured but not run; no remote repository was supplied. These are local results. The 100% coverage result covers the foundation checker and scaffold, not pipeline functionality from future epics.
