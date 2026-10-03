# 0011: Artifact ownership and bounded read access

Date: 2026-10-02
Status: Accepted

## Context

The HTTP API exposes run status, reports, artifacts, and logs. The plan forbids
mounting all of `runs/` as static files and requires that provider secrets, raw
HTML caches, and checkpoint databases are not downloadable. Client input must
never be joined directly onto a path, and symlinks must not be followed out of
the workspace.

## Decision

A single `ArtifactReader` owns every filesystem read. Run IDs resolve to a
directory under the configured workspace root with containment enforced before
any read. Artifact download IDs are resolved through a server-side allowlist of
paths (`output/`, `research/`, `logs/`, and named state files); appears outside
the allowlist returns `404`. Symlinks at any path level are rejected rather than
followed, and each resolved path is re-checked for containment.

Log reads are paged and bounded, and each JSON Lines record is projected onto a
small public shape (timestamp, level, phase, event, and non-reserved fields).
Markdown downloads are served as attachments. Raw HTML caches, checkpoint
databases, and the ownership lock are excluded from the allowlist.

## Consequences

### Pros

- A traversal or symlink escape is rejected before any bytes are read.
- Secrets and raw caches cannot be downloaded even if they appear in a run.

### Cons

- New artifact locations must be added to the allowlist deliberately.
- Artifact size limits apply to downloads; an unusually large report is refused
  rather than streamed.
