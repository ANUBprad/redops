"""Common value objects shared across bounded contexts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from app.kernel.entities.base import ValueObject


@dataclass(frozen=True, slots=True)
class Email(ValueObject):
    """Immutable email address value object with validation."""

    address: str
    _pattern: ClassVar[str] = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    def __post_init__(self) -> None:
        if not re.match(self._pattern, self.address):
            raise ValueError(f"Invalid email address: {self.address}")


@dataclass(frozen=True, slots=True)
class URL(ValueObject):
    """Immutable URL value object with basic validation."""

    value: str
    _pattern: ClassVar[str] = r"^https?://[^\s/$.?#].[^\s]*$"

    def __post_init__(self) -> None:
        if not re.match(self._pattern, self.value):
            raise ValueError(f"Invalid URL: {self.value}")


@dataclass(frozen=True, slots=True)
class NonEmptyString(ValueObject):
    """A string that must not be empty or whitespace-only."""

    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        if not stripped:
            raise ValueError("Value must not be empty")
        object.__setattr__(self, "value", stripped)


@dataclass(frozen=True, slots=True)
class Percentage(ValueObject):
    """A value between 0.0 and 1.0 (inclusive)."""

    value: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"Percentage must be between 0.0 and 1.0, got {self.value}")
