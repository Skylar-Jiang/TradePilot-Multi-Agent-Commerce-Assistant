from datetime import date
from pathlib import Path

import yaml

from app.background.contracts import BackgroundQuery
from app.background.providers import build_default_background_registry
from app.background.providers.us_tariff_provider import USTariffProvider
from app.background.tariff_data import TariffRuleRecord, build_tariff_database
from app.core.config import Settings


def test_us_tariff_provider_returns_evidence_with_provenance(tmp_path: Path) -> None:
    mapping_path, database_path = _write_tariff_artifacts(tmp_path)
    provider = USTariffProvider(database_path=database_path, mapping_path=mapping_path)

    result = provider.query(
        BackgroundQuery(
            product_name="Cordless pet water fountain",
            product_type="Fountains",
            market="United States",
            jurisdiction="US",
            context_types=["tariff_rate"],
            effective_date=date(2026, 7, 1),
            query_date=date(2026, 7, 15),
        )
    )

    assert result.data_gaps == []
    assert len(result.evidence) == 1
    evidence = result.evidence[0]
    assert evidence.context_type == "tariff_rate"
    assert evidence.source_name == "USITC Harmonized Tariff Schedule"
    assert evidence.source_uri == "https://hts.usitc.gov/export"
    assert "General duty rate: Free." in evidence.content
    assert "candidate HTS 8421210000" in evidence.content
    assert result.decision_inputs["primary_tariff_profile"]["hs_code"] == "8421210000"
    assert result.decision_inputs["manual_review_required"] is True
    assert "additional_duty_present" in result.decision_inputs["tariff_risk_flags"]
    assert result.decision_inputs["tariff_cost_burden"] == "high"
    assert "目标毛利" in result.decision_inputs["agent_decision_brief"]
    assert result.decision_inputs["tariff_recommended_actions"]


def test_us_tariff_provider_returns_data_gap_when_mapping_is_missing(tmp_path: Path) -> None:
    mapping_path, database_path = _write_tariff_artifacts(tmp_path)
    provider = USTariffProvider(database_path=database_path, mapping_path=mapping_path)

    result = provider.query(
        BackgroundQuery(
            product_name="Mystery feeder",
            product_type="automatic pet feeder",
            market="United States",
            jurisdiction="US",
            context_types=["tariff_rate"],
            effective_date=date(2026, 7, 1),
            query_date=date(2026, 7, 15),
        )
    )

    assert result.evidence == []
    assert [gap.code for gap in result.data_gaps] == ["missing_hs_mapping"]


def test_us_tariff_provider_supports_existing_shampoos_category(tmp_path: Path) -> None:
    mapping_path, database_path = _write_tariff_artifacts(tmp_path)
    provider = USTariffProvider(database_path=database_path, mapping_path=mapping_path)

    result = provider.query(
        BackgroundQuery(
            product_name="Hypoallergenic dog shampoo",
            product_type="Shampoos",
            market="United States",
            jurisdiction="US",
            context_types=["tariff_rate"],
            effective_date=date(2026, 7, 1),
            query_date=date(2026, 7, 15),
        )
    )

    assert result.data_gaps == []
    assert len(result.evidence) == 1
    evidence = result.evidence[0]
    assert evidence.source_name == "USITC Harmonized Tariff Schedule"
    assert "candidate HTS 3305100000" in evidence.content
    assert "General duty rate: Free." in evidence.content


def test_default_background_registry_registers_provider_when_artifacts_exist(tmp_path: Path) -> None:
    mapping_path, database_path = _write_tariff_artifacts(tmp_path)
    settings = Settings(
        _env_file=None,
        database_url="sqlite://",
        trade_hs_mapping_path=mapping_path,
        trade_tariff_db_path=database_path,
    )

    registry = build_default_background_registry(settings)
    result = registry.query(
        BackgroundQuery(
            product_name="Cordless pet water fountain",
            product_type="Fountains",
            market="United States",
            jurisdiction="US",
            context_types=["tariff_rate"],
            effective_date=date(2026, 7, 1),
            query_date=date(2026, 7, 15),
        )
    )

    assert result is not None
    assert result.provider == "us-tariff-provider"
    assert len(result.evidence) == 1


def test_us_tariff_provider_supports_existing_retractable_leashes_category(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "external" / "serving" / "tariff_rules.sqlite"
    build_tariff_database(
        [
            TariffRuleRecord(
                market="United States",
                jurisdiction="US",
                hs_code="4201006000",
                hs_version="2026 Rev. 11",
                product_scope="Saddlery and harness for any animal",
                general_rate="2.4%",
                special_rate_text="",
                additional_duty_text="",
                effective_date=date(2026, 1, 1),
                end_date=None,
                source_name="USITC Harmonized Tariff Schedule",
                source_url="https://hts.usitc.gov/export",
            )
        ],
        database_path,
    )
    provider = USTariffProvider(
        database_path=database_path,
        mapping_path=Path(__file__).resolve().parents[3] / "config" / "trade" / "hs_mapping.yaml",
    )

    result = provider.query(
        BackgroundQuery(
            product_name="Reflective retractable dog leash",
            product_type="Retractable Leashes",
            market="United States",
            jurisdiction="US",
            context_types=["tariff_rate"],
            effective_date=date(2026, 7, 1),
            query_date=date(2026, 7, 15),
        )
    )

    assert result.data_gaps == []
    assert len(result.evidence) == 1
    assert "candidate HTS 4201006000" in result.evidence[0].content
    assert result.decision_inputs["primary_tariff_profile"]["hs_code"] == "4201006000"
    assert "non_free_general_rate" in result.decision_inputs["tariff_risk_flags"]
    assert result.decision_inputs["tariff_cost_burden"] == "medium"


def test_us_tariff_provider_supports_exact_dog_harness_alias_from_existing_categories(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "external" / "serving" / "tariff_rules.sqlite"
    build_tariff_database(
        [
            TariffRuleRecord(
                market="United States",
                jurisdiction="US",
                hs_code="4201006000",
                hs_version="2026 Rev. 11",
                product_scope="Saddlery and harness for any animal",
                general_rate="2.4%",
                special_rate_text="",
                additional_duty_text="",
                effective_date=date(2026, 1, 1),
                end_date=None,
                source_name="USITC Harmonized Tariff Schedule",
                source_url="https://hts.usitc.gov/export",
            )
        ],
        database_path,
    )
    provider = USTariffProvider(
        database_path=database_path,
        mapping_path=Path(__file__).resolve().parents[3] / "config" / "trade" / "hs_mapping.yaml",
    )

    result = provider.query(
        BackgroundQuery(
            product_name="No-pull dog harness",
            product_type="dog harness",
            market="United States",
            jurisdiction="US",
            context_types=["tariff_rate"],
            effective_date=date(2026, 7, 1),
            query_date=date(2026, 7, 15),
        )
    )

    assert result.data_gaps == []
    assert len(result.evidence) == 1
    assert result.decision_inputs["primary_tariff_profile"]["hs_code"] == "4201006000"


def _write_tariff_artifacts(tmp_path: Path) -> tuple[Path, Path]:
    mapping_path = tmp_path / "config" / "trade" / "hs_mapping.yaml"
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.write_text(
        yaml.safe_dump(
            {
                "mappings": [
                    {
                        "segment_id": "fountains",
                        "product_types": ["Fountains"],
                        "keywords": ["pet fountain"],
                        "hs_codes": [
                            {
                                "hs_code": "8421210000",
                                "confidence": 0.74,
                                "rationale": "Phase 1 candidate mapping for pet fountains.",
                            }
                        ],
                        "notes": "Use only as a candidate mapping for the existing Fountains category.",
                    },
                    {
                        "segment_id": "shampoos",
                        "product_types": ["Shampoos"],
                        "keywords": ["pet shampoo"],
                        "hs_codes": [
                            {
                                "hs_code": "3305100000",
                                "confidence": 0.78,
                                "rationale": "Phase 1 candidate mapping for the existing Shampoos category.",
                            }
                        ],
                        "notes": "Use only as a candidate mapping for the existing Shampoos category.",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    database_path = tmp_path / "data" / "external" / "serving" / "tariff_rules.sqlite"
    build_tariff_database(
        [
            TariffRuleRecord(
                market="United States",
                jurisdiction="US",
                hs_code="8421210000",
                hs_version="2026 Rev. 11",
                product_scope="Filtering or purifying machinery for liquids",
                general_rate="Free",
                special_rate_text="",
                additional_duty_text="25%",
                effective_date=date(2026, 1, 1),
                end_date=None,
                source_name="USITC Harmonized Tariff Schedule",
                source_url="https://hts.usitc.gov/export",
            ),
            TariffRuleRecord(
                market="United States",
                jurisdiction="US",
                hs_code="3305100000",
                hs_version="2026 Rev. 11",
                product_scope="Shampoos",
                general_rate="Free",
                special_rate_text="",
                additional_duty_text="",
                effective_date=date(2026, 1, 1),
                end_date=None,
                source_name="USITC Harmonized Tariff Schedule",
                source_url="https://hts.usitc.gov/export",
            )
        ],
        database_path,
    )
    return mapping_path, database_path
