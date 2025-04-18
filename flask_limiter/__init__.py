"""Flask-Limiter extension for rate limiting."""

from __future__ import annotations

from . import _version
from .constants import ExemptionScope, HeaderNames
from .errors import RateLimitExceeded
from .extension import Limiter, RequestLimit

__all__ = [
    "ExemptionScope",
    "HeaderNames",
    "Limiter",
    "RateLimitExceeded",
    "RequestLimit",
]

#: Aliased for backward compatibility
HEADERS = HeaderNames

__version__ = _version.get_versions()["version"]
