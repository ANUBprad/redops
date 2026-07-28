"""Provider-specific error model.

Extends the Kernel error hierarchy with provider-domain errors.
All provider failures should raise typed exceptions from this
module rather than raw SDK or HTTP errors.
"""

from __future__ import annotations

from app.providers.exceptions.auth import AuthenticationRequired
from app.providers.exceptions.availability import ProviderUnavailable
from app.providers.exceptions.base import ProviderException
from app.providers.exceptions.limits import (
    ContextWindowExceeded,
    TokenLimitExceeded,
)
from app.providers.exceptions.model import InvalidModel
from app.providers.exceptions.rate_limit import RateLimitExceeded
from app.providers.exceptions.streaming import StreamingFailure
from app.providers.exceptions.timeout import ProviderTimeout

__all__ = [
    "AuthenticationRequired",
    "ContextWindowExceeded",
    "InvalidModel",
    "ProviderException",
    "ProviderTimeout",
    "ProviderUnavailable",
    "RateLimitExceeded",
    "StreamingFailure",
    "TokenLimitExceeded",
]
