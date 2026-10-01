"""Shared validation rules for pipeline hand-offs."""

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, HttpUrl, PlainSerializer


class Contract(BaseModel):
    """Strict, revalidated contracts; tools cannot silently coerce bad payloads."""

    model_config = ConfigDict(
        extra="forbid", strict=True, revalidate_instances="always", validate_assignment=True
    )


def trim_topic(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


Topic = Annotated[str, BeforeValidator(trim_topic), Field(min_length=3, max_length=250)]
# JSON-safe dumps also let LangGraph's msgpack serializer preserve URL-bearing models.
HTTPURL = Annotated[HttpUrl, PlainSerializer(str, return_type=str)]
SourceID = Annotated[str, Field(pattern=r"^S-[0-9]{2,}$")]
Phase = Literal[
    "plan", "search", "normalize", "fetch", "index", "synthesize", "write", "citations", "report"
]
