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
你是一个生鲜电商竞品情报分析师。
请根据以下信息生成一份简洁、可落地的竞品分析摘要。

产品名称：{product}
竞争对手：{competitor}
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
                    "一句话结论：盒马在会员价和即时履约上具备优势，但需要持续关注叮咚买菜的满减促销。\n"
                    "关键发现：\n"
                    "1. 盒马鸡蛋会员价更低，适合作为引流商品。\n"
                    "2. 叮咚买菜满减活动提升客单价，对价格敏感用户有吸引力。\n"
                    "3. 售后评价差异会影响复购，需要纳入舆情监控。\n"
                    "运营建议：\n"
                    "1. 保持肉蛋奶核心 SKU 的会员价优势。\n"
                    "2. 将价格监控、促销监控和投诉舆情放入同一日报。"
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
    parser.add_argument("--product", default="盒马鲜生")
    parser.add_argument("--competitor", default="叮咚买菜")
    parser.add_argument("--key-points", default="鸡蛋会员价下降，叮咚买菜推出满减，履约时效和售后评价出现差异。")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    result = run_runnable_sequence(args.product, args.competitor, args.key_points, mock=args.mock)
    print("\n=== RunnableSequence 竞品分析摘要 ===")
    print(result)


if __name__ == "__main__":
    main()
