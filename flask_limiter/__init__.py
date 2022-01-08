"""Flask-Limiter extension for rate limiting."""
from ._version import get_versions
from .errors import RateLimitExceeded
from .extension import HEADERS, Limiter, LimitDetail

__version__ = get_versions()["version"]
del get_versions

__all__ = ["RateLimitExceeded", "Limiter", "LimitDetail", "HEADERS"]
