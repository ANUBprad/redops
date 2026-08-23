"""Shared helpers for measurement-based metrics."""

from __future__ import annotations

from typing import Any


def as_number(value: Any) -> float | None:
    """Coerce metadata values into floats.

    The pipeline carries measured values (tokens, cost, latency) as
    strings, so numeric strings must be accepted alongside int/float.
    Returns None when the value cannot be interpreted as a number.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
