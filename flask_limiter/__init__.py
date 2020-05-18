"""Flask-Limiter extension for rate limiting."""
from ._version import get_versions
from .errors import RateLimitExceeded
from .extension import Limiter, HEADERS

__version__ = get_versions()['version']
del get_versions

__all__ = ['RateLimitExceeded', 'Limiter', 'HEADERS']
