"""
errors and exceptions
"""

from werkzeug.exceptions import abort


class ConfigurationError(Exception):
    """
    exception raised when a configuration problem
    is encountered
    """
    pass

class RateLimitExceeded(Exception):
    """
    exception raised when a rate limit is hit.
    The exception results in ``abort(409)`` being called.
    """
    def __init__(self, limit):
        abort(429, str(limit))
