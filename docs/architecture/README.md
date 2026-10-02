# Agent architecture

Human documentation for the orchestrator and its four sub-agents (PD-005, PD-022). Each agent has a `skill.md` describing what it does and a `contract.md` describing what it must consume, produce, and satisfy.

These files are documentation, not runtime skills. The agents load their prompts from `prompts/` through the catalog; nothing here is loaded at run time.

| Agent | Role | Tools | Documentation |
| --- | --- | --- | --- |
| orchestrator | Coordinates the nine phases and owns the run state | `plan_search`, `normalize_results`, `build_index`, `validate_citations`, `write_run_report` | [skill](agents/orchestrator/skill.md) · [contract](agents/orchestrator/contract.md) |
| search_agent | Runs paged searches and collects candidate URLs | `google_search` | [skill](agents/search_agent/skill.md) · [contract](agents/search_agent/contract.md) |
| research_agent | Fetches each clean URL and writes one immutable source file | `collect_source` | [skill](agents/research_agent/skill.md) · [contract](agents/research_agent/contract.md) |
| analyst_agent | Synthesizes the corpus into themes and an outline | filesystem tools only | [skill](agents/analyst_agent/skill.md) · [contract](agents/analyst_agent/contract.md) |
| writer_agent | Drafts the cited blog from the corpus and summary | filesystem tools only | [skill](agents/writer_agent/skill.md) · [contract](agents/writer_agent/contract.md) |

## How the pieces fit

- **Agents orchestrate; tools execute (BR-001).** An agent decides which tool to call; the tool performs the I/O and returns a typed contract. Agents never fetch a URL or construct a provider client.
- **Prompts come from the catalog.** `prompts/catalog.py` loads the packaged prompt for each agent. `evaluations/agent_architecture.py` fails the build if an agent module builds a provider client or inlines a prompt.
- **HTTP stays in services.** `evaluations/agent_boundary.py` fails the build if an agent module imports an HTTP client.
- **State is typed.** `RunState` carries the run's progress; a state-changing tool returns a `RunStateUpdate`, which the registry adapter converts to a framework `Command`.
- **Sources are immutable.** `research/NNN_<slug>.md` is written once and never overwritten (BR-003).

## Related documents

- [Product decisions PD-005 and PD-022](../../SPECS.md#product-decisions) — the agent set and this documentation format.
- [ADR 0001: DeepAgents on LangGraph](../adr/0001-deepagents-on-langgraph.md) — the framework choice.
- [ADR 0004: Disable the general-purpose sub-agent](../adr/0004-disable-general-purpose-subagent.md) — why only four sub-agents exist.
- [PRD.md §9](../../PRD.md) — the sub-agent and tool table this documentation expands.
