"""Flask-Limiter extension for rate limiting."""

from __future__ import annotations

from . import _version
from .constants import ExemptionScope, HeaderNames
from .errors import RateLimitExceeded
from .extension import Limiter, RequestLimit
from .limits import (
    ApplicationLimit,
    Limit,
    MetaLimit,
    RouteLimit,
)

__all__ = [
    "ExemptionScope",
    "HeaderNames",
    "Limiter",
    "Limit",
    "RouteLimit",
    "ApplicationLimit",
    "MetaLimit",
    "RateLimitExceeded",
    "RequestLimit",
]

__version__ = _version.get_versions()["version"]
