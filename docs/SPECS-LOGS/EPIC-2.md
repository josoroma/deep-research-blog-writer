# EPIC-2: Contracts and Agent Building Blocks

Date: 2026-10-01

Status: DONE. All six stories, the live tool call, and fresh-checkout verification passed. Implementation commit: `f13077a`. Commands and acceptance evidence are in [EPIC-2-RUNBOOK.md](EPIC-2-RUNBOOK.md).

## Objective and scope

Implement US-2.1 through US-2.6 from [SPECS.md](../../SPECS.md#epic-2-contracts-and-agent-building-blocks), building on the committed EPIC-1 foundation. Deliver validated pipeline contracts, explicit checkpointable state, a nonempty typed tool registry, packaged prompts for all five agents, an injectable OpenRouter model service, and a separate live tool-calling smoke test.

Keep agent assembly, real search/extraction, the research CLI, and the per-run SQLite workspace lifecycle in their later epics. Verify the building blocks through real LangGraph state/checkpoint and ToolNode integration, without pretending the blog pipeline already exists.

## Implementation sequence

1. **US-2.1 — Contracts and settings.** Add `schemas/requests.py`, `schemas/responses.py`, and `schemas/config.py`. Trim topics before enforcing 3–250 characters; default pages/per_page/max_urls to 3/10/30. Include the PRD's SearchResult, FetchedPage, Source, and RunReport fields. Validate budgets, URLs, counts, and types. Reject unknown contract fields. Add `pydantic-settings` as a direct dependency; load settings from environment and `.env`, protect credentials with `SecretStr`, and expose independently configurable model IDs for all five agents. Preserve the OpenRouter-qualified production default from US-2.6, stripping only the provider prefix when constructing ChatOpenRouter.
2. **US-2.2 — Explicit state.** Define RunState with topic, completed phases, clean results, and typed URL outcomes. Define a DeepAgentState subclass with RunState under `run`. Validate replacements rather than trusting Pydantic `model_copy(update=...)`, which does not revalidate values. Add a deterministic state-changing tool that reads `runtime.state` and returns a validated model. Adapt it to LangGraph Command updates at the framework boundary. Prove state round-trip through a real compiled LangGraph and checkpointer, including nested URL outcome models.
3. **US-2.3 — Typed registry.** Implement a reusable typed tool definition/registry with explicit Pydantic input and output classes. Validate registration and both sides of invocation. Reject raw dictionaries and wrongly typed or corrupted model outputs. Expose LangChain-compatible tool adapters without allowing the runtime context to appear in model-facing input schemas. Register the state-changing building block and prove execution through a real ToolNode. Do not register pretend implementations of later pipeline tools.
4. **US-2.4 — Prompt catalog and architecture checks.** Store one Markdown prompt per orchestrator/search/research/analyst/writer agent. Load resources by an allowlisted agent name using `importlib.resources`, so installed wheels work outside the checkout. Transfer the skill's operating rules and workflow into the orchestrator prompt, applying governing product decisions (PD-005 tool assignment, two citation repairs, specified headings). Never load SKILL.md as a runtime skill. Add recursive AST checks and regression tests against inline system prompts and provider-client construction/imports in agent modules, alongside EPIC-1's HTTP boundary.
5. **US-2.5 — LLM service.** Construct ChatOpenRouter centrally for each configured agent, with `openrouter_provider={"require_parameters": true, "data_collection": "deny"}` on every request. Support injected fake BaseChatModel instances without requiring credentials. Test actual outgoing SDK request parameters with a stub transport/client; no live calls in unit tests. Fail clearly for missing keys, invalid provider-prefixed IDs, or unknown agent names.
6. **US-2.6 — Production model and smoke test.** Record ADR 0002 for OpenRouter and DeepSeek V4.1 Flash. Default every agent to `openrouter:deepseek/deepseek-v4.1-flash`. Add an explicit live smoke command/test outside the offline suite that forces a small typed tool call, validates the response, uses a bounded request with retries disabled, and emits credential-safe evidence. Run it when a valid local OPENROUTER_API_KEY is available. A missing key or failed provider response is pending live acceptance, never a successful live test.
7. **Verify and deliver.** Keep Ruff 0.13.0, mypy 1.18.1, and the >=80% coverage floor. Add meaningful tests for invalid hand-offs, settings precedence, model selection/preferences, registry errors, state validation/checkpoint restoration, prompt packaging, and architecture rejection. Run setup, all quality gates/hooks, an offline `make demo-epic-2`, build, and installed-wheel verification. Record commands, real outputs, exit statuses, coverage XML, and source hashes under `docs/evidence/epic-2/`. Create `EPIC-2-RUNBOOK.md` with setup, demonstrations, negative examples, and an acceptance matrix. Commit the implementation and lockfile with hooks active; update only verified EPIC-2 statuses in SPECS.md.

## Acceptance and evidence matrix

| Story | Acceptance evidence |
| --- | --- |
| US-2.1 | Valid trimmed request/defaults; field-named rejection for invalid topics/config; all PRD hand-off fields present |
| US-2.2 | DeepAgentState subclass annotation; malformed replacement rejected; real checkpoint retains RunState and nested outcomes |
| US-2.3 | Nonempty TOOLS mapping; Pydantic input/output on every entry; bad inputs, missing contracts, and raw-dict output rejected; real ToolNode execution |
| US-2.4 | All five resource files load; orchestrator contains skill rules/workflow with governing decisions; inline prompt rejected in a nested agent module; wheel resources present |
| US-2.5 | All agents resolve configured models; captured SDK request carries required provider preferences; fake injection avoids credentials; direct provider construction rejected |
| US-2.6 | All five defaults exactly match the specified production ID; ADR 0002; valid live tool call when a key is available |

## Demo and evidence of done

- Run `make setup`, `make check`, and `make hooks` to show the reproducible locked environment and retained EPIC-1 gates.
- Run `make demo-epic-2` to show typed requests, rejection cases, a registered tool updating real graph state, checkpoint restoration, five packaged prompts, production model routing/preferences, and fake injection without provider calls.
- Run the installed-wheel verifier to show the contracts and prompts work outside the repository.
- With a configured local key, run `make smoke-epic-2` to demonstrate the selected production model's live tool call. Record its actual result separately from offline checks.
- Show the runbook's story-by-story acceptance matrix and raw evidence. If live credentials are unavailable, leave that acceptance criterion and the epic's full acceptance status pending explicitly.

## Completion checklist

- [x] US-2.1 implemented and verified.
- [x] US-2.2 implemented and verified.
- [x] US-2.3 implemented and verified.
- [x] US-2.4 implemented and verified.
- [x] US-2.5 implemented and verified.
- [x] US-2.6 code/defaults/ADR complete; live tool call verified.
- [x] Locked setup, strict quality checks/hooks, offline demo, build, and installed-wheel check pass.
- [x] Runbook, raw command transcripts, coverage, and source hashes saved.
- [x] Implementation/lockfile committed with hooks active; final evidence committed separately.

## References

The product decisions and acceptance criteria in SPECS.md govern scope. Integration details are checked against the installed locked packages and official documentation for [ChatOpenRouter](https://docs.langchain.com/oss/python/integrations/chat/openrouter), [LangChain tool runtime/state updates](https://docs.langchain.com/oss/python/langchain/tools), [OpenRouter provider routing](https://openrouter.ai/docs/guides/routing/provider-selection), and [Pydantic settings](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/).
