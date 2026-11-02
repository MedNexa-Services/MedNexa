from __future__ import annotations

from telephony.config import get_settings


class Capacity:
    def __init__(self) -> None:
        self._active = 0

    @property
    def active(self) -> int:
        return self._active

    def full(self) -> bool:
        return self._active >= get_settings().max_concurrent_calls

    def try_acquire(self) -> bool:
        if self.full():
            return False
        self._active += 1
        return True

    def release(self) -> None:
        self._active = max(0, self._active - 1)


calls = Capacity()
