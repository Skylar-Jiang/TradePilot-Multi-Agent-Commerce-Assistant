from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
import yaml

from app.background.contracts import BackgroundQuery
from app.background.tariff_data import TariffRuleRecord, build_tariff_database
from app.core.config import Settings
from app.main import create_app


def test_create_app_auto_registers_us_tariff_provider_when_local_artifacts_exist(
    tmp_path: Path,
) -> None:
    mapping_path, database_path = _write_tariff_artifacts(tmp_path)
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path / 'app.db'}",
        report_dir=tmp_path / "reports",
        upload_dir=tmp_path / "uploads",
        chroma_dir=tmp_path / "chroma",
        chroma_persist_dir=tmp_path / "chroma",
        trade_hs_mapping_path=mapping_path,
        trade_tariff_db_path=database_path,
    )

    with TestClient(create_app(settings)) as client:
        result = client.app.state.background_registry.query(
            BackgroundQuery(
                product_name="Cordless pet water fountain",
                product_type="pet water fountain",
                market="United States",
                jurisdiction="US",
                context_types=["tariff_rate"],
                effective_date=date(2026, 7, 16),
                query_date=date(2026, 7, 16),
            )
        )

    assert result is not None
    assert result.provider == "us-tariff-provider"
    assert len(result.evidence) == 1
    assert result.evidence[0].source_name == "USITC Harmonized Tariff Schedule"
    assert "General duty rate: Free." in result.evidence[0].content


def _write_tariff_artifacts(tmp_path: Path) -> tuple[Path, Path]:
    mapping_path = tmp_path / "config" / "trade" / "hs_mapping.yaml"
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.write_text(
        yaml.safe_dump(
            {
                "mappings": [
                    {
                        "segment_id": "pet_water_fountain",
                        "product_types": ["pet water fountain"],
                        "keywords": ["pet fountain"],
                        "hs_codes": [
                            {
                                "hs_code": "8421210000",
                                "confidence": 0.74,
                                "rationale": "Phase 1 candidate mapping for pet fountains.",
                            }
                        ],
                        "notes": "Use only as a candidate mapping.",
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
                effective_date=date(2026, 7, 16),
                end_date=None,
                source_name="USITC Harmonized Tariff Schedule",
                source_url="https://hts.usitc.gov/export",
            )
        ],
        database_path,
    )
    return mapping_path, database_path
