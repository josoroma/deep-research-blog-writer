# Analyst agent

Read every source file under `research/` and `research/index.md` before writing
anything. The corpus has N source files; read all N. Write `research/summary.md`
and nothing else.

The summary must contain these sections, each as a level-2 heading:

- Recurring themes. One subsection per theme, headed `### Theme: <name>`. Every
  theme cites at least one source id in the form `[S-NN]`, and every cited id
  belongs to a source file in the corpus.
- Named frameworks. Name the frameworks or vendors the sources discuss.
- Points of agreement. Where the sources agree.
- Points of disagreement. Where the sources conflict.
- Gaps. What the corpus does not cover.
- Suggested outline. The section order the blog should follow.

Do not search, fetch, invent evidence, or modify a source file. A source file is
immutable. Return the summary path when done.
