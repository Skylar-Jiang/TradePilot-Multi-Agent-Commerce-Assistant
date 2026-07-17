from __future__ import annotations

import csv
import json
import sqlite3
from collections.abc import Iterable, Sequence
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
import re

DEFAULT_SOURCE_NAME = "USITC Harmonized Tariff Schedule"
DEFAULT_SOURCE_URL = "https://hts.usitc.gov/export"

_HS_DIGITS = re.compile(r"\D+")
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%Y%m%d")
_COLUMN_ALIASES = {
    "hs_code": (
        "hts number",
        "htsno",
        "hts number legacy",
        "subheading",
        "tariff number",
        "hs code",
    ),
    "product_scope": (
        "article description",
        "description",
        "indent description",
        "full description",
    ),
    "general_rate": (
        "general",
        "general rate of duty",
        "column 1 general",
        "rate of duty 1-general",
    ),
    "special_rate_text": (
        "special",
        "special rate of duty",
        "rate of duty 1-special",
    ),
    "additional_duty_text": (
        "other",
        "column 2",
        "rate of duty 2",
        "additional duties",
        "additional duty text",
    ),
    "effective_date": (
        "effective date",
        "valid from",
        "start date",
    ),
    "end_date": (
        "end date",
        "valid to",
        "expiration date",
    ),
    "hs_version": (
        "hts revision",
        "hts version",
        "schedule version",
    ),
}


@dataclass(slots=True)
class TariffRuleRecord:
    market: str
    jurisdiction: str
    hs_code: str
    hs_version: str
    product_scope: str
    general_rate: str
    special_rate_text: str
    additional_duty_text: str
    effective_date: date
    end_date: date | None
    source_name: str
    source_url: str


def normalize_hs_code(value: str) -> str:
    digits = _HS_DIGITS.sub("", value or "")
    if len(digits) < 6:
        raise ValueError(f"HS code must contain at least 6 digits, got {value!r}")
    return digits[:10]


def parse_optional_date(value: str | None) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value!r}")


def _normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _resolve_column(headers: Sequence[str], field_name: str) -> str | None:
    normalized = {_normalize_header(header): header for header in headers}
    for alias in _COLUMN_ALIASES[field_name]:
        header = normalized.get(alias)
        if header is not None:
            return header
    return None


def parse_us_hts_table(
    source_path: Path,
    *,
    source_name: str = DEFAULT_SOURCE_NAME,
    source_url: str = DEFAULT_SOURCE_URL,
    market: str = "United States",
    jurisdiction: str = "US",
    default_effective_date: date | None = None,
    default_hs_version: str = "",
) -> list[TariffRuleRecord]:
    text = source_path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError(f"No tabular headers found in {source_path}")

    hs_header = _resolve_column(reader.fieldnames, "hs_code")
    scope_header = _resolve_column(reader.fieldnames, "product_scope")
    general_header = _resolve_column(reader.fieldnames, "general_rate")
    if hs_header is None or scope_header is None or general_header is None:
        raise ValueError("HTS input must contain HS code, product scope, and general rate columns")

    special_header = _resolve_column(reader.fieldnames, "special_rate_text")
    additional_header = _resolve_column(reader.fieldnames, "additional_duty_text")
    effective_header = _resolve_column(reader.fieldnames, "effective_date")
    end_header = _resolve_column(reader.fieldnames, "end_date")
    version_header = _resolve_column(reader.fieldnames, "hs_version")

    records: list[TariffRuleRecord] = []
    for row in reader:
        raw_hs_code = (row.get(hs_header) or "").strip()
        if not raw_hs_code:
            continue
        general_rate = (row.get(general_header) or "").strip()
        if not general_rate:
            continue
        effective_date = parse_optional_date(row.get(effective_header)) or default_effective_date
        if effective_date is None:
            raise ValueError(f"Missing effective date for HS code {raw_hs_code!r}")
        records.append(
            TariffRuleRecord(
                market=market,
                jurisdiction=jurisdiction,
                hs_code=normalize_hs_code(raw_hs_code),
                hs_version=(row.get(version_header) or default_hs_version).strip(),
                product_scope=(row.get(scope_header) or "").strip(),
                general_rate=general_rate,
                special_rate_text=(row.get(special_header) or "").strip() if special_header else "",
                additional_duty_text=(row.get(additional_header) or "").strip()
                if additional_header
                else "",
                effective_date=effective_date,
                end_date=parse_optional_date(row.get(end_header)) if end_header else None,
                source_name=source_name,
                source_url=source_url,
            )
        )
    return records


def write_normalized_jsonl(records: Iterable[TariffRuleRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(_record_to_json(record), ensure_ascii=False) for record in records]
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def build_tariff_database(
    records: Sequence[TariffRuleRecord],
    database_path: Path,
    *,
    metadata: dict[str, str] | None = None,
) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("DROP TABLE IF EXISTS tariff_rules")
        connection.execute("DROP TABLE IF EXISTS import_metadata")
        connection.execute(
            """
            CREATE TABLE tariff_rules (
                market TEXT NOT NULL,
                jurisdiction TEXT NOT NULL,
                hs_code TEXT NOT NULL,
                hs_version TEXT NOT NULL,
                product_scope TEXT NOT NULL,
                general_rate TEXT NOT NULL,
                special_rate_text TEXT NOT NULL,
                additional_duty_text TEXT NOT NULL,
                effective_date TEXT NOT NULL,
                end_date TEXT,
                source_name TEXT NOT NULL,
                source_url TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE import_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO tariff_rules (
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    record.market,
                    record.jurisdiction,
                    record.hs_code,
                    record.hs_version,
                    record.product_scope,
                    record.general_rate,
                    record.special_rate_text,
                    record.additional_duty_text,
                    record.effective_date.isoformat(),
                    record.end_date.isoformat() if record.end_date else None,
                    record.source_name,
                    record.source_url,
                )
                for record in records
            ],
        )
        connection.execute(
            "CREATE INDEX idx_tariff_rules_lookup ON tariff_rules (jurisdiction, hs_code, effective_date)"
        )
        metadata_rows = {
            "record_count": str(len(records)),
            **(metadata or {}),
        }
        connection.executemany(
            "INSERT INTO import_metadata (key, value) VALUES (?, ?)",
            sorted(metadata_rows.items()),
        )
        connection.commit()


def _record_to_json(record: TariffRuleRecord) -> dict[str, object]:
    payload = asdict(record)
    payload["effective_date"] = record.effective_date.isoformat()
    payload["end_date"] = record.end_date.isoformat() if record.end_date else None
    return payload
