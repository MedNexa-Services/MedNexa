"""Failed-login throttling (plan task 5.4 covers rate limiting; this protects sign-in).

In-memory and per process: enough for the single API process this project runs
today; a multi-worker deployment would need Redis (already in the compose file).
"""

import time
from collections import deque
from collections.abc import Callable

MAX_TRACKED_KEYS = 10_000


class FailedLoginLimiter:
    """Blocks a key after `max_failures` failed attempts within `window_seconds`."""

    def __init__(
        self,
        max_failures: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_failures
        self._window = window_seconds
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}

    def _recent(self, key: str) -> deque[float]:
        attempts = self._failures.get(key)
        if attempts is None:
            return deque()
        cutoff = self._clock() - self._window
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if not attempts:
            del self._failures[key]
        return attempts

    def retry_after(self, key: str) -> int:
        """Seconds until `key` may try again; 0 if it is not blocked."""
        attempts = self._recent(key)
        if len(attempts) < self._max:
            return 0
        return max(1, int(attempts[0] + self._window - self._clock()) + 1)

    def record_failure(self, key: str) -> None:
        if len(self._failures) >= MAX_TRACKED_KEYS:
            for stale in [k for k in self._failures if not self._recent(k)]:
                self._failures.pop(stale, None)
            if len(self._failures) >= MAX_TRACKED_KEYS:  # still full: drop the oldest key
                self._failures.pop(next(iter(self._failures)))
        self._failures.setdefault(key, deque()).append(self._clock())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)

    def clear(self) -> None:
        self._failures.clear()
