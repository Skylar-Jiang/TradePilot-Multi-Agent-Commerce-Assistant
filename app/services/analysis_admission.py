from collections import deque
from collections.abc import Callable
from threading import Lock
from time import monotonic
from typing import TypeVar

from app.core.exceptions import AnalysisRateLimitedError

T = TypeVar("T")


class AnalysisAdmission:
    def __init__(self, *, requests: int, window_seconds: int) -> None:
        self.requests = requests
        self.window_seconds = window_seconds
        self._accepted_at: deque[float] = deque()
        self._lock = Lock()

    def admit(self, create: Callable[[], T]) -> T:
        with self._lock:
            now = monotonic()
            cutoff = now - self.window_seconds
            while self._accepted_at and self._accepted_at[0] <= cutoff:
                self._accepted_at.popleft()
            if len(self._accepted_at) >= self.requests:
                raise AnalysisRateLimitedError()
            result = create()
            self._accepted_at.append(now)
            return result
