"""Clock abstraction for controlling time in tests.

All code that needs the current time should use a Clock instance
rather than calling datetime.now() directly. This makes time-based
logic testable by injecting a frozen or configurable clock.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone


class Clock(ABC):
    """Abstract clock that provides the current time.

    Usage:
        class SystemClock(Clock):
            def now(self) -> datetime:
                return datetime.now(timezone.utc)

        class FrozenClock(Clock):
            def __init__(self, fixed_time: datetime | None = None):
                self._fixed = fixed_time or datetime(2026, 1, 1, tzinfo=timezone.utc)
            def now(self) -> datetime:
                return self._fixed
    """

    @abstractmethod
    def now(self) -> datetime:
        """Return the current datetime in UTC."""
        ...

    def utcnow(self) -> datetime:
        """Alias for now()."""
        return self.now()

    def today(self) -> datetime:
        """Return the start of the current day (midnight UTC)."""
        dt = self.now()
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)


class SystemClock(Clock):
    """Wall-clock implementation that returns real UTC time."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FrozenClock(Clock):
    """Frozen clock for testing. Always returns the configured time."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        self._fixed = fixed_time or datetime(2026, 1, 1, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._fixed

    def advance(self, delta: timedelta) -> None:
        """Advance the frozen clock by a timedelta."""
        self._fixed += delta
