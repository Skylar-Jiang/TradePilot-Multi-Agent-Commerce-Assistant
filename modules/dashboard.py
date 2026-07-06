"""Backend data views for the intelligence dashboard and Swagger demos."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from modules.data_loader import load_project_records
from modules.report_writer import REPORT_DIR, render_markdown_report

RISK_KEYWORDS = {
    "降价": ("medium", "价格下探"),
    "涨价": ("medium", "价格上涨"),
    "满减": ("medium", "促销竞争"),
    "秒杀": ("medium", "限时促销"),
    "会员价": ("medium", "会员价差"),
    "不新鲜": ("high", "品质风险"),
    "缺斤少两": ("high", "计量争议"),
    "配送慢": ("medium", "履约时效风险"),
    "包装破损": ("medium", "包装履约风险"),
    "售后差": ("high", "售后服务风险"),
    "价格虚高": ("medium", "价格争议"),
    "变质": ("high", "食品安全风险"),
    "退款": ("medium", "售后退款风险"),
    "投诉": ("high", "消费者投诉"),
}


def infer_risk_tags(text: str) -> list[dict[str, str]]:
    tags = []
    for keyword, (level, label) in RISK_KEYWORDS.items():
        if keyword in text:
            tags.append({"level": level, "label": label, "keyword": keyword})
    return tags


def risk_rank(level: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(level, 0)


def competitor_summary() -> list[dict[str, Any]]:
    summaries = []
    for record in load_project_records():
        tags = infer_risk_tags(f"{record.title} {record.content}")
        highest = max((tag["level"] for tag in tags), key=risk_rank, default="low")
        summaries.append(
            {
                "competitor": record.competitor,
                "dimension": record.dimension,
                "title": record.title,
                "source_url": record.source_url,
                "collected_at": record.collected_at,
                "risk_level": highest,
                "risk_tags": tags,
                "summary": record.content[:160],
            }
        )
    summaries.sort(key=lambda item: (risk_rank(item["risk_level"]), item["collected_at"]), reverse=True)
    return summaries


def comparison_data() -> dict[str, Any]:
    records = load_project_records()
    competitors = sorted({record.competitor for record in records if record.competitor})
    dimensions = ["price", "new_product", "sentiment"]
    matrix = []
    for competitor in competitors:
        row = {"competitor": competitor}
        for dimension in dimensions:
            dimension_records = [
                record for record in records if record.competitor == competitor and record.dimension == dimension
            ]
            row[dimension] = {
                "count": len(dimension_records),
                "latest_titles": [record.title for record in dimension_records[-3:]],
            }
        matrix.append(row)
    return {"dimensions": dimensions, "competitors": competitors, "matrix": matrix}


def risk_tags_view() -> list[dict[str, Any]]:
    items = []
    for item in competitor_summary():
        for tag in item["risk_tags"]:
            items.append(
                {
                    "competitor": item["competitor"],
                    "dimension": item["dimension"],
                    "title": item["title"],
                    "source_url": item["source_url"],
                    **tag,
                }
            )
    items.sort(key=lambda item: risk_rank(item["level"]), reverse=True)
    return items


def list_reports() -> list[dict[str, Any]]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    reports = []
    for path in sorted(REPORT_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        data = json.loads(path.read_text(encoding="utf-8"))
        reports.append(
            {
                "name": path.name,
                "title": data.get("title", path.stem),
                "json_path": str(path),
                "markdown_path": str(path.with_suffix(".md")),
                "created_at": path.stat().st_mtime,
            }
        )
    return reports


def report_preview(report_name: str) -> dict[str, str]:
    safe_name = Path(report_name).name
    json_path = REPORT_DIR / safe_name
    if json_path.suffix != ".json":
        json_path = json_path.with_suffix(".json")
    if not json_path.exists():
        raise FileNotFoundError(safe_name)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    md_path = json_path.with_suffix(".md")
    markdown = md_path.read_text(encoding="utf-8") if md_path.exists() else render_markdown_report(data)
    return {"name": json_path.name, "markdown": markdown, "json": json.dumps(data, ensure_ascii=False, indent=2)}
