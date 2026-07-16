import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel

from app.agents.structured_output import invoke_structured


class ParsedFixture(BaseModel):
    answer: str


def prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([("human", "Return JSON for {question}")])


def test_structured_output_retries_once_after_json_parse_failure() -> None:
    model = FakeListChatModel(responses=["not-json", '{"answer":"合格"}'])

    result = invoke_structured(
        prompt=prompt(),
        model=model,
        values={"question": "测试"},
        output_model=ParsedFixture,
        normalize=lambda payload: payload,
        max_parse_retries=1,
    )

    assert result.value == ParsedFixture(answer="合格")
    assert result.model_call_count == 2
    assert result.parse_retry_count == 1
    assert result.parser_name == "PydanticOutputParser"


def test_structured_output_retries_after_pydantic_schema_failure() -> None:
    model = FakeListChatModel(responses=['{"wrong":"field"}', '{"answer":"合格"}'])

    result = invoke_structured(
        prompt=prompt(),
        model=model,
        values={"question": "测试"},
        output_model=ParsedFixture,
        normalize=lambda payload: payload,
        max_parse_retries=1,
    )

    assert result.value.answer == "合格"
    assert result.parse_retry_count == 1


def test_structured_output_does_not_retry_provider_runtime_failure() -> None:
    calls = 0

    def fail(_value):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        raise RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        invoke_structured(
            prompt=prompt(),
            model=RunnableLambda(fail),
            values={"question": "测试"},
            output_model=ParsedFixture,
            normalize=lambda payload: payload,
            max_parse_retries=2,
        )

    assert calls == 1


def test_structured_output_aggregates_provider_token_usage_across_parse_retry() -> None:
    responses = iter(
        [
            AIMessage(
                content="not-json",
                usage_metadata={"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
            ),
            AIMessage(
                content='{"answer":"合格"}',
                usage_metadata={"input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
            ),
        ]
    )

    result = invoke_structured(
        prompt=prompt(),
        model=RunnableLambda(lambda _: next(responses)),
        values={"question": "测试"},
        output_model=ParsedFixture,
        normalize=lambda payload: payload,
        max_parse_retries=1,
    )

    assert result.token_usage == {"input_tokens": 20, "output_tokens": 6, "total_tokens": 26}
