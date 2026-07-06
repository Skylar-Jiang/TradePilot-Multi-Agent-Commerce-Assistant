"""Automatic filtering, enrichment, and lightweight classification for raw intelligence."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Iterable

from modules.data_loader import IntelligenceRecord

MIN_CONTENT_LENGTH = 80

NOISE_KEYWORDS = {
    "cookie",
    "cookies",
    "subscribe",
    "newsletter",
    "sign in",
    "sign up",
    "all rights reserved",
    "privacy policy",
    "terms of service",
    "advertisement",
    "enable javascript",
}

DIMENSION_KEYWORDS = {
    "price": [
        "price",
        "discount",
        "套餐",
        "价格",
        "单价",
        "会员价",
        "满减",
        "秒杀",
        "促销",
        "折扣",
        "涨价",
        "降价",
        "猪肉",
        "牛肉",
        "鸡蛋",
        "牛奶",
        "白菜",
        "番茄",
        "苹果",
    ],
    "new_product": [
        "上新",
        "新品",
        "节令",
        "预售",
        "礼盒",
        "产地",
        "规格",
        "预制菜",
        "车厘子",
        "草莓季",
        "发布",
        "更新",
    ],
    "sentiment": [
        "complaint",
        "issue",
        "risk",
        "不新鲜",
        "缺斤少两",
        "配送慢",
        "包装破损",
        "售后差",
        "价格虚高",
        "变质",
        "退款",
        "投诉",
        "差评",
        "风险",
    ],
}


def normalize_url(url: str) -> str:
    return re.sub(r"[?#].*$", "", url.strip().rstrip("/"))


def infer_dimension(text: str, fallback: str = "general") -> str:
    lowered = text.lower()
    scores = {
        dimension: sum(1 for keyword in keywords if keyword.lower() in lowered)
        for dimension, keywords in DIMENSION_KEYWORDS.items()
    }
    best_dimension, score = max(scores.items(), key=lambda item: item[1])
    return best_dimension if score > 0 else fallback


def is_noise_record(record: IntelligenceRecord, keywords: list[str]) -> tuple[bool, str]:
    text = f"{record.title} {record.content}".lower()
    if record.source_type == "csv" and len(text.strip()) >= 20:
        pass
    elif len(record.content) < MIN_CONTENT_LENGTH:
        return True, "content_too_short"
    if not record.source_url:
        return True, "missing_source_url"
    if keywords and not any(keyword.lower() in text for keyword in keywords):
        return True, "keyword_not_matched"
    noise_hits = sum(1 for keyword in NOISE_KEYWORDS if keyword in text)
    if noise_hits >= 4 and record.source_type not in {"webpage", "forum"}:
        return True, "too_many_boilerplate_terms"
    return False, ""


def filter_and_enrich_records(
    records: Iterable[IntelligenceRecord],
    keywords: list[str] | None = None,
    fallback_dimension: str = "general",
) -> tuple[list[IntelligenceRecord], list[dict[str, str]]]:
    keywords = keywords or []
    accepted: list[IntelligenceRecord] = []
    rejected: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for record in records:
        normalized = normalize_url(record.source_url)
        if normalized in seen_urls:
            rejected.append({"source_url": record.source_url, "reason": "duplicate_url"})
            continue
        is_noise, reason = is_noise_record(record, keywords)
        if is_noise:
            rejected.append({"source_url": record.source_url, "reason": reason})
            continue
        seen_urls.add(normalized)
        inferred_dimension = infer_dimension(
            f"{record.title} {record.content}",
            fallback=record.dimension if record.dimension != "general" else fallback_dimension,
        )
        accepted.append(replace(record, source_url=normalized, dimension=inferred_dimension))

    return accepted, rejected
