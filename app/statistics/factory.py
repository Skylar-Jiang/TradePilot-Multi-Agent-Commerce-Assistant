from collections.abc import Callable

from sqlalchemy.orm import Session

from app.statistics.providers.pet_supplies import PetSuppliesStatisticsProvider
from app.statistics.contracts import StatisticsProvider

StatisticsProviderFactory = Callable[[Session], StatisticsProvider]


def create_statistics_provider(session: Session) -> StatisticsProvider:
    return PetSuppliesStatisticsProvider(session)
