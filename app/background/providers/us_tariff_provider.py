from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from contextlib import closing
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
from typing import Any

import yaml

from app.background.contracts import BackgroundEvidence, BackgroundQuery, BackgroundResult
from app.schemas.common import DataGap

_SUPPORTED_CONTEXT_TYPES = {"tariff_rate", "import_duty", "customs_duty"}
_US_MARKET_TOKENS = {"united states", "us", "usa", "u.s.", "u.s.a."}
_TARIFF_COST_SEVERITY = {"unknown": -1, "low": 0, "medium": 1, "high": 2}


@dataclass(slots=True)
class HsCodeCandidate:
    hs_code: str
    confidence: float
    rationale: str


@dataclass(slots=True)
class HsMappingEntry:
    segment_id: str
    product_types: tuple[str, ...]
    keywords: tuple[str, ...]
    hs_codes: tuple[HsCodeCandidate, ...]
    notes: str


class USTariffProvider:
    name = "us-tariff-provider"

    def __init__(
        self,
        database_path: Path,
        mapping_path: Path,
    ) -> None:
        self.database_path = database_path
        self.mapping_path = mapping_path
        self._mappings = load_hs_mappings(mapping_path)

    def query(self, query: BackgroundQuery) -> BackgroundResult:
        result = BackgroundResult(provider=self.name, query=query)
        if not _is_us_query(query):
            return result
        if query.context_types and not set(query.context_types).intersection(_SUPPORTED_CONTEXT_TYPES):
            return result
        if not self.database_path.is_file():
            result.data_gaps.append(
                DataGap(
                    code="tariff_database_unavailable",
                    field="trade_tariff_db_path",
                    reason=f"Tariff serving database not found at {self.database_path}",
                    required_for="us_tariff_lookup",
                )
            )
            return result

        matched_entries = match_hs_mappings(self._mappings, product_name=query.product_name, product_type=query.product_type)
        if not matched_entries:
            result.data_gaps.append(
                DataGap(
                    code="missing_hs_mapping",
                    field="product_type",
                    reason=(
                        f"No explicit HS mapping exists for product type {query.product_type!r}; "
                        "Phase 1 will not infer a tariff classification."
                    ),
                    required_for="us_tariff_lookup",
                )
            )
            return result
        if len(matched_entries) > 1:
            result.data_gaps.append(
                DataGap(
                    code="ambiguous_hs_mapping",
                    field="product_type",
                    reason=(
                        f"Multiple HS mapping entries matched {query.product_type!r}; "
                        "Phase 1 refuses to select one automatically."
                    ),
                    required_for="us_tariff_lookup",
                )
            )
            return result

        as_of = query.effective_date or query.query_date
        entry = matched_entries[0]
        tariff_profiles: list[dict[str, Any]] = []
        for candidate in entry.hs_codes:
            rule = _lookup_tariff_rule(self.database_path, candidate.hs_code, as_of)
            if rule is None:
                result.data_gaps.append(
                    DataGap(
                        code="missing_tariff_rule",
                        field="hs_code",
                        reason=(
                            f"No HTS tariff rule was found for HS code {candidate.hs_code} "
                            f"effective on {as_of.isoformat()}."
                        ),
                        required_for="us_tariff_lookup",
                    )
                )
                continue
            tariff_profiles.append(_build_tariff_profile(query, entry, candidate, rule))
            result.evidence.append(
                BackgroundEvidence(
                    evidence_id=f"us-hts-{rule['hs_code']}-{rule['effective_date']}",
                    context_type="tariff_rate",
                    content=_build_evidence_text(query, entry, candidate, rule),
                    source_name=str(rule["source_name"]),
                    source_uri=str(rule["source_url"]),
                    effective_date=date.fromisoformat(str(rule["effective_date"])),
                    jurisdiction=str(rule["jurisdiction"]),
                    confidence=candidate.confidence,
                )
            )
        if tariff_profiles:
            result.decision_inputs = _build_decision_inputs(query, tariff_profiles)
            result.text = str(result.decision_inputs.get("agent_decision_brief") or "").strip()
        if not result.evidence and not result.data_gaps:
            result.data_gaps.append(
                DataGap(
                    code="tariff_evidence_unavailable",
                    field="hs_code",
                    reason="No tariff evidence could be retrieved for the matched HS mapping.",
                    required_for="us_tariff_lookup",
                )
            )
        return result


def load_hs_mappings(path: Path) -> list[HsMappingEntry]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    raw_entries = payload.get("mappings", []) if isinstance(payload, dict) else []
    mappings: list[HsMappingEntry] = []
    for item in raw_entries:
        mappings.append(
            HsMappingEntry(
                segment_id=str(item["segment_id"]),
                product_types=tuple(_normalize_text(value) for value in item.get("product_types", [])),
                keywords=tuple(_normalize_text(value) for value in item.get("keywords", [])),
                hs_codes=tuple(
                    HsCodeCandidate(
                        hs_code=_normalize_hs_code(str(code["hs_code"])),
                        confidence=float(code.get("confidence", 0.5)),
                        rationale=str(code.get("rationale", "")),
                    )
                    for code in item.get("hs_codes", [])
                ),
                notes=str(item.get("notes", "")),
            )
        )
    return mappings


def match_hs_mappings(
    mappings: Iterable[HsMappingEntry],
    *,
    product_name: str,
    product_type: str,
) -> list[HsMappingEntry]:
    normalized_type = _normalize_text(product_type)
    haystack = " ".join(part for part in (_normalize_text(product_name), normalized_type) if part)
    exact_matches = [entry for entry in mappings if normalized_type and normalized_type in entry.product_types]
    if exact_matches:
        return exact_matches
    return [
        entry
        for entry in mappings
        if entry.keywords and any(keyword and keyword in haystack for keyword in entry.keywords)
    ]


def _lookup_tariff_rule(database_path: Path, hs_code: str, as_of: date) -> sqlite3.Row | None:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT
                market,
                jurisdiction,
                hs_code,
                hs_version,
                product_scope,
                general_rate,
                special_rate_text,
                additional_duty_text,
                effective_date,
                end_date,
                source_name,
                source_url
            FROM tariff_rules
            WHERE jurisdiction = 'US'
              AND hs_code = ?
              AND effective_date <= ?
              AND (end_date IS NULL OR end_date = '' OR end_date >= ?)
            ORDER BY effective_date DESC
            LIMIT 1
            """,
            (hs_code, as_of.isoformat(), as_of.isoformat()),
        ).fetchone()
    return row


def _build_evidence_text(
    query: BackgroundQuery,
    mapping: HsMappingEntry,
    candidate: HsCodeCandidate,
    rule: sqlite3.Row,
) -> str:
    parts = [
        (
            f"Configured Phase 1 HS mapping matched {query.product_type!r} "
            f"to candidate HTS {rule['hs_code']} ({rule['product_scope']})."
        ),
        f"General duty rate: {rule['general_rate']}.",
    ]
    if str(rule["special_rate_text"]).strip():
        parts.append(f"Special rate text: {rule['special_rate_text']}.")
    if str(rule["additional_duty_text"]).strip():
        parts.append(f"Additional duty text: {rule['additional_duty_text']}.")
    if candidate.rationale:
        parts.append(f"Mapping rationale: {candidate.rationale}.")
    if mapping.notes:
        parts.append(f"Mapping notes: {mapping.notes}.")
    return " ".join(parts)


def _build_tariff_profile(
    query: BackgroundQuery,
    mapping: HsMappingEntry,
    candidate: HsCodeCandidate,
    rule: sqlite3.Row,
) -> dict[str, Any]:
    general_rate = str(rule["general_rate"]).strip()
    special_rate_text = str(rule["special_rate_text"]).strip()
    additional_duty_text = str(rule["additional_duty_text"]).strip()
    risk_flags = _tariff_risk_flags(
        general_rate=general_rate,
        special_rate_text=special_rate_text,
        additional_duty_text=additional_duty_text,
        confidence=candidate.confidence,
    )
    manual_review_required = True
    tariff_cost_burden = _tariff_cost_burden(
        general_rate=general_rate,
        additional_duty_text=additional_duty_text,
    )
    summary_parts = [
        f"{query.product_type} 当前命中的候选 HTS 为 {rule['hs_code']}",
        f"一般税率为 {general_rate or '未注明'}",
    ]
    if additional_duty_text:
        summary_parts.append(f"另有附加税文本 {additional_duty_text}")
    if special_rate_text:
        summary_parts.append(f"特殊税率文本为 {special_rate_text}")
    summary_parts.append("现阶段仅作为候选归类，正式进口前仍需人工复核。")
    selection_impact = _selection_impact_lines(
        general_rate=general_rate,
        special_rate_text=special_rate_text,
        additional_duty_text=additional_duty_text,
        confidence=candidate.confidence,
    )
    recommended_actions = _recommended_actions(
        general_rate=general_rate,
        special_rate_text=special_rate_text,
        additional_duty_text=additional_duty_text,
    )
    return {
        "segment_id": mapping.segment_id,
        "product_type": query.product_type,
        "product_name": query.product_name,
        "hs_code": str(rule["hs_code"]),
        "product_scope": str(rule["product_scope"]),
        "general_rate": general_rate,
        "special_rate_text": special_rate_text,
        "additional_duty_text": additional_duty_text,
        "effective_date": str(rule["effective_date"]),
        "source_name": str(rule["source_name"]),
        "source_uri": str(rule["source_url"]),
        "confidence": candidate.confidence,
        "mapping_notes": mapping.notes,
        "mapping_rationale": candidate.rationale,
        "tariff_summary": "；".join(summary_parts),
        "tariff_risk_flags": risk_flags,
        "tariff_cost_burden": tariff_cost_burden,
        "manual_review_required": manual_review_required,
        "selection_impact": selection_impact,
        "recommended_actions": recommended_actions,
    }


def _build_decision_inputs(query: BackgroundQuery, tariff_profiles: list[dict[str, Any]]) -> dict[str, Any]:
    primary = tariff_profiles[0]
    impact_lines: list[str] = []
    recommended_actions: list[str] = []
    for profile in tariff_profiles:
        impact_lines.extend(str(item) for item in profile.get("selection_impact", []))
        recommended_actions.extend(str(item) for item in profile.get("recommended_actions", []))
    impact_lines = list(dict.fromkeys(line for line in impact_lines if line))
    recommended_actions = list(dict.fromkeys(line for line in recommended_actions if line))
    risk_flags = sorted(
        {
            str(flag)
            for profile in tariff_profiles
            for flag in profile.get("tariff_risk_flags", [])
            if str(flag).strip()
        }
    )
    manual_review_required = any(bool(profile.get("manual_review_required")) for profile in tariff_profiles)
    profile_summaries = [str(profile.get("tariff_summary") or "").strip() for profile in tariff_profiles]
    profile_summaries = [item for item in profile_summaries if item]
    tariff_cost_burden = _max_tariff_cost_burden(
        str(profile.get("tariff_cost_burden") or "unknown") for profile in tariff_profiles
    )
    agent_decision_brief = _agent_decision_brief(
        product_type=query.product_type,
        primary_profile=primary,
        tariff_cost_burden=tariff_cost_burden,
    )
    return {
        "market": query.market,
        "jurisdiction": query.jurisdiction,
        "tariff_summary": " ".join(profile_summaries),
        "tariff_profiles": tariff_profiles,
        "tariff_risk_flags": risk_flags,
        "tariff_cost_burden": tariff_cost_burden,
        "manual_review_required": manual_review_required,
        "selection_impact": impact_lines,
        "tariff_recommended_actions": recommended_actions,
        "agent_decision_brief": agent_decision_brief,
        "primary_tariff_profile": {
            key: primary.get(key)
            for key in (
                "product_type",
                "hs_code",
                "product_scope",
                "general_rate",
                "special_rate_text",
                "additional_duty_text",
                "effective_date",
                "confidence",
                "tariff_summary",
                "tariff_risk_flags",
                "tariff_cost_burden",
                "manual_review_required",
                "selection_impact",
                "recommended_actions",
            )
        },
    }


def _tariff_risk_flags(
    *,
    general_rate: str,
    special_rate_text: str,
    additional_duty_text: str,
    confidence: float,
) -> list[str]:
    flags: list[str] = []
    normalized_general_rate = general_rate.strip().lower()
    if additional_duty_text:
        flags.append("additional_duty_present")
    if special_rate_text:
        flags.append("special_rate_text_present")
    if normalized_general_rate and normalized_general_rate != "free":
        flags.append("non_free_general_rate")
    if confidence < 0.75:
        flags.append("candidate_mapping_low_confidence")
    flags.append("broker_review_required")
    return flags


def _selection_impact_lines(
    *,
    general_rate: str,
    special_rate_text: str,
    additional_duty_text: str,
    confidence: float,
) -> list[str]:
    impacts: list[str] = []
    if additional_duty_text:
        impacts.append("存在附加税文本，选品测算时应把附加税一并计入 landed cost、毛利和定价缓冲。")
        impacts.append("如果目标毛利空间本来就偏窄，应优先回算含税到岸成本，再决定是否继续推进该品类。")
    elif general_rate.strip().lower() == "free":
        impacts.append("一般税率显示为 Free，基础关税压力相对较低，但仍需核实是否存在其他适用附加税或条件限制。")
    else:
        impacts.append(f"一般税率为 {general_rate or '未注明'}，应在选品利润测算中预留基础关税成本。")
    if special_rate_text:
        impacts.append("存在特殊税率文本，是否适用取决于额外条件，选品立项前应确认申报适用性。")
    if confidence < 0.75:
        impacts.append("当前 HS 归类置信度不高，税费结论只适合作为候选输入，正式上线前需要报关归类复核。")
    else:
        impacts.append("当前税号仍属于候选归类，建议在打样或备货前完成人工归类复核，避免后续税费重算。")
    return impacts


def _recommended_actions(
    *,
    general_rate: str,
    special_rate_text: str,
    additional_duty_text: str,
) -> list[str]:
    actions = [
        "在打样或首单前完成 customs broker / 报关行 HTS 归类复核。",
    ]
    if additional_duty_text:
        actions.append("把附加税情景加入 landed cost 与毛利测算，重新校验定价缓冲。")
    elif general_rate.strip().lower() != "free":
        actions.append("把一般税率计入 landed cost 测算，并复核目标毛利是否仍然成立。")
    if special_rate_text:
        actions.append("确认特殊税率文本对应的适用条件，避免误用优惠税率。")
    return actions


def _tariff_cost_burden(*, general_rate: str, additional_duty_text: str) -> str:
    if additional_duty_text:
        return "high"
    normalized_general_rate = general_rate.strip().lower()
    if not normalized_general_rate:
        return "unknown"
    if normalized_general_rate == "free":
        return "low"
    return "medium"


def _max_tariff_cost_burden(values: Iterable[str]) -> str:
    best = "unknown"
    for value in values:
        normalized = str(value or "unknown").strip().lower() or "unknown"
        if _TARIFF_COST_SEVERITY.get(normalized, -1) > _TARIFF_COST_SEVERITY[best]:
            best = normalized
    return best


def _agent_decision_brief(
    *,
    product_type: str,
    primary_profile: dict[str, Any],
    tariff_cost_burden: str,
) -> str:
    hs_code = str(primary_profile.get("hs_code") or "").strip() or "unknown"
    general_rate = str(primary_profile.get("general_rate") or "").strip() or "未注明"
    additional_duty_text = str(primary_profile.get("additional_duty_text") or "").strip()
    special_rate_text = str(primary_profile.get("special_rate_text") or "").strip()
    burden_text = {
        "high": "税费压力偏高，应优先检验含税成本是否仍支持目标毛利。",
        "medium": "税费会直接影响 landed cost，需要纳入定价与毛利测算。",
        "low": "基础关税压力相对较低，但仍要保留归类与适用条件复核。",
        "unknown": "税费压力暂无法稳定判断，需要补足归类与规则信息。",
    }[tariff_cost_burden]
    parts = [
        f"美国税费输入显示 {product_type} 当前候选 HTS 为 {hs_code}",
        f"一般税率 {general_rate}",
    ]
    if additional_duty_text:
        parts.append(f"另有附加税文本 {additional_duty_text}")
    if special_rate_text:
        parts.append(f"并存在特殊税率文本 {special_rate_text}")
    parts.append(burden_text)
    parts.append("正式进口前仍需人工归类复核。")
    return "；".join(parts)


def _is_us_query(query: BackgroundQuery) -> bool:
    market = _normalize_text(query.market)
    jurisdiction = _normalize_text(query.jurisdiction)
    return market in _US_MARKET_TOKENS or jurisdiction in {"us", "usa", "united states"}


def _normalize_hs_code(value: str) -> str:
    digits = re.sub(r"\D+", "", value)
    return digits[:10]


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())
