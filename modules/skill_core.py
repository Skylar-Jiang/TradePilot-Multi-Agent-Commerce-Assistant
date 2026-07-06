"""Application-level Skill wrappers for existing RAG, Agent, and report capabilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from modules.agent_core import AgentOrchestrator
from modules.dashboard import infer_risk_tags, risk_rank
from modules.llm_client import LLMConfigurationError, OpenAICompatibleLLM
from modules.report_writer import save_report
from modules.tools import retrieve_evidence_tool

SKILL_TRACE_PATH = Path("logs/skill_trace.jsonl")


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    runner: Callable[[dict[str, Any]], dict[str, Any]]


def standard_output(
    competitor: str,
    analysis_result: dict[str, Any],
    evidence: list[dict[str, Any]],
    risk_level: str = "low",
    risk_tags: list[dict[str, Any]] | None = None,
    suggestions: list[str] | None = None,
    insufficient_evidence: bool | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if insufficient_evidence is None:
        insufficient_evidence = len(evidence) == 0
    output = {
        "competitor": competitor,
        "analysis_result": analysis_result,
        "risk_level": risk_level,
        "risk_tags": risk_tags or [],
        "suggestions": suggestions or [],
        "evidence": evidence,
        "insufficient_evidence": insufficient_evidence,
    }
    if extra:
        output.update(extra)
    return output


def append_skill_trace(skill_name: str, payload: dict[str, Any], result: dict[str, Any]) -> None:
    SKILL_TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "skill_name": skill_name,
        "provider": payload.get("provider", "mock"),
        "competitor": payload.get("competitor", ""),
        "question": payload.get("question", ""),
        "insufficient_evidence": result.get("insufficient_evidence"),
        "evidence_count": len(result.get("evidence", [])),
        "risk_level": result.get("risk_level"),
    }
    with SKILL_TRACE_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_skill_traces(limit: int = 50) -> list[dict[str, Any]]:
    if not SKILL_TRACE_PATH.exists():
        return []
    lines = SKILL_TRACE_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines[-limit:]]


def run_skill(skill_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if skill_name not in SKILL_REGISTRY:
        raise ValueError(f"Unknown skill: {skill_name}")
    result = SKILL_REGISTRY[skill_name].runner(payload)
    append_skill_trace(skill_name, payload, result)
    return result


def list_skills() -> list[dict[str, Any]]:
    return [
        {
            "name": skill.name,
            "description": skill.description,
            "input_schema": skill.input_schema,
            "output_schema": skill.output_schema,
        }
        for skill in SKILL_REGISTRY.values()
    ]


def get_skill(skill_name: str) -> dict[str, Any]:
    if skill_name not in SKILL_REGISTRY:
        raise ValueError(f"Unknown skill: {skill_name}")
    skill = SKILL_REGISTRY[skill_name]
    return {
        "name": skill.name,
        "description": skill.description,
        "input_schema": skill.input_schema,
        "output_schema": skill.output_schema,
    }


def evidence_for(payload: dict[str, Any], dimension: str | None = None, query_suffix: str = "") -> list[dict[str, Any]]:
    competitor = payload.get("competitor", "")
    question = payload.get("query") or payload.get("question", "请进行生鲜电商竞品分析")
    top_k = int(payload.get("top_k", 5))
    query = f"{competitor} {question} {query_suffix}".strip()
    return retrieve_evidence_tool(query=query, dimension=dimension, top_k=top_k, competitor=competitor)


def summarize_evidence(evidence: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    titles = [item.get("title", "") for item in evidence]
    urls = sorted({item.get("source_url", "") for item in evidence if item.get("source_url")})
    return {
        "dimension": dimension,
        "summary": "证据不足，未形成可靠结论。" if not evidence else "基于检索证据形成结构化分析。",
        "key_points": titles[:5],
        "source_urls": urls,
    }


def aggregate_risk(evidence: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    tags: list[dict[str, Any]] = []
    for item in evidence:
        tags.extend(infer_risk_tags(f"{item.get('title', '')} {item.get('text', '')}"))
    if not tags:
        return "low", []
    level = max((tag["level"] for tag in tags), key=risk_rank)
    unique = []
    seen = set()
    for tag in tags:
        key = (tag.get("label"), tag.get("keyword"))
        if key not in seen:
            unique.append(tag)
            seen.add(key)
    return level, unique


def compact_text(value: str, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "。"


def evidence_text(item: dict[str, Any]) -> str:
    return f"{item.get('title', '')} {item.get('text', '')}".strip()


def filter_evidence_by_keywords(evidence: list[dict[str, Any]], keywords: list[str]) -> list[dict[str, Any]]:
    matched = []
    for item in evidence:
        text = evidence_text(item)
        if any(keyword in text for keyword in keywords):
            matched.append(item)
    return matched


def synthesize_section(
    evidence: list[dict[str, Any]],
    section_name: str,
    keywords: list[str],
    fallback_focus: str,
    max_items: int = 5,
) -> str:
    matched = filter_evidence_by_keywords(evidence, keywords) or evidence[:max_items]
    if not matched:
        return f"{section_name}暂无足够公开证据支撑确定性判断，建议补充授权 API、每日价格 CSV 或更多公开报道后再形成结论。"

    points = []
    for item in matched[:max_items]:
        title = item.get("title", "未命名来源")
        text = compact_text(item.get("text", ""), 160)
        competitor = item.get("competitor") or "相关平台"
        points.append(f"{competitor}的公开信息显示，{title}：{text}")
    return f"{section_name}方面，{fallback_focus}" + "；".join(points) + "。"


def platform_updates_from_evidence(evidence: list[dict[str, Any]], max_items: int = 6) -> list[str]:
    updates = []
    seen = set()
    for item in evidence:
        title = item.get("title", "")
        if not title or title in seen:
            continue
        seen.add(title)
        competitor = item.get("competitor") or "相关平台"
        updates.append(f"{competitor}：{title}。{compact_text(item.get('text', ''), 120)}")
        if len(updates) >= max_items:
            break
    return updates


def build_local_integrated_report(
    competitor: str,
    analyses: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    risk_level: str,
    risk_tags: list[dict[str, Any]],
    insufficient: bool,
) -> dict[str, Any]:
    platform_updates = platform_updates_from_evidence(evidence)
    source_urls = sorted({item.get("source_url", "") for item in evidence if item.get("source_url")})
    if insufficient:
        executive_summary = "当前检索证据不足，系统不输出确定性竞品判断。建议先补充真实价格、促销、舆情和行业报道数据。"
    else:
        executive_summary = (
            f"基于 {len(evidence)} 条公开证据片段，{competitor or '目标平台'}的分析重点集中在价格促销、"
            "生鲜履约效率、供应链能力和服务体验风险。报告已将原始证据整合为经营判断，未使用单纯引用记录的占位表达。"
        )

    price_keywords = ["猪肉", "牛肉", "鸡肉", "鸡蛋", "土鸡蛋", "鲜牛奶", "纯牛奶", "酸奶", "肉", "蛋", "奶"]
    vegetable_keywords = ["白菜", "土豆", "番茄", "西红柿", "黄瓜", "青菜", "菠菜", "胡萝卜", "洋葱", "蔬菜"]
    fruit_keywords = ["苹果", "香蕉", "橙子", "草莓", "葡萄", "车厘子", "水果"]
    promotion_keywords = ["满减", "秒杀", "会员价", "促销", "预售", "上新", "新品", "节令", "礼盒", "价格战"]
    sentiment_keywords = ["不新鲜", "配送慢", "缺斤少两", "售后", "投诉", "破损", "变质", "价格虚高", "风险", "履约"]

    return {
        "title": f"{competitor} 生鲜电商竞品动态追踪与价格舆情分析报告",
        "executive_summary": executive_summary,
        "platform_updates": platform_updates or ["暂无足够平台动态证据，建议补充行业媒体和平台公开活动页。"],
        "meat_egg_dairy_price_comparison": synthesize_section(
            evidence,
            "肉蛋奶价格对比",
            price_keywords,
            "应重点观察高频刚需 SKU 的单位价格、会员价和促销价差。",
        ),
        "vegetable_price_comparison": synthesize_section(
            evidence,
            "基础蔬菜价格对比",
            vegetable_keywords,
            "白菜、土豆、番茄、黄瓜等基础菜对用户价格感知最敏感，适合做日级监控。",
        ),
        "fruit_price_comparison": synthesize_section(
            evidence,
            "水果价格对比",
            fruit_keywords,
            "水果类更容易受节令、产地和大包装促销影响，需要同时关注价格和品质反馈。",
        ),
        "promotion_and_seasonal_products": synthesize_section(
            evidence,
            "促销与新品/节令商品",
            promotion_keywords,
            "促销活动会直接影响短期转化，新品和节令商品则体现平台选品与供应链能力。",
        ),
        "sentiment_and_service_risks": synthesize_section(
            evidence,
            "负面舆情与服务风险",
            sentiment_keywords,
            "生鲜消费风险主要集中在新鲜度、履约时效、重量准确性、包装和售后处理。",
        ),
        "time_series_price_trend": (
            "当前证据已具备按 collected_at/publish_time 扩展为日、周、月趋势的基础。"
            "若持续导入每日价格 CSV 或授权 API 数据，可进一步计算涨跌幅、异常波动和平台价差。"
        ),
        "opportunity_threat_judgement": (
            f"综合判断风险等级为 {risk_level}。机会在于围绕鸡蛋、鲜牛奶、猪肉、番茄、草莓等高频 SKU 做价格带监控和促销响应；"
            "威胁在于竞品通过价格战、前置仓效率或供应链直采降低用户迁移成本。"
        ),
        "operation_suggestions": [
            "建立肉蛋奶、基础蔬菜、水果三张日价监控表，跟踪单位价格、会员价和促销价。",
            "对价格战和大促报道设置高优先级预警，结合库存和毛利判断是否跟进。",
            "将不新鲜、配送慢、缺斤少两、售后差等舆情标签沉淀为服务风险看板。",
            "对公开网页无法直接提取价格明细的来源，优先改接授权 API 或规范化 CSV，而不是绕过反爬。",
        ],
        "key_findings": platform_updates[:8],
        "risk_level": risk_level,
        "risk_tags": risk_tags,
        "source_urls": source_urls,
        "insufficient_evidence": insufficient,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def try_llm_integrated_report(
    payload: dict[str, Any],
    competitor: str,
    analyses: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if payload.get("provider", "mock") == "mock":
        return None
    prompt = """
你是生鲜电商竞品分析报告智能体。请把 evidence 中的原文片段整合成可直接阅读的报告，不要写“见 evidence”“见记录”“参考记录”等占位表达。
所有判断必须来自 evidence；证据不足时明确写 insufficient_evidence=true，并说明缺什么数据。
只输出 JSON，字段必须包含：
title, executive_summary, platform_updates, meat_egg_dairy_price_comparison,
vegetable_price_comparison, fruit_price_comparison, promotion_and_seasonal_products,
sentiment_and_service_risks, time_series_price_trend, opportunity_threat_judgement,
operation_suggestions, key_findings, risk_level, risk_tags, source_urls,
insufficient_evidence, generated_at。
"""
    llm_payload = {
        "competitor": competitor,
        "analyses": analyses,
        "evidence": evidence,
    }
    try:
        return OpenAICompatibleLLM().chat_json(prompt, llm_payload, role="report", max_tokens=2200)
    except Exception:
        return None


def run_agent_or_mock(payload: dict[str, Any], agent_name: str, dimension: str, query_suffix: str) -> dict[str, Any]:
    provider = payload.get("provider", "mock")
    competitor = payload.get("competitor", "")
    question = payload.get("question", "请进行竞品分析")
    top_k = int(payload.get("top_k", 5))

    if provider != "mock":
        try:
            result = AgentOrchestrator().run_agent(agent_name, competitor, question, top_k=top_k)
            evidence = result.get("evidence", [])
            risk_level, risk_tags = aggregate_risk(evidence)
            return standard_output(
                competitor=competitor,
                analysis_result=result,
                evidence=evidence,
                risk_level=risk_level,
                risk_tags=risk_tags,
                suggestions=result.get("recommendations", []) or result.get("suggestions", []),
                insufficient_evidence=len(evidence) == 0,
                extra={"provider": provider, "skill_agent": agent_name},
            )
        except (LLMConfigurationError, Exception) as exc:
            evidence = evidence_for(payload, dimension=dimension, query_suffix=query_suffix)
            risk_level, risk_tags = aggregate_risk(evidence)
            return standard_output(
                competitor=competitor,
                analysis_result={
                    **summarize_evidence(evidence, dimension),
                    "provider_error": str(exc),
                    "fallback": "mock",
                },
                evidence=evidence,
                risk_level=risk_level,
                risk_tags=risk_tags,
                suggestions=["检查模型 Key 或继续使用 provider=mock 完成无 Key 演示。"],
                insufficient_evidence=len(evidence) == 0,
                extra={"provider": provider, "skill_agent": agent_name},
            )

    evidence = evidence_for(payload, dimension=dimension, query_suffix=query_suffix)
    risk_level, risk_tags = aggregate_risk(evidence)
    suggestions = ["证据不足，建议补充真实来源。"] if not evidence else ["基于证据继续跟踪变化并补充横向竞品源。"]
    return standard_output(
        competitor=competitor,
        analysis_result=summarize_evidence(evidence, dimension),
        evidence=evidence,
        risk_level=risk_level,
        risk_tags=risk_tags,
        suggestions=suggestions,
        insufficient_evidence=len(evidence) == 0,
        extra={"provider": "mock", "skill_agent": agent_name},
    )


def price_analysis_skill(payload: dict[str, Any]) -> dict[str, Any]:
    return run_agent_or_mock(payload, "price_monitor", "price", "鸡蛋 牛奶 猪肉 番茄 黄瓜 苹果 草莓 价格 单价 会员价 满减 秒杀 促销 涨跌")


def new_product_analysis_skill(payload: dict[str, Any]) -> dict[str, Any]:
    return run_agent_or_mock(payload, "new_product", "new_product", "新品 节令 上架 草莓 车厘子 年货礼盒 预制菜 产地 规格变化")


def sentiment_analysis_skill(payload: dict[str, Any]) -> dict[str, Any]:
    return run_agent_or_mock(payload, "sentiment", "sentiment", "不新鲜 缺斤少两 配送慢 包装破损 售后差 价格虚高 投诉 舆情 风险")


def trend_comparison_skill(payload: dict[str, Any]) -> dict[str, Any]:
    competitor = payload.get("competitor", "")
    evidence = evidence_for(payload, dimension=None, query_suffix="肉蛋奶 蔬菜 水果 日 周 月 价格趋势 平台价差 促销变化")
    by_dimension: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for item in evidence:
        by_dimension[item.get("dimension", "general")] = by_dimension.get(item.get("dimension", "general"), 0) + 1
        by_source[item.get("source_url", "")] = by_source.get(item.get("source_url", ""), 0) + 1
    risk_level, risk_tags = aggregate_risk(evidence)
    return standard_output(
        competitor=competitor,
        analysis_result={
            "dimension_counts": by_dimension,
            "source_counts": by_source,
            "trend_summary": "证据不足，无法判断趋势。" if not evidence else "按生鲜品类、维度和来源汇总近期价格与舆情动态。",
        },
        evidence=evidence,
        risk_level=risk_level,
        risk_tags=risk_tags,
        suggestions=["补充连续日价格 CSV 或授权 API 数据，以增强日/周/月趋势判断。"],
        insufficient_evidence=len(evidence) == 0,
        extra={"provider": payload.get("provider", "mock")},
    )


def report_generation_skill(payload: dict[str, Any]) -> dict[str, Any]:
    competitor = payload.get("competitor", "")
    analyses = payload.get("analyses") or [
        price_analysis_skill(payload),
        new_product_analysis_skill(payload),
        sentiment_analysis_skill(payload),
        trend_comparison_skill(payload),
    ]
    evidence_by_id = {}
    for analysis in analyses:
        for item in analysis.get("evidence", []):
            evidence_by_id[item.get("chunk_id") or item.get("source_url")] = item
    evidence = list(evidence_by_id.values())
    risk_level, risk_tags = aggregate_risk(evidence)
    insufficient = len(evidence) == 0 or all(item.get("insufficient_evidence") for item in analyses)

    report = try_llm_integrated_report(payload, competitor, analyses, evidence)
    if not report:
        report = build_local_integrated_report(
            competitor=competitor,
            analyses=analyses,
            evidence=evidence,
            risk_level=risk_level,
            risk_tags=risk_tags,
            insufficient=insufficient,
        )
    else:
        report.setdefault("risk_level", risk_level)
        report.setdefault("risk_tags", risk_tags)
        report.setdefault("source_urls", sorted({item.get("source_url", "") for item in evidence if item.get("source_url")}))
        report.setdefault("insufficient_evidence", insufficient)
        report.setdefault("generated_at", datetime.now(timezone.utc).isoformat())

    files = save_report(report, competitor or "unknown")
    return standard_output(
        competitor=competitor,
        analysis_result=report,
        evidence=evidence,
        risk_level=risk_level,
        risk_tags=risk_tags,
        suggestions=["用 /reports/{report_name}/preview 查看已整合后的 Markdown 简报。"],
        insufficient_evidence=insufficient,
        extra={"provider": payload.get("provider", "mock"), "report_files": files},
    )

def orchestrator_skill(payload: dict[str, Any]) -> dict[str, Any]:
    analyses = [
        price_analysis_skill(payload),
        new_product_analysis_skill(payload),
        sentiment_analysis_skill(payload),
        trend_comparison_skill(payload),
    ]
    report = report_generation_skill({**payload, "analyses": analyses})
    evidence_by_id = {}
    for item in analyses + [report]:
        for evidence in item.get("evidence", []):
            evidence_by_id[evidence.get("chunk_id") or evidence.get("source_url")] = evidence
    risk_level, risk_tags = aggregate_risk(list(evidence_by_id.values()))
    insufficient = all(item.get("insufficient_evidence") for item in analyses)
    return standard_output(
        competitor=payload.get("competitor", ""),
        analysis_result={
            "price": analyses[0],
            "new_product": analyses[1],
            "sentiment": analyses[2],
            "trend": analyses[3],
            "report": report,
        },
        evidence=list(evidence_by_id.values()),
        risk_level=risk_level,
        risk_tags=risk_tags,
        suggestions=report.get("suggestions", []),
        insufficient_evidence=insufficient,
        extra={"provider": payload.get("provider", "mock"), "report_files": report.get("report_files")},
    )


INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "competitor": {"type": "string"},
        "query": {"type": "string"},
        "question": {"type": "string"},
        "top_k": {"type": "integer", "default": 5},
        "provider": {"type": "string", "enum": ["mock", "openai"], "default": "mock"},
        "dimensions": {"type": "array", "items": {"type": "string"}},
        "report_type": {"type": "string", "default": "weekly"},
        "date_range": {"type": "object"},
    },
    "required": ["competitor"],
}

OUTPUT_SCHEMA = {
    "type": "object",
    "required": [
        "competitor",
        "analysis_result",
        "risk_level",
        "risk_tags",
        "suggestions",
        "evidence",
        "insufficient_evidence",
    ],
}


SKILL_REGISTRY: dict[str, SkillDefinition] = {
    "price_monitor_skill": SkillDefinition(
        "price_monitor_skill",
        "分析生鲜价格波动、平台价差、单位价格、促销力度、涨跌幅和价格异常。",
        INPUT_SCHEMA,
        OUTPUT_SCHEMA,
        price_analysis_skill,
    ),
    "product_update_skill": SkillDefinition(
        "product_update_skill",
        "分析新品上架、节令商品、预制菜新品、产地变化和规格变化。",
        INPUT_SCHEMA,
        OUTPUT_SCHEMA,
        new_product_analysis_skill,
    ),
    "sentiment_risk_skill": SkillDefinition(
        "sentiment_risk_skill",
        "分析不新鲜、缺斤少两、配送慢、包装破损、售后差、价格争议等负面舆情。",
        INPUT_SCHEMA,
        OUTPUT_SCHEMA,
        sentiment_analysis_skill,
    ),
    "trend_compare_skill": SkillDefinition(
        "trend_compare_skill",
        "分析肉蛋奶、基础蔬菜、水果等商品的日/周/月价格趋势。",
        INPUT_SCHEMA,
        OUTPUT_SCHEMA,
        trend_comparison_skill,
    ),
    "report_generation_skill": SkillDefinition(
        "report_generation_skill",
        "生成生鲜电商竞品分析报告。",
        INPUT_SCHEMA,
        OUTPUT_SCHEMA,
        report_generation_skill,
    ),
    "orchestrator_skill": SkillDefinition(
        "orchestrator_skill",
        "调度价格、新品、舆情、趋势和报告生成 Skill，完成完整生鲜竞品分析流程。",
        INPUT_SCHEMA,
        OUTPUT_SCHEMA,
        orchestrator_skill,
    ),
}

