from importlib import import_module
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from app.adapters.base import DomainAdapter
from app.core.enums import DataOrigin, ImplementationStatus, KnowledgeType

DEFAULT_PROFILES_DIR = Path(__file__).resolve().parents[2] / "config" / "domain_profiles"


class DomainProfile(BaseModel):
    profile_id: str
    display_name: str
    data_origin: DataOrigin
    implementation_status: ImplementationStatus
    adapter: str
    knowledge_domains: list[KnowledgeType] = Field(default_factory=list)
    notes: str = ""


def load_domain_profile(
    profile_id: str,
    *,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
) -> DomainProfile:
    for path in sorted(profiles_dir.glob("*.yaml")):
        profile = DomainProfile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        if profile.profile_id == profile_id:
            return profile
    raise ValueError(f"Unknown domain profile: {profile_id}")


def load_domain_adapter(profile: DomainProfile) -> DomainAdapter:
    module_name, class_name = profile.adapter.rsplit(".", 1)
    adapter_class = getattr(import_module(module_name), class_name)
    adapter = adapter_class()
    if not isinstance(adapter, DomainAdapter):
        raise TypeError(f"Configured adapter does not implement DomainAdapter: {profile.adapter}")
    return adapter
