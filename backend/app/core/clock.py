from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class IClock(Protocol):
    def now(self) -> datetime: ...


class RealClock:
    def now(self) -> datetime:
        return datetime.now(tz=UTC)


class FrozenClock:
    def __init__(self, frozen_at: datetime) -> None:
        if frozen_at.tzinfo is None:
            raise ValueError("FrozenClock requires tz-aware datetime")
        self._t = frozen_at

    def now(self) -> datetime:
        return self._t

    def advance(self, seconds: float) -> None:
        from datetime import timedelta

        self._t = self._t + timedelta(seconds=seconds)


_default_clock: IClock = RealClock()


def get_clock() -> IClock:
    return _default_clock


def set_clock(clock: IClock) -> None:
    global _default_clock
    _default_clock = clock
