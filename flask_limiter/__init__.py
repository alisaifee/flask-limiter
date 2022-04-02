"""Flask-Limiter extension for rate limiting."""
from . import _version
from .errors import RateLimitExceeded
from .extension import HEADERS, Limiter, RequestLimit

__all__ = ["RateLimitExceeded", "Limiter", "RequestLimit", "HEADERS"]

__version__ = _version.get_versions()["version"]
