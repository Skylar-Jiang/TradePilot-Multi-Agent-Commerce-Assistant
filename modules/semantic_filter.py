"""LLM-powered semantic filtering for public opinion records."""

from __future__ import annotations

import os
from dataclasses import replace
from typing import Any

from modules.data_loader import IntelligenceRecord
from modules.llm_client import LLMConfigurationError, OpenAICompatibleLLM

SEMANTIC_FILTER_PROMPT = """
你是竞品舆情数据清洗审核器，任务是判断每条公开数据是否值得进入生鲜电商竞品动态追踪与价格舆情分析库。
保留标准：
1. 与盒马、叮咚买菜、美团买菜、朴朴超市、京东七鲜、永辉生活、山姆会员店、京东生鲜等平台相关；
2. 与肉蛋奶、基础蔬菜、水果、水产、预制菜等高频生鲜商品的价格、促销、新品/节令上架、投诉舆情、行业动态相关；
3. 来源可追溯，内容不是纯导航、登录页、广告页、隐私条款、站点模板；
4. 可用于后续价格波动、新品/节令商品、负面舆情、平台对比、市场机会分析。

输出 JSON：
{
  "items": [
    {
      "record_id": "原 record_id",
      "keep": true,
      "dimension": "price|new_product|sentiment|general",
      "reason": "保留或过滤原因",
      "confidence": 0.0
    }
  ]
}
只输出 JSON，不要 Markdown。
"""


def semantic_filter_records(
    records: list[IntelligenceRecord],
    batch_size: int = 8,
) -> tuple[list[IntelligenceRecord], list[dict[str, Any]], dict[str, Any]]:
    if not records:
        return [], [], {"enabled": True, "batches": 0}
    if os.getenv("LLM_FILTER_ENABLED", "true").lower() not in {"1", "true", "yes", "on"}:
        return records, [], {"enabled": False, "reason": "LLM_FILTER_ENABLED is false"}

    try:
        llm = OpenAICompatibleLLM()
    except LLMConfigurationError as exc:
        return records, [], {"enabled": False, "reason": str(exc)}

    accepted: list[IntelligenceRecord] = []
    rejected: list[dict[str, Any]] = []
    batches = 0
    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        payload = {
            "records": [
                {
                    "record_id": record.record_id,
                    "title": record.title,
                    "content": record.content[:1200],
                    "source_url": record.source_url,
                    "source_type": record.source_type,
                    "competitor": record.competitor,
                    "dimension": record.dimension,
                }
                for record in batch
            ]
        }
        try:
            result = llm.chat_json(SEMANTIC_FILTER_PROMPT, payload, role="fast", max_tokens=1600)
        except Exception as exc:
            return records, rejected, {"enabled": True, "failed_open": True, "reason": str(exc)}

        decisions = {item.get("record_id"): item for item in result.get("items", [])}
        for record in batch:
            decision = decisions.get(record.record_id, {})
            if decision.get("keep", True):
                accepted.append(replace(record, dimension=decision.get("dimension") or record.dimension))
            else:
                rejected.append(
                    {
                        "source_url": record.source_url,
                        "reason": f"llm_rejected:{decision.get('reason', 'no reason')}",
                        "confidence": decision.get("confidence"),
                    }
                )
        batches += 1
    return accepted, rejected, {"enabled": True, "batches": batches}
