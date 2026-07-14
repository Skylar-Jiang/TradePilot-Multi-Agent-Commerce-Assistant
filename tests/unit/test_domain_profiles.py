from pathlib import Path

from app.adapters.base import DomainAdapter
from app.adapters.profiles import load_domain_adapter, load_domain_profile
from app.core.enums import DataOrigin, ImplementationStatus

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_profile_loads_and_selects_its_adapter() -> None:
    profile = load_domain_profile(
        "generic_cross_border_demo",
        profiles_dir=ROOT / "config" / "domain_profiles",
    )
    adapter = load_domain_adapter(profile)

    assert profile.data_origin is DataOrigin.DEMO
    assert profile.implementation_status is ImplementationStatus.SCAFFOLD
    assert profile.knowledge_domains == ["product_knowledge", "review_insight"]
    assert isinstance(adapter, DomainAdapter)
    assert adapter.domain_name == profile.profile_id


def test_seed_script_does_not_select_a_concrete_adapter_in_code() -> None:
    source = (ROOT / "scripts" / "seed_demo.py").read_text(encoding="utf-8")

    assert "DemoDomainAdapter" not in source
    assert "load_domain_profile" in source
    assert "load_domain_adapter" in source


def test_pet_supplies_profile_loads_and_selects_its_adapter() -> None:
    profile = load_domain_profile(
        "pet_supplies",
        profiles_dir=ROOT / "config" / "domain_profiles",
    )
    adapter = load_domain_adapter(profile)

    assert profile.profile_id == "pet_supplies"
    assert profile.data_origin is DataOrigin.REAL
    assert profile.implementation_status is ImplementationStatus.SCAFFOLD
    assert isinstance(adapter, DomainAdapter)
    assert adapter.domain_name == "pet_supplies"
