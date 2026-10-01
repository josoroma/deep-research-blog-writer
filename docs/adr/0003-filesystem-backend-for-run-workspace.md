# 0003: Persist the run workspace to local disk with FilesystemBackend

Date: 2026-10-01

Status: Accepted

## Context

[PRD.md §12](../../PRD.md#12-open-decisions) leaves the deep agent's filesystem backend open and recommends a real-disk backend. [SPECS.md PD-007](../../SPECS.md#pd-007--real-disk-workspace) requires `FilesystemBackend(root_dir="runs/<run_id>/", virtual_mode=True)`. The project brief expects the corpus and blog to be readable locally once a run finishes, and [BR-006](../../SPECS.md#br-006--the-run-workspace-holds-every-artifact) requires every artifact under `runs/<run_id>/`.

DeepAgents 0.7 offers a `StateBackend` that keeps files in graph state and a `FilesystemBackend` that writes to disk. The choice affects when files become visible, how a run is inspected, and whether a path can escape the workspace.

## Decision

Configure the deep agent with `FilesystemBackend(root_dir=<runs/<run_id>>, virtual_mode=True)`.

- Each `write_file` reaches disk immediately, so a run's artifacts survive the process and can be opened with any editor.
- `virtual_mode=True` treats incoming paths as virtual absolute paths under the root. It rejects `..` and `~`, and it refuses any resolved path outside the root, including symlink escapes.
- The root is the run's own workspace, so one run cannot read or write another run's files.

## Consequences

### Pros

- Artifacts are inspectable and durable without a separate export step.
- Path containment is enforced by the backend, satisfying PD-007 and BR-006.
- The same backend serves the orchestrator and every sub-agent, so all agents share one workspace view.
- A later move to a server can swap the backend without changing agent code.

### Cons

- Writes touch the host filesystem, so a run needs a writable `runs/` directory.
- `virtual_mode` is path containment, not a sandbox; it does not isolate the process.
- Concurrent runs rely on distinct run ids rather than a lock.
- The backend does not enforce source immutability; US-6.1#4 adds that rule.
