from collections.abc import Callable

from sqlalchemy.orm import Session

from app.statistics.contracts import StatisticsProvider
from app.statistics.stub import ScaffoldStatisticsProvider

StatisticsProviderFactory = Callable[[Session], StatisticsProvider]


def create_statistics_provider(session: Session) -> StatisticsProvider:
    del session
    return ScaffoldStatisticsProvider()
