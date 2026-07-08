"""Conversation memory and webpage crawler workflow.

Run Memory + crawler demo:
    python -m modules.conversation_crawler --mock
"""

from __future__ import annotations

import argparse
import os
import re
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


class CompatConversationBufferMemory:
    """Fallback for LangChain 1.x environments without langchain.memory."""

    def __init__(self, memory_key: str = "history", input_key: str = "question", output_key: str = "output"):
        self.memory_key = memory_key
        self.input_key = input_key
        self.output_key = output_key
        self.buffer: list[tuple[str, str]] = []

    def load_memory_variables(self, _: dict[str, Any]) -> dict[str, str]:
        history = "\n".join(f"Human: {question}\nAI: {answer}" for question, answer in self.buffer)
        return {self.memory_key: history}

    def save_context(self, inputs: dict[str, str], outputs: dict[str, str]) -> None:
        self.buffer.append((inputs.get(self.input_key, ""), outputs.get(self.output_key, "")))


def create_conversation_buffer_memory():
    try:
        from langchain.memory import ConversationBufferMemory

        print("Memory 来源：langchain.memory.ConversationBufferMemory")
        return ConversationBufferMemory(memory_key="history", input_key="question", output_key="output")
    except ModuleNotFoundError:
        print("Memory 来源：兼容实现（当前 LangChain 1.x 已移除 langchain.memory）")
        return CompatConversationBufferMemory(memory_key="history", input_key="question", output_key="output")


def extract_webpage_text(html: str, source_url: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else source_url
    link_titles = []
    for link in soup.find_all("a", href=True)[:10]:
        text = link.get_text(" ", strip=True)
        if text:
            link_titles.append(f"{text} ({urljoin(source_url, link['href'])})")

    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    if link_titles:
        text = f"{text}\n新闻/链接标题：\n" + "\n".join(link_titles)
    return {"title": title, "text": text[:5000], "source_url": source_url}


def fetch_webpage_text(url: str) -> dict[str, str]:
    response = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
        },
    )
    response.raise_for_status()
    return extract_webpage_text(response.text, source_url=url)


def build_memory_llm(mock: bool):
    if mock:
        from langchain_core.language_models.fake_chat_models import FakeListChatModel

        return FakeListChatModel(
            responses=[
                "我已抓取并总结网页内容：盒马相关促销信息可作为价格监控样本，建议继续跟踪会员价和满减活动。",
                "根据上一轮记忆，你刚才关注的是盒马促销网页；本轮重点应补充叮咚买菜的同类活动做对比。",
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


def answer_with_memory(question: str, web_context: str, memory, chain) -> str:
    memory_vars = memory.load_memory_variables({})
    answer = chain.invoke(
        {
            "history": memory_vars.get("history", ""),
            "web_context": web_context,
            "question": question,
        }
    )
    memory.save_context({"question": question}, {"output": answer})
    return answer


def run_memory_crawler(url: str, mock: bool = False) -> list[str]:
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import PromptTemplate

    memory = create_conversation_buffer_memory()
    llm = build_memory_llm(mock)
    prompt = PromptTemplate(
        input_variables=["history", "web_context", "question"],
        template=(
            "你是生鲜电商竞品情报助手。\n"
            "历史对话：\n{history}\n\n"
            "网页抓取内容：\n{web_context}\n\n"
            "用户问题：{question}\n"
            "请结合网页内容和历史对话回答，无法判断时说明需要补充证据。"
        ),
    )
    chain = prompt | llm | StrOutputParser()

    if mock:
        page = {
            "title": "Mock 生鲜促销新闻",
            "text": "盒马推出夏季水果促销，鸡蛋会员价下降；叮咚买菜同步推出满减活动。",
            "source_url": url,
        }
    else:
        page = fetch_webpage_text(url)

    web_context = f"标题：{page['title']}\n来源：{page['source_url']}\n正文：{page['text']}"
    return [
        answer_with_memory("帮我抓取并总结这个竞品网页的新闻标题和核心内容。", web_context, memory, chain),
        answer_with_memory("总结上次讨论的要点，并说明下一步要对比什么。", "", memory, chain),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="多轮对话与网页抓取：ConversationBufferMemory + BeautifulSoup")
    parser.add_argument("--mock", action="store_true", help="不请求真实网页和真实 API")
    parser.add_argument("--url", default="https://example.com")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    outputs = run_memory_crawler(args.url, mock=args.mock)
    for index, output in enumerate(outputs, start=1):
        print(f"\n=== 第 {index} 轮对话 ===")
        print(output)


if __name__ == "__main__":
    main()
