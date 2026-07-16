from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel, ValidationError

from app.agents.model_factory import parse_json_object

logger = logging.getLogger("tradepilot.agent.structured_output")


@dataclass(frozen=True, slots=True)
class StructuredOutputResult[OutputT: BaseModel]:
    value: OutputT
    model_call_count: int
    parse_retry_count: int
    token_usage: dict[str, int] | None = None
    parser_name: str = "PydanticOutputParser"


def invoke_structured[OutputT: BaseModel](
    *,
    prompt: Runnable[Any, Any],
    model: Runnable[Any, Any],
    values: Mapping[str, Any],
    output_model: type[OutputT],
    normalize: Callable[[dict[str, Any]], OutputT | dict[str, Any]],
    max_parse_retries: int,
) -> StructuredOutputResult[OutputT]:
    """Invoke one typed LCEL chain and retry only malformed JSON/schema output."""
    parser = PydanticOutputParser(pydantic_object=output_model)
    token_usage: dict[str, int] = {}

    def capture_usage(message: object) -> object:
        usage = getattr(message, "usage_metadata", None)
        if not isinstance(usage, dict):
            metadata = getattr(message, "response_metadata", None)
            usage = metadata.get("token_usage") if isinstance(metadata, dict) else None
        if isinstance(usage, dict):
            aliases = {
                "prompt_tokens": "input_tokens",
                "completion_tokens": "output_tokens",
                "input_tokens": "input_tokens",
                "output_tokens": "output_tokens",
                "total_tokens": "total_tokens",
            }
            for source, target in aliases.items():
                value = usage.get(source)
                if isinstance(value, int):
                    token_usage[target] = token_usage.get(target, 0) + value
        return message

    def decode_and_normalize(message: object) -> OutputT | dict[str, Any]:
        content = getattr(message, "content", message)
        return normalize(parse_json_object(str(content)))

    def serialize(value: OutputT | dict[str, Any]) -> str:
        if isinstance(value, BaseModel):
            return value.model_dump_json()
        return json.dumps(value, ensure_ascii=False)

    chain = (
        prompt
        | model
        | RunnableLambda(capture_usage)
        | RunnableLambda(decode_and_normalize)
        | RunnableLambda(serialize)
        | parser
    )
    retryable = (OutputParserException, ValidationError, ValueError)
    for attempt in range(max_parse_retries + 1):
        try:
            value = chain.invoke(dict(values))
            return StructuredOutputResult(
                value=value,
                model_call_count=attempt + 1,
                parse_retry_count=attempt,
                token_usage=token_usage or None,
            )
        except retryable as exc:
            if attempt >= max_parse_retries:
                raise
            logger.warning(
                "structured_output_parse_retry",
                extra={
                    "event": "structured_output_parse_retry",
                    "attempt": attempt + 1,
                    "max_parse_retries": max_parse_retries,
                    "error_type": type(exc).__name__,
                    "output_model": output_model.__name__,
                },
            )
    raise AssertionError("unreachable")
