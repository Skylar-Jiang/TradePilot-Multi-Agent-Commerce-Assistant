from __future__ import annotations

from app.background.providers.us_tariff_provider import USTariffProvider
from app.background.registry import BackgroundProviderRegistry
from app.core.config import Settings


def build_default_background_registry(settings: Settings) -> BackgroundProviderRegistry:
    registry = BackgroundProviderRegistry()
    if settings.trade_tariff_db_path.is_file() and settings.trade_hs_mapping_path.is_file():
        registry.register(
            USTariffProvider(
                database_path=settings.trade_tariff_db_path,
                mapping_path=settings.trade_hs_mapping_path,
            )
        )
    return registry


__all__ = ["USTariffProvider", "build_default_background_registry"]
