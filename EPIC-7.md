# EPIC-7: Synthesis and Blog Authoring

Date: 2026-10-01

Status: Planned. This plan is written before implementation. Successful commands and PM evidence will be recorded in `EPIC-7-RUNBOOK.md` and `docs/evidence/epic-7/` after verification.

## Objective

Implement US-7.1–US-7.4 from [SPECS.md](SPECS.md#epic-7-synthesis-and-blog-authoring), building on the completed EPIC-6 corpus. Distill the corpus into `research/summary.md`, write one cited `output/blog.md` in the fixed PD-015 structure, prove every `[S-NN]` resolves to a source file, and repair dangling citations within two passes. A draft outside 2000–5000 words is kept and recorded as `blog_length`; a draft that still dangles after two repairs fails as `dangling_citations` and keeps the last draft.

Run reporting, outcome classification, and durable resume stay in EPIC-8. Scoring "every non-obvious claim carries a citation" stays in US-10.4. This milestone produces the summary, the draft, and the citation gate.

## Current baseline

- `prompts/analyst_agent.md` and `prompts/writer_agent.md` already state the FR-7 contents, the PD-015 headings, the length range, and the citation rules. They are short. The acceptance scenarios need the required sections and the `[S-NN]` form spelled out so a model cannot miss them.
- `analyst_agent` and `writer_agent` already receive no application tools (`agents/deep_research.py`). Both reach the corpus through the shared `ImmutableSourceBackend`, which allows reads everywhere and writes to `research/summary.md` and `output/` while refusing overwrites of `research/NNN_<slug>.md`. US-7.1#2 and US-7.2#3 are therefore already satisfied by the EPIC-6 backend; this milestone proves them rather than re-wiring them.
- `validate_citations` is a labelled stub in `tools/stubs.py` returning zero citations checked. `ValidateCitationsOutput` already carries `citations_checked` and `dangling_source_ids`, but it cannot report a References mismatch or update run state.
- `Phase` already enumerates `synthesize`, `write`, and `citations`. Nothing records them, and nothing checks blog structure or length.
- `workflows/corpus_run.py` writes the corpus and `corpus_state.json` and stops. No workflow reads the corpus to write a summary or a blog.
- The offline suite blocks sockets and drives agents with `ScriptedChatModel` (`evaluations/fakes.py`), which records the tool names bound per call. That is how this milestone proves what each agent may do without a live model.

## Implementation sequence

1. **Contracts.**
   - Extend `ValidateCitationsOutput` with `mismatched_source_ids` and make it a `RunStateUpdate`, mirroring `BuildIndexOutput`. The stub keeps its own output model so the skeleton registry still builds.
   - Add a `BlogCheck` contract: `word_count`, `headings_valid`, `within_length`, and `reason`. `reason` is `blog_length` when the draft is outside 2000–5000 words and `None` otherwise. The draft is never regenerated because of length (NFR-4, PD-015).
   - Add a `CitationFinding` contract: `citations_checked`, `dangling_source_ids`, `mismatched_source_ids`, and `passed`. `passed` is true only when both lists are empty.
   - Add a `AuthoringSummary` contract for the milestone: summary path, blog path, word count, citation counts, repair passes used, status (`completed` or `failed`), and reason (`blog_length`, `dangling_citations`, or `None`).

2. **US-7.1: Analyst prompt and summary check** (`services/authoring.py`).
   - Rewrite `prompts/analyst_agent.md` so it names the required contents: recurring themes, named frameworks or vendors, points of agreement, points of disagreement, gaps, and a suggested outline. Require every theme to cite at least one `[S-NN]` that exists in the corpus, and require reading every source file plus `research/index.md` before writing `research/summary.md`.
   - `check_summary(root)` reads `research/summary.md` and the corpus. It fails when any required section is missing, when a theme cites no source, or when a cited source id is not in the corpus. It returns the source ids the summary actually references.
   - The analyst's write access is the existing backend. A test drives the built agent with a scripted `write_file` of `research/summary.md` and asserts the file lands, while a `write_file` of a source file is still refused.

3. **US-7.2: Writer prompt, structure, and length.**
   - Rewrite `prompts/writer_agent.md` with the PD-015 headings in order, the 2000–5000 word range, the inline `[S-NN]` form, and the References rule: every cited source id listed once with its title and URL. State that the draft is written once and that a repair request only fixes or drops the named dangling citations.
   - `check_blog(root)` parses `output/blog.md`. It requires one `#` title followed by `## Introduction`, `## Landscape`, `## Key Frameworks`, `## Analysis and Trade-offs`, `## Outlook`, `## Conclusion`, and `## References`, in that order, and counts words. A draft outside the range is kept; the returned `BlogCheck.reason` is `blog_length`.
   - The writer reads only `research/` because that is all the material the prompt allows, and the backend is rooted at the run workspace (`virtual_mode=True`), so no path escapes it. A test asserts the writer's bound tools contain no network tool and no `collect_source`.

4. **US-7.3: `validate_citations`.**
   - Implement the check in `services/authoring.py` over `output/blog.md` and the corpus front-matter. Collect every `[S-NN]`, count them, and report any id with no source file as dangling. Report a cited id missing from `## References`, or listed there with a URL other than its source file's URL, as mismatched.
   - Register `validate_citations` through `create_tool_registry` when an authoring session is bound, replacing the stub the way `build_index` replaced its stub. It returns the finding and records the `citations` phase only when validation passes. A failing validation still returns a validated result; it does not raise, so the repair loop can run.
   - Tests cover a fully resolved draft, a dangling `S-31`, a cited id missing from References, and a References entry whose URL differs from the source file.

5. **US-7.4: The citation gate.**
   - `run_authoring` validates, and on failure re-invokes the writer with the dangling and mismatched ids, then validates again. It stops after 2 repair passes (PD-016). Each pass is counted; the original generation is not.
   - When dangling citations remain, the run ends `failed` with reason `dangling_citations`, `output/blog.md` keeps the last draft, and `output/run.json` lists the dangling source ids. This file is the citation-gate record; the full FR-10 run report stays in US-8.1.
   - A clean draft records the `citations` phase and proceeds. The milestone stops there; it does not write the EPIC-8 report.

6. **Runnable authoring milestone and demo.**
   - Add `--author-only --workspace <corpus-run>` to `deep-research-blog`. It reads the corpus and runs the analyst and writer through the registered tools and the configured model, then runs the citation gate, and prints the `AuthoringSummary`. Exit 0 means the gate passed, including a `blog_length` draft; exit 1 means `dangling_citations` or a fatal error; exit 2 rejects a workspace that has no corpus.
   - The offline demo does not call a model. `evaluations/epic7_demo.py` builds a corpus from the EPIC-6 fixtures, writes a summary and a blog with a scripted agent, and runs the real `validate_citations` plus the repair loop against drafts that dangle once and then resolve. It asserts the headings, the citation form, the References match, the refused source overwrite, and the two-pass failure path.
   - Add `scripts/inspect-authoring.py` to validate a workspace: summary sections, blog headings and word count, and citation findings that match `output/run.json`.

7. **Verification and delivery.**
   - Test the summary check, the blog structure and length check, resolved, dangling, and mismatched citations, the repair loop boundary, and the writer's tool boundary.
   - Keep the offline suite network-blocked. No live model call is required for acceptance; a live authoring smoke stays opt-in behind `OPENROUTER_API_KEY` and out of the coverage gate.
   - Run locked setup, strict quality and coverage checks, hooks, the EPIC-2 through EPIC-6 demos, the new demo, the wheel and sdist build, an installed-wheel check, and a committed fresh-checkout verification.
   - Record transcripts, timestamps, the offline snapshot, coverage, and source hashes under `docs/evidence/epic-7/`. Write `EPIC-7-RUNBOOK.md`.
   - Update only the verified EPIC-7 story and task statuses in `SPECS.md`, and commit with hooks active.

## Acceptance matrix

| Story | Evidence |
| --- | --- |
| US-7.1 | `research/summary.md` has themes, named frameworks, agreement, disagreement, gaps, and an outline; every theme cites a `source_id` present in the corpus |
| US-7.1 | The analyst run reads every source file; a scripted run that skips one fails `check_summary` |
| US-7.2 | `output/blog.md` carries the seven `##` headings in order after one `#` title, and citations use `[S-NN]` |
| US-7.2 | A 1999-word draft is kept, not regenerated, and the run records `blog_length` |
| US-7.2 | The writer is offered no network tool and no `collect_source`; its backend is rooted at the run workspace |
| US-7.3 | A draft whose every `[S-NN]` matches a source file passes and reports the count |
| US-7.3 | A draft citing `[S-31]` with no such source fails and reports `S-31` dangling |
| US-7.3 | A cited id missing from `## References`, or listed with a different URL, fails and reports the mismatch |
| US-7.4 | One dangling id triggers a writer repair and a second validation, and a clean result passes |
| US-7.4 | Dangling ids remaining after 2 repair passes end the run `failed` with `dangling_citations`; the last draft stays and `output/run.json` lists the ids |

## Completion checklist

- [ ] Analyst and writer prompts rewritten against the acceptance scenarios.
- [ ] Summary, structure, and length checks implemented.
- [ ] `validate_citations` implemented and registered.
- [ ] Citation repair loop capped at 2 passes.
- [ ] Author-only workflow and offline demo pass.
- [ ] Strict gates, hooks, prior demos, installed wheel, and fresh checkout pass.
- [ ] Runbook, transcripts, snapshot, coverage, and source hashes saved.
- [ ] Implementation and evidence committed.

## Scope boundaries

- `output/run.json` here records only the citation-gate outcome. The full run report (timings, token totals, URL counts) is US-8.1.
- Status classification (`succeeded`, `degraded`, `failed`) beyond the citation gate is US-8.2. This milestone records `blog_length` and `dangling_citations` as reasons; it does not decide the run's final status.
- Whether every non-obvious claim carries a citation is scored by US-10.4, not enforced here.
- No new ADR. The writer and analyst share the EPIC-6 backend, and the citation gate is a tool plus a bounded loop, not a new architecture.

## Technical references

- [SPECS.md](SPECS.md#epic-7-synthesis-and-blog-authoring) US-7.1 to US-7.4.
- [PRD.md](PRD.md) FR-7, FR-8, FR-9, and NFR-4.
- PD-015 and PD-016 in [SPECS.md](SPECS.md).
