"""Explicit, credential-safe live acceptance check; excluded from offline tests."""

import json
import sys
from typing import Literal

from pydantic import ValidationError

from schemas.common import Contract
from schemas.config import AGENT_NAMES, PRODUCTION_MODEL, RunSettings
from services.llm_service import LLMService, MissingOpenRouterKey


class FoundationPing(Contract):
    """Acknowledge readiness of the EPIC-2 typed tool interface."""

    value: Literal["EPIC-2-ready"]


def main() -> int:
    try:
        settings = RunSettings(model_max_retries=0, model_timeout_seconds=30)
        if any(settings.models.for_agent(agent) != PRODUCTION_MODEL for agent in AGENT_NAMES):
            raise ValueError(
                "Live production acceptance requires the specified production model for every agent"
            )
        model = LLMService(settings).for_agent("orchestrator")
        response = model.bind_tools([FoundationPing], tool_choice="FoundationPing").invoke(
            "Call FoundationPing exactly once with value EPIC-2-ready.",
            max_tokens=128,
            retries=None,
        )
        if len(response.tool_calls) != 1:
            raise ValueError("Expected exactly one tool call")
        call = response.tool_calls[0]
        if call["name"] != "FoundationPing" or not call.get("id"):
            raise ValueError("Expected a named FoundationPing call with a call id")
        arguments = FoundationPing.model_validate(call["args"])
        print(
            json.dumps(
                {
                    "status": "passed",
                    "model": PRODUCTION_MODEL,
                    "tool": call["name"],
                    "arguments": arguments.model_dump(),
                    "provider_preferences": {"require_parameters": True, "data_collection": "deny"},
                    "usage": response.usage_metadata,
                },
                indent=2,
            )
        )
        return 0
    except MissingOpenRouterKey:
        print(
            "Live acceptance pending: set OPENROUTER_API_KEY in the environment or local .env.",
            file=sys.stderr,
        )
        return 2
    except (ValidationError, ValueError) as error:
        print(
            f"Live acceptance failed: {type(error).__name__}; "
            "inspect local settings or returned tool call.",
            file=sys.stderr,
        )
        return 1
    except Exception as error:  # noqa: BLE001 - report only the type, never the body
        # Never print provider exception bodies, headers, keys, or credential-bearing tracebacks.
        print(
            f"Live acceptance failed: {type(error).__name__} from the provider request.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
