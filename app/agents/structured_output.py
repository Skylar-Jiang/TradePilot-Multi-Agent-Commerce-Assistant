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

# 获取当前模块的日志记录器，用于记录警告和错误信息（如解析失败重试时的日志）
logger = logging.getLogger("tradepilot.agent.structured_output")


# 使用 dataclass 装饰器定义结构化输出的结果载体，设置为不可变（frozen=True）与 slots 优化内存使用
# [OutputT: BaseModel] 声明了泛型类型，表示该类包含的值必须是 Pydantic 的 BaseModel 的子类
@dataclass(frozen=True, slots=True)
class StructuredOutputResult[OutputT: BaseModel]:
    # value: 存储最终成功解析并转换好的结构化数据对象
    value: OutputT
    # model_call_count: 记录大模型实际被调用的总次数（初次调用 + 失败重试次数）
    model_call_count: int
    # parse_retry_count: 记录由于输出格式不合规导致的重试次数
    parse_retry_count: int
    # token_usage: 记录调用大模型过程中累计消耗的 token 数量字典（输入/输出/总计等），若未获取到则为 None
    token_usage: dict[str, int] | None = None
    # parser_name: 记录所使用的解析器名称，默认为 PydanticOutputParser
    parser_name: str = "PydanticOutputParser"


# 核心调用函数：负责编排提示词与大模型调用，捕获结果并解析为强类型的 Pydantic 对象，同时具备自动重试机制
# 泛型参数 [OutputT: BaseModel] 限定了输出对象的目标类型
def invoke_structured[OutputT: BaseModel](
    *,
    # prompt: LangChain 的提示词 Runnable 对象
    prompt: Runnable[Any, Any],
    # model: LangChain 的语言模型 Runnable 对象
    model: Runnable[Any, Any],
    # values: 用于填充提示词模板的参数字典
    values: Mapping[str, Any],
    # output_model: 期望得到的 Pydantic 模型类（决定了结构化输出的格式）
    output_model: type[OutputT],
    # normalize: 自定义的回调函数，用于在标准解析之前清洗或补全模型输出的字典数据
    normalize: Callable[[dict[str, Any]], OutputT | dict[str, Any]],
    # max_parse_retries: 遇到解析异常时的最大允许重试次数
    max_parse_retries: int,
) -> StructuredOutputResult[OutputT]:
    """Invoke one typed LCEL chain and retry only malformed JSON/schema output."""
    """调用单个类型化的 LCEL 链，并仅针对格式错误的 JSON/Schema 输出进行重试。"""

    # 实例化 LangChain 的 Pydantic 输出解析器，绑定我们期望的目标模型类
    parser = PydanticOutputParser(pydantic_object=output_model)
    # 初始化一个空字典，以便在链条多次执行（包含重试）中累加模型调用的 token 消耗
    token_usage: dict[str, int] = {}

    # --- 辅助步骤 1：拦截响应并提取 token 消耗统计 ---
    def capture_usage(message: object) -> object:
        # 尝试直接从消息对象的 usage_metadata 属性中获取使用情况
        usage = getattr(message, "usage_metadata", None)
        # 如果没找到 usage_metadata，尝试去 response_metadata 中查找 token_usage
        if not isinstance(usage, dict):
            metadata = getattr(message, "response_metadata", None)
            usage = metadata.get("token_usage") if isinstance(metadata, dict) else None

        # 如果成功获取到了字典形式的使用情况，则将各个维度的 token 数进行累加
        if isinstance(usage, dict):
            # 将不同大模型提供商可能有差异的 token 字段名统一映射为标准名称
            aliases = {
                "prompt_tokens": "input_tokens",
                "completion_tokens": "output_tokens",
                "input_tokens": "input_tokens",
                "output_tokens": "output_tokens",
                "total_tokens": "total_tokens",
            }
            # 遍历使用量字典，对匹配的键进行累计计算
            for source, target in aliases.items():
                value = usage.get(source)
                if isinstance(value, int):
                    token_usage[target] = token_usage.get(target, 0) + value
        # 返回原有的消息对象，保证 LCEL 链条的数据可以继续向下游传递
        return message

    # --- 辅助步骤 2：从文本提取 JSON 并规范化 ---
    def decode_and_normalize(message: object) -> OutputT | dict[str, Any]:
        # 获取消息对象的 content 属性，如果是纯字符串则直接使用
        content = getattr(message, "content", message)
        # parse_json_object 负责从可能的 Markdown 或杂乱文本中提取出纯净的 JSON 字典
        # normalize 负责根据业务需求对解析出来的字典进行进一步校验、修改或填充默认值
        return normalize(parse_json_object(str(content)))

    # --- 辅助步骤 3：将规范化后的数据再转回 JSON 字符串 ---
    def serialize(value: OutputT | dict[str, Any]) -> str:
        # 如果经过 normalize 后已经是目标 Pydantic 对象，则调用其自带的序列化方法
        if isinstance(value, BaseModel):
            return value.model_dump_json()
        # 否则使用内置的 json.dumps 将字典转为 JSON 字符串（禁用 ASCII 转义以保留原有的非 ASCII 字符如中文）
        return json.dumps(value, ensure_ascii=False)

    # 构建 LCEL (LangChain Expression Language) 处理链
    # 数据流转：填充提示词 -> 大模型生成 -> 拦截并统计 Token -> 提取清洗 JSON -> 转回 JSON 字符串 -> Pydantic 最终解析
    chain = (
        prompt
        | model
        | RunnableLambda(capture_usage)
        | RunnableLambda(decode_and_normalize)
        | RunnableLambda(serialize)
        | parser
    )

    # 定义遇到哪些异常时触发重试：LangChain的输出解析错误、Pydantic的校验错误、通用的值错误
    retryable = (OutputParserException, ValidationError, ValueError)

    # 开始执行调用与重试逻辑（循环次数 = 最大重试次数 + 1 次首次尝试）
    for attempt in range(max_parse_retries + 1):
        try:
            # 触发整个链条的运行，并传入字典化的 values 参数
            value = chain.invoke(dict(values))
            # 若执行无异常，封装结果并返回
            return StructuredOutputResult(
                value=value,
                model_call_count=attempt + 1,      # 本次成功前总共发起的模型调用次数
                parse_retry_count=attempt,         # 发生过的解析失败重试次数
                token_usage=token_usage or None,   # 返回统计到的 Token 消耗，空字典则返回 None
            )
        except retryable as exc:
            # 如果捕获到了预期的异常且达到了最大允许的重试次数，则不再重试，直接将异常抛出
            if attempt >= max_parse_retries:
                raise
            # 若仍有重试额度，记录一次警告日志，以便开发者监控大模型输出稳定性和重试频率
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

    # 防止代码在非正常情况下跌落循环之外（理论上不会执行到这里）
    raise AssertionError("unreachable")
