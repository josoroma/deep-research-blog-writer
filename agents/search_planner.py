"""The orchestrator derives typed variants through the central model service."""

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import ValidationError

from prompts.catalog import load_prompt
from schemas.errors import ContractViolationError
from schemas.requests import ResearchRequest
from schemas.search import QueryVariants
from services.llm_service import LLMService


class SearchPlanningError(ContractViolationError, ValueError):
    """The planner exhausted its one validation-repair attempt."""

    code = "search_planning_failed"


def derive_query_variants(
    request: ResearchRequest, llm: LLMService, *, config: RunnableConfig | None = None
) -> QueryVariants:
    model = llm.for_agent("orchestrator").with_structured_output(QueryVariants)
    messages: list[BaseMessage] = [
        SystemMessage(content=load_prompt("orchestrator")),
        HumanMessage(
            content=f"Derive search-query variants for this request: {request.model_dump_json()}"
        ),
    ]
    for attempt in range(2):
        try:
            variants = QueryVariants.model_validate(model.invoke(messages, config=config))
            if any(query.casefold() == request.topic.casefold() for query in variants.variants):
                raise SearchPlanningError("variants must differ from the topic")
            return variants
        except (ValidationError, SearchPlanningError):
            if attempt == 1:
                raise SearchPlanningError(
                    "Could not derive valid query variants after two attempts"
                ) from None
            messages.append(
                HumanMessage(
                    content="The previous plan failed validation. Revise it for the same request."
                )
            )
    raise AssertionError("unreachable")  # pragma: no cover
