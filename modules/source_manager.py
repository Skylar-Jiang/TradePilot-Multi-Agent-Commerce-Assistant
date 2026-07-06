"""Data source configuration and automated collection jobs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from modules.data_loader import IntelligenceRecord, MultiSourceDocumentLoader, load_csv, save_records_csv
from modules.filtering import filter_and_enrich_records
from modules.rag_chain import build_project_index
from modules.semantic_filter import semantic_filter_records

CONFIG_DIR = Path("data/config")
SCENARIO_SOURCE_YAML = Path("config/sources.yaml")
SOURCE_CONFIG_PATH = CONFIG_DIR / "data_sources.json"
COLLECTION_LOG_PATH = Path("logs/collection_jobs.jsonl")
AUTO_COLLECTION_PATH = Path("data/raw/auto_collected_records.csv")


@dataclass
class DataSourceConfig:
    source_id: str
    source_type: str
    url: str = ""
    path: str = ""
    competitor: str = ""
    dimension: str = "general"
    priority: int = 5
    frequency_minutes: int = 1440
    enabled: bool = True
    keywords: list[str] = field(default_factory=list)
    llm_filter_enabled: bool = True
    last_run_at: str = ""
    next_run_at: str = ""
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def due(self, now: datetime | None = None) -> bool:
        if not self.enabled:
            return False
        now = now or datetime.now(timezone.utc)
        if not self.last_run_at:
            return True
        next_run = parse_datetime(self.next_run_at)
        return not next_run or now >= next_run

    def mark_run(self, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        self.last_run_at = now.isoformat()
        self.next_run_at = (now + timedelta(minutes=self.frequency_minutes)).isoformat()


def parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def load_sources() -> list[DataSourceConfig]:
    if SCENARIO_SOURCE_YAML.exists():
        return load_sources_from_yaml(SCENARIO_SOURCE_YAML)
    if not SOURCE_CONFIG_PATH.exists():
        save_sources(default_sources())
    data = json.loads(SOURCE_CONFIG_PATH.read_text(encoding="utf-8"))
    return [DataSourceConfig(**item) for item in data]


def load_sources_from_yaml(path: Path) -> list[DataSourceConfig]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    competitors = data.get("competitors", [])
    scenario_keywords = [
        keyword
        for competitor in competitors
        for keyword in competitor.get("keywords", [])
    ]
    category_keywords = [
        keyword
        for category in (data.get("product_categories") or {}).values()
        for keyword in category.get("keywords", [])
    ]
    sources = []
    for idx, item in enumerate(data.get("sources", []), start=1):
        source_type = item.get("type", "html")
        mapped_type = {
            "html": "webpage",
            "manual_csv": "csv",
        }.get(source_type, source_type)
        keywords = item.get("keywords") or scenario_keywords + category_keywords
        sources.append(
            DataSourceConfig(
                source_id=item.get("id", f"source_{idx}"),
                source_type=mapped_type,
                url=item.get("url", ""),
                path=item.get("file", item.get("path", "")),
                competitor=item.get("competitor", ""),
                dimension=item.get("dimension", "general"),
                priority=item.get("priority", idx),
                frequency_minutes=item.get("frequency_minutes", 1440),
                enabled=item.get("enabled", True),
                keywords=keywords,
                llm_filter_enabled=item.get("llm_filter_enabled", False if mapped_type == "csv" else True),
                notes=item.get("name", item.get("notes", "")),
            )
        )
    return sources


def save_sources(sources: list[DataSourceConfig]) -> Path:
    SOURCE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_CONFIG_PATH.write_text(
        json.dumps([asdict(source) for source in sources], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return SOURCE_CONFIG_PATH


def default_sources() -> list[DataSourceConfig]:
    return [
        DataSourceConfig(
            source_id="agri_price_public",
            source_type="webpage",
            url="https://pfsc.agri.cn/",
            competitor="",
            dimension="price",
            priority=1,
            frequency_minutes=1440,
            keywords=["猪肉", "牛肉", "鸡蛋", "蔬菜", "水果", "批发价格"],
            notes="全国农产品批发市场价格信息。",
        ),
        DataSourceConfig(
            source_id="mofcom_food_price",
            source_type="webpage",
            url="https://cif.mofcom.gov.cn/",
            competitor="",
            dimension="price",
            priority=2,
            frequency_minutes=1440,
            keywords=["食用农产品", "价格", "肉类", "蛋类", "蔬菜", "水果"],
            notes="商务部食用农产品价格信息。",
        ),
        DataSourceConfig(
            source_id="jd_fresh_manual",
            source_type="csv",
            path="data/raw/jd_fresh_manual.csv",
            competitor="京东生鲜",
            dimension="price",
            priority=3,
            frequency_minutes=1440,
            keywords=["京东生鲜", "鸡蛋", "牛奶", "猪肉", "苹果", "价格"],
            notes="京东生鲜价格手工样例。",
        ),
        DataSourceConfig(
            source_id="hema_price_manual",
            source_type="csv",
            path="data/raw/hema_price_manual.csv",
            competitor="盒马",
            dimension="price",
            priority=4,
            frequency_minutes=1440,
            keywords=["盒马", "猪肉", "鸡蛋", "牛奶", "蔬菜", "水果"],
            notes="盒马价格手工样例。",
        ),
        DataSourceConfig(
            source_id="dingdong_price_manual",
            source_type="csv",
            path="data/raw/dingdong_price_manual.csv",
            competitor="叮咚买菜",
            dimension="price",
            priority=5,
            frequency_minutes=1440,
            keywords=["叮咚买菜", "鸡蛋", "番茄", "黄瓜", "草莓", "促销"],
            notes="叮咚买菜价格手工样例。",
        ),
        DataSourceConfig(
            source_id="meituan_price_manual",
            source_type="csv",
            path="data/raw/meituan_price_manual.csv",
            competitor="美团买菜",
            dimension="price",
            priority=6,
            frequency_minutes=1440,
            keywords=["美团买菜", "猪肉", "牛奶", "土豆", "香蕉", "秒杀"],
            notes="美团买菜价格手工样例。",
        ),
        DataSourceConfig(
            source_id="fresh_promotion_manual",
            source_type="csv",
            path="data/raw/fresh_promotion_manual.csv",
            competitor="",
            dimension="price",
            priority=7,
            frequency_minutes=1440,
            keywords=["满减", "秒杀", "会员价", "促销", "预售"],
            notes="生鲜促销活动样例。",
        ),
        DataSourceConfig(
            source_id="fresh_news_manual",
            source_type="csv",
            path="data/raw/fresh_news_manual.csv",
            competitor="",
            dimension="market",
            priority=8,
            frequency_minutes=1440,
            keywords=["生鲜", "即时零售", "供应链", "门店", "冷链"],
            notes="生鲜行业新闻样例。",
        ),
        DataSourceConfig(
            source_id="fresh_social_manual",
            source_type="csv",
            path="data/raw/fresh_social_manual.csv",
            competitor="",
            dimension="sentiment",
            priority=9,
            frequency_minutes=1440,
            keywords=["不新鲜", "配送慢", "缺斤少两", "售后", "价格虚高"],
            notes="知乎、小红书、微博公开舆情手工样例。",
        ),
        DataSourceConfig(
            source_id="fresh_complaint_manual",
            source_type="csv",
            path="data/raw/fresh_complaint_manual.csv",
            competitor="",
            dimension="sentiment",
            priority=10,
            frequency_minutes=1440,
            keywords=["黑猫投诉", "投诉", "退款", "缺斤少两", "变质", "售后差"],
            notes="生鲜投诉舆情样例。",
        ),
    ]


def upsert_source(source: DataSourceConfig) -> DataSourceConfig:
    sources = load_sources()
    replaced = False
    for idx, existing in enumerate(sources):
        if existing.source_id == source.source_id:
            sources[idx] = source
            replaced = True
            break
    if not replaced:
        sources.append(source)
    save_sources(sources)
    return source


def delete_source(source_id: str) -> bool:
    sources = load_sources()
    kept = [source for source in sources if source.source_id != source_id]
    save_sources(kept)
    return len(kept) != len(sources)


def collect_source(source: DataSourceConfig, use_llm_filter: bool = True) -> dict[str, Any]:
    loader = MultiSourceDocumentLoader(
        source_type=source.source_type,
        url=source.url,
        path=source.path,
        competitor=source.competitor,
        dimension=source.dimension,
    )
    raw_records: list[IntelligenceRecord] = loader.load_records()
    rule_records, rejected = filter_and_enrich_records(
        raw_records,
        keywords=source.keywords,
        fallback_dimension=source.dimension,
    )
    records = rule_records
    llm_rejected: list[dict[str, Any]] = []
    llm_meta: dict[str, Any] = {"enabled": False}
    if use_llm_filter and source.llm_filter_enabled:
        records, llm_rejected, llm_meta = semantic_filter_records(records)

    existing = load_csv(AUTO_COLLECTION_PATH) if AUTO_COLLECTION_PATH.exists() else []
    existing_ids = {record.record_id for record in existing}
    existing_urls = {record.source_url for record in existing}
    new_records = [
        record for record in records if record.record_id not in existing_ids and record.source_url not in existing_urls
    ]
    if new_records:
        save_records_csv(existing + new_records, AUTO_COLLECTION_PATH)
    source.mark_run()
    log_entry = {
        "source_id": source.source_id,
        "source_type": source.source_type,
        "raw_count": len(raw_records),
        "rule_pass_count": len(rule_records),
        "count": len(new_records),
        "duplicate_count": len(records) - len(new_records),
        "rejected_count": len(rejected) + len(llm_rejected),
        "rejected": (rejected + llm_rejected)[:20],
        "llm_filter": llm_meta,
        "collected_at": source.last_run_at,
        "output_path": str(AUTO_COLLECTION_PATH),
    }
    append_collection_log(log_entry)
    return log_entry


def run_collection_job(force: bool = False, use_llm_filter: bool = True) -> dict[str, Any]:
    sources = sorted(load_sources(), key=lambda item: item.priority)
    results = []
    errors = []
    for source in sources:
        if not force and not source.due():
            continue
        try:
            results.append(collect_source(source, use_llm_filter=use_llm_filter))
        except Exception as exc:  # Keep scheduled jobs from failing the whole system.
            errors.append({"source_id": source.source_id, "error": str(exc)})
    save_sources(sources)
    if any(item.get("count", 0) > 0 for item in results):
        index = build_project_index()
        index_meta = {"rebuilt": True, "chunks": len(index.chunks)}
    else:
        index_meta = {"rebuilt": False, "chunks": 0}
    return {"collected": results, "errors": errors, "source_count": len(sources), "index": index_meta}


def append_collection_log(entry: dict[str, Any]) -> None:
    COLLECTION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with COLLECTION_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_collection_logs(limit: int = 50) -> list[dict[str, Any]]:
    if not COLLECTION_LOG_PATH.exists():
        return []
    lines = COLLECTION_LOG_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines[-limit:]]
