"""LangChain chains for competitor intelligence analysis.

Run RunnableSequence demo:
    python -m modules.competitor_analysis_chains --mock
"""

from __future__ import annotations

import argparse
import os
import re

from dotenv import load_dotenv


COMPETITOR_ANALYSIS_TEMPLATE = """
你是一个生鲜批发采购区域供应源竞品情报分析师。
请根据以下信息生成一份简洁、可落地的竞品分析摘要。

分析品类：{product}
区域供应源竞品：{competitor}
关键差异点：{key_points}

输出要求：
1. 先给出一句话结论。
2. 列出 3 条关键发现。
3. 给出 2 条运营建议。
"""


def extract_keywords(text: str, max_chars: int = 50) -> str:
    """Extract compact keyword text for RunnableSequence preprocessing."""
    compact = re.sub(r"\s+", "", text or "")
    return compact[:max_chars]


def build_prompt_inputs(product: str, competitor: str, key_points: str) -> dict[str, str]:
    return {
        "product": product.strip() or "未指定产品",
        "competitor": competitor.strip() or "未指定竞品",
        "key_points": key_points.strip() or "未提供关键差异点",
    }


def build_competitor_prompt():
    from langchain_core.prompts import PromptTemplate

    return PromptTemplate(
        input_variables=["product", "competitor", "key_points"],
        template=COMPETITOR_ANALYSIS_TEMPLATE,
    )


def build_analysis_llm(mock: bool):
    if mock:
        from langchain_core.language_models.fake_chat_models import FakeListChatModel

        return FakeListChatModel(
            responses=[
                (
                    "一句话结论：山东寿光黄瓜在规格稳定性上更强，但河北黄瓜和辽宁批发市场黄瓜形成低价采购替代压力。\n"
                    "关键发现：\n"
                    "1. 山东寿光黄瓜精品货规格稳定，适合作为主采购基准。\n"
                    "2. 河北黄瓜受降雨影响到货波动，短期价差优势收窄。\n"
                    "3. 辽宁批发市场黄瓜低价到货，对价格敏感采购形成替代。\n"
                    "运营建议：\n"
                    "1. 建立寿光、河北、辽宁三地黄瓜日价与到货量监控表。\n"
                    "2. 将批发价、异常价差、新批次供应和质量监管风险放入同一日报。"
                )
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
    )


def run_runnable_sequence(product: str, competitor: str, raw_key_points: str, mock: bool = False) -> str:
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.runnables import RunnableLambda, RunnableSequence

    prompt = build_competitor_prompt()
    llm = build_analysis_llm(mock)
    preprocess = RunnableLambda(
        lambda inputs: build_prompt_inputs(
            product=inputs["product"],
            competitor=inputs["competitor"],
            key_points=extract_keywords(inputs["raw_key_points"]),
        )
    )
    runnable_sequence = preprocess | prompt | llm | StrOutputParser()

    print(f"链路类型：{type(runnable_sequence).__name__}")
    print(f"是否 RunnableSequence：{isinstance(runnable_sequence, RunnableSequence)}")
    return runnable_sequence.invoke(
        {
            "product": product,
            "competitor": competitor,
            "raw_key_points": raw_key_points,
        }
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="竞品分析链路：PromptTemplate + RunnableSequence")
    parser.add_argument("--mock", action="store_true", help="不调用真实 API，生成可截图的固定输出")
    parser.add_argument("--product", default="黄瓜")
    parser.add_argument("--competitor", default="河北黄瓜")
    parser.add_argument("--key-points", default="山东寿光黄瓜批发价小幅上行，河北黄瓜受降雨影响到货减少，辽宁批发市场低价到货。")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    result = run_runnable_sequence(args.product, args.competitor, args.key_points, mock=args.mock)
    print("\n=== RunnableSequence 竞品分析摘要 ===")
    print(result)


if __name__ == "__main__":
    main()
