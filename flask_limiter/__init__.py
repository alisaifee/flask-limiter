"""Flask-Limiter extension for rate limiting."""
from . import _version
from .errors import RateLimitExceeded
from .extension import HEADERS, ExemptionScope, Limiter, RequestLimit

__all__ = ["HEADERS", "ExemptionScope", "Limiter", "RateLimitExceeded", "RequestLimit"]

__version__ = _version.get_versions()["version"]
