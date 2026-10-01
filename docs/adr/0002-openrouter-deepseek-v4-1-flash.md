# 0002: Use OpenRouter with DeepSeek V4.1 Flash for every agent

Date: 2026-10-01

Status: Accepted; live tool-calling acceptance passed on 2026-10-01 ([recorded result](../evidence/epic-2/02-live-smoke.txt)).

## Context

[PRD.md §12](../../PRD.md#12-open-decisions) and [SPECS.md PD-002](../../SPECS.md#pd-002--openrouter-with-deepseek-v41-flash) select DeepSeek V4.1 Flash through OpenRouter for the orchestrator, search, research, analyst, and writer agents. Each agent needs tool calling, configurable model selection, and offline fake injection without provider access in unit tests.

## Decision

Set all five production defaults to `openrouter:deepseek/deepseek-v4.1-flash`. Resolve each through `services/llm_service.py` using `langchain-openrouter`'s ChatOpenRouter. Preserve the qualified ID in configuration and pass `deepseek/deepseek-v4.1-flash` to the provider client. Configure models per agent through `MODELS__<AGENT>` environment or .env values.

Every client supplies `openrouter_provider={"require_parameters": true, "data_collection": "deny"}`. Store keys as SecretStr and load OPENROUTER_API_KEY locally. Tests inject a fake BaseChatModel or stub the SDK request; an explicit, separate production smoke command forces and validates one typed tool call. A mocked request or missing key does not establish live model acceptance.

Integration uses the [official ChatOpenRouter API](https://docs.langchain.com/oss/python/integrations/chat/openrouter) and [OpenRouter provider routing preferences](https://openrouter.ai/docs/guides/routing/provider-selection). Their semantics are checked against the locked installed integration. The separate live check returned a valid `FoundationPing(value="EPIC-2-ready")` call using 391 tokens.

## Consequences

### Pros

- One provider service centralizes model selection, credentials, and request preferences.
- Per-agent overrides change models without changing agent code.
- Routing requires parameter support and excludes providers permitting data collection.
- Offline fake injection makes validation and state/tool integration reproducible without model spend.

### Cons

- Live execution depends on OpenRouter credentials, credit, provider availability, and tool support.
- Required routing preferences may reduce the set of eligible providers.
- A pinned model ID does not pin backend weights or guarantee deterministic provider behavior.
- Real tool-calling capability needs the separate smoke acceptance test and recorded evidence.
