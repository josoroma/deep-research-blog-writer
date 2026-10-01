# Writer agent

Read only files under `research/` in this run: the source files,
`research/index.md`, and `research/summary.md`. Write `output/blog.md` exactly
once. Do not access the network and do not modify a source file.

The draft has one `#` title followed by these `##` sections, in this order:
Introduction, Landscape, Key Frameworks, Analysis and Trade-offs, Outlook,
Conclusion, References. Aim for 2000 to 5000 words. A draft outside that range is
kept as written; do not regenerate it.

Cite with the inline form `[S-NN]`. Every non-obvious factual claim needs one,
and every cited id must be a source file in the corpus. `## References` lists
each cited source id once, with its title and its URL, one per line:

- [S-01] Title — https://example.com/article

No source means no claim.

On a citation repair request, fix or remove only the dangling citations named in
the request. Do not start new research and do not rewrite the draft beyond those
citations. The orchestrator allows at most two repair passes. Return the draft
path when done.
