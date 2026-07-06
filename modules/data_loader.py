"""Load, clean, and persist public competitor intelligence records."""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import feedparser
import pandas as pd
import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")


@dataclass
class IntelligenceRecord:
    title: str
    content: str
    source_url: str
    source_type: str = "manual"
    competitor: str = ""
    dimension: str = "general"
    collected_at: str = ""
    record_id: str = ""

    def __post_init__(self) -> None:
        self.content = clean_text(self.content)
        self.title = clean_text(self.title)
        if not self.collected_at:
            self.collected_at = datetime.now(timezone.utc).isoformat()
        if not self.record_id:
            base = f"{self.source_url}|{self.title}|{self.content[:200]}"
            self.record_id = hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    ad_patterns = ["点击查看", "责任编辑", "广告", "免责声明"]
    for pattern in ad_patterns:
        text = text.replace(pattern, "")
    return text.strip()


def dedupe_records(records: Iterable[IntelligenceRecord]) -> list[IntelligenceRecord]:
    seen: set[str] = set()
    unique: list[IntelligenceRecord] = []
    for record in records:
        if record.record_id in seen or not record.content:
            continue
        seen.add(record.record_id)
        unique.append(record)
    return unique


def load_csv(path: str | Path) -> list[IntelligenceRecord]:
    csv_path = Path(path)
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return []
    df = pd.read_csv(csv_path)
    records = []
    for row in df.fillna("").to_dict(orient="records"):
        fresh_content = build_content_from_fresh_row(row)
        records.append(
            IntelligenceRecord(
                title=row.get("title", ""),
                content=row.get("content", row.get("text", fresh_content)),
                source_url=row.get("source_url", row.get("url", "")),
                source_type=row.get("source_type", "csv"),
                competitor=row.get("competitor", ""),
                dimension=row.get("dimension", "general"),
                collected_at=row.get("collected_at", row.get("publish_time", "")),
                record_id=row.get("record_id", ""),
            )
        )
    return dedupe_records(records)


def build_content_from_fresh_row(row: dict[str, Any]) -> str:
    if "product_name" not in row:
        return ""
    parts = [
        f"竞品平台：{row.get('competitor', '')}",
        f"商品类别：{row.get('product_category', '')}",
        f"商品名称：{row.get('product_name', '')}",
        f"规格：{row.get('specification', '')}",
        f"价格：{row.get('price', '')}",
        f"单位价格：{row.get('unit_price', '')}",
        f"信息标题：{row.get('title', '')}",
        f"内容：{row.get('content', '')}",
        f"来源：{row.get('source', '')}",
        f"发布时间：{row.get('publish_time', '')}",
    ]
    return "；".join(str(part) for part in parts if str(part).strip())


def fetch_webpage(url: str, competitor: str = "", dimension: str = "general") -> IntelligenceRecord:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }
    last_error: Exception | None = None
    for _ in range(3):
        try:
            response = requests.get(url, timeout=20, headers=headers)
            break
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(1)
    else:
        raise RuntimeError(f"Failed to fetch webpage after retries: {last_error}") from last_error
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    content = soup.get_text(" ", strip=True)
    return IntelligenceRecord(
        title=title,
        content=content[:12000],
        source_url=url,
        source_type="webpage",
        competitor=competitor,
        dimension=dimension,
    )


def fetch_rss(url: str, competitor: str = "", dimension: str = "general", limit: int = 20) -> list[IntelligenceRecord]:
    feed = feedparser.parse(url)
    records = []
    for entry in feed.entries[:limit]:
        content = entry.get("summary", "") or entry.get("description", "")
        records.append(
            IntelligenceRecord(
                title=entry.get("title", ""),
                content=BeautifulSoup(content, "html.parser").get_text(" ", strip=True),
                source_url=entry.get("link", url),
                source_type="rss",
                competitor=competitor,
                dimension=dimension,
            )
        )
    return dedupe_records(records)


def fetch_search_page(
    url: str,
    competitor: str = "",
    dimension: str = "general",
    limit: int = 20,
) -> list[IntelligenceRecord]:
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
    soup = BeautifulSoup(response.text, "html.parser")
    records = []
    for link in soup.find_all("a", href=True):
        title = clean_text(link.get_text(" ", strip=True))
        href = link["href"]
        if not title or href.startswith("#") or href.startswith("javascript:"):
            continue
        if href.startswith("/"):
            from urllib.parse import urljoin

            href = urljoin(url, href)
        parent_text = clean_text(link.parent.get_text(" ", strip=True) if link.parent else title)
        records.append(
            IntelligenceRecord(
                title=title[:200],
                content=parent_text[:2000] or title,
                source_url=href,
                source_type="search_page",
                competitor=competitor,
                dimension=dimension,
            )
        )
        if len(records) >= limit:
            break
    return dedupe_records(records)


def save_records_csv(records: Iterable[IntelligenceRecord], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    unique = dedupe_records(records)
    columns = [
        "title",
        "content",
        "source_url",
        "source_type",
        "competitor",
        "dimension",
        "collected_at",
        "record_id",
    ]
    pd.DataFrame([asdict(record) for record in unique], columns=columns).to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )
    return output_path


def load_project_records() -> list[IntelligenceRecord]:
    records: list[IntelligenceRecord] = []
    for directory in (RAW_DIR, PROCESSED_DIR):
        for path in directory.glob("*.csv"):
            records.extend(load_csv(path))
    return dedupe_records(records)


class MultiSourceDocumentLoader:
    """LangChain-style loader for CSV, RSS, webpage, and forum sources."""

    def __init__(
        self,
        source_type: str,
        url: str = "",
        path: str = "",
        competitor: str = "",
        dimension: str = "general",
    ):
        self.source_type = source_type
        self.url = url
        self.path = path
        self.competitor = competitor
        self.dimension = dimension

    def load_records(self) -> list[IntelligenceRecord]:
        if self.source_type == "csv":
            return load_csv(self.path)
        if self.source_type == "rss":
            return fetch_rss(self.url, competitor=self.competitor, dimension=self.dimension)
        if self.source_type == "search_page":
            return fetch_search_page(self.url, competitor=self.competitor, dimension=self.dimension)
        if self.source_type in {"webpage", "forum"}:
            record = fetch_webpage(self.url, competitor=self.competitor, dimension=self.dimension)
            record.source_type = self.source_type
            return [record]
        raise ValueError(f"Unsupported source_type: {self.source_type}")

    def load(self) -> list[Document]:
        documents = []
        for record in self.load_records():
            documents.append(
                Document(
                    page_content=record.content,
                    metadata={
                        "record_id": record.record_id,
                        "title": record.title,
                        "source_url": record.source_url,
                        "source_type": record.source_type,
                        "competitor": record.competitor,
                        "dimension": record.dimension,
                        "collected_at": record.collected_at,
                    },
                )
            )
        return documents
