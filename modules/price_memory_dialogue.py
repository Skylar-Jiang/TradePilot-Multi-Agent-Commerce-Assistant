"""Two real API calls with memory for fresh-price webpage content.

Run real API demo:
    python -m modules.price_memory_dialogue

Run local mock demo:
    python -m modules.price_memory_dialogue --mock
"""

from __future__ import annotations

import argparse
import os
from typing import Any

from dotenv import load_dotenv


WEBPAGE_PRICE_CONTEXT = """
网页标题：生鲜批发价格公开样例
网页解析内容：
1. 山东寿光黄瓜批发价小幅上行，主要因为本地新批次上市节奏放缓，优质货源议价能力增强。
2. 河北产区近期受降雨影响，黄瓜采收、装车和到货节奏放慢，部分批发市场反馈到货量减少。
3. 辽宁批发市场出现低价到货，主要为普通规格货源，短期可能拉低周边市场报价预期。
4. 质量监管提示：降雨后产区需要关注水分偏高、运输损耗和分级不稳定，避免只看低价忽略品质风险。
"""

FIRST_QUESTION = "请根据网页解析内容，总结本轮抓取到的生鲜批发价格样例，控制在一段话内。"
SECOND_QUESTION = "请根据上一轮记忆，说明刚才关注的核心行情，并指出本轮下一步要补充对比的重点。"


class CompatConversationBufferMemory:
    """Small memory fallback for LangChain 1.x environments without langchain.memory."""

    def __init__(self, memory_key: str = "history", input_key: str = "question", output_key: str = "answer"):
        self.memory_key = memory_key
        self.input_key = input_key
        self.output_key = output_key
        self.buffer: list[tuple[str, str]] = []

    def load_memory_variables(self, _: dict[str, Any]) -> dict[str, str]:
        history = "\n".join(f"Human: {question}\nAI: {answer}" for question, answer in self.buffer)
        return {self.memory_key: history}

    def save_context(self, inputs: dict[str, str], outputs: dict[str, str]) -> None:
        self.buffer.append((inputs.get(self.input_key, ""), outputs.get(self.output_key, "")))


def create_memory():
    try:
        from langchain.memory import ConversationBufferMemory

        return ConversationBufferMemory(memory_key="history", input_key="question", output_key="answer")
    except ModuleNotFoundError:
        return CompatConversationBufferMemory(memory_key="history", input_key="question", output_key="answer")


def create_price_memory_prompt():
    from langchain_core.prompts import PromptTemplate

    return PromptTemplate(
        input_variables=["history", "web_context", "question"],
        template=(
            "你是生鲜批发价格情报分析助手。请严格基于给定材料回答，不要编造新地区或新价格。\n"
            "输出只写一段中文正文，不要写 Markdown 列表，不要添加标题。\n\n"
            "历史记忆：\n{history}\n\n"
            "本轮网页解析内容：\n{web_context}\n\n"
            "用户问题：{question}\n"
        ),
    )


def build_dialogue_llm(mock: bool):
    if mock:
        from langchain_core.language_models.fake_chat_models import FakeListChatModel

        return FakeListChatModel(
            responses=[
                "根据网页解析内容，本轮抓取到的生鲜批发价格样例主要涉及山东寿光、河北和辽宁三个区域的黄瓜行情。其中，山东寿光黄瓜批发价小幅上行，河北黄瓜受降雨影响到货减少，辽宁批发市场出现低价到货。",
                "根据上一轮记忆，你刚才关注的是寿光黄瓜行情；本轮重点应补充河北降雨影响、辽宁低价到货和质量监管风险做对比。",
            ]
        )

    from langchain_openai import ChatOpenAI

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("请先在 .env 中配置 OPENAI_API_KEY 或 DEEPSEEK_API_KEY，或使用 --mock。")

    return ChatOpenAI(
        model=os.getenv("MODEL_ANALYSIS", "deepseek-chat"),
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        temperature=float(os.getenv("MODEL_TEMPERATURE", "0.0")),
        max_tokens=300,
    )


def ask_with_memory(chain, memory, question: str, web_context: str = "") -> str:
    memory_vars = memory.load_memory_variables({})
    answer = chain.invoke(
        {
            "history": memory_vars.get("history", ""),
            "web_context": web_context,
            "question": question,
        }
    )
    memory.save_context({"question": question}, {"answer": answer})
    return answer


def run_price_memory_dialogue(mock: bool = False) -> list[str]:
    from langchain_core.output_parsers import StrOutputParser

    memory = create_memory()
    prompt = create_price_memory_prompt()
    chain = prompt | build_dialogue_llm(mock) | StrOutputParser()

    first_answer = ask_with_memory(chain, memory, FIRST_QUESTION, WEBPAGE_PRICE_CONTEXT)
    second_answer = ask_with_memory(chain, memory, SECOND_QUESTION)
    return [first_answer, second_answer]


def print_dialogue(outputs: list[str]) -> None:
    for index, output in enumerate(outputs, start=1):
        print(f"=== 第 {index} 轮对话 ===")
        print(output.strip())
        if index != len(outputs):
            print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="两次真实 API 调用：网页内容总结 + 记忆追问")
    parser.add_argument("--mock", action="store_true", help="不调用真实 API，使用固定输出检查格式")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    print_dialogue(run_price_memory_dialogue(mock=args.mock))


if __name__ == "__main__":
    main()
