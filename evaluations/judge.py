"""The claim-level groundedness judge (US-10.4, PD-021).

The judge asks a model whether each factual claim is supported by the source it
cites. It defaults to DeepSeek V4.1 Flash on OpenRouter, the same model the agents
use. Tests inject a fake judge, so the offline suite never calls a provider.
"""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field

from evaluations.scoring import ClaimVerdict
from schemas.config import RunSettings
from services.llm_service import LLMService

SYSTEM_PROMPT = (
    "You are a strict fact-checking judge. For each claim, decide whether the cited "
    "source supports it. Answer only with the structured verdicts."
)


class Verdict(BaseModel):
    """One judge decision, matched back to its claim by index."""

    model_config = ConfigDict(extra="forbid", strict=True)

    index: int = Field(ge=0)
    supported: bool


class Verdicts(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    verdicts: list[Verdict] = Field(default_factory=list)


class ModelJudge:
    """Judge claims with a chat model through the central LLM service."""

    def __init__(self, settings: RunSettings, *, model: BaseChatModel | None = None) -> None:
        self.settings = settings
        self.model = model

    def _chat(self) -> BaseChatModel:
        if self.model is not None:
            return self.model
        return LLMService(self.settings).for_agent("orchestrator")

    def judge(self, claims: Sequence[ClaimVerdict]) -> list[ClaimVerdict]:
        if not claims:
            return []
        numbered = "\n".join(
            f"{index}. [{item.source_id or 'uncited'}] {item.claim}"
            for index, item in enumerate(claims)
        )
        structured = self._chat().with_structured_output(Verdicts)
        result = structured.invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=f"Judge these claims:\n{numbered}"),
            ]
        )
        verdicts = Verdicts.model_validate(result)
        supported = {item.index: item.supported for item in verdicts.verdicts}
        return [
            item.model_copy(update={"supported": supported.get(index, False)})
            for index, item in enumerate(claims)
        ]


class AlwaysSupportedJudge:
    """Offline judge that accepts every claim; used by the demo and tests."""

    def judge(self, claims: Sequence[ClaimVerdict]) -> list[ClaimVerdict]:
        return [item.model_copy(update={"supported": True}) for item in claims]
