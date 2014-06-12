"""
errors and exceptions
"""

from werkzeug.exceptions import HTTPException


class ConfigurationError(Exception):
    """
    exception raised when a configuration problem
    is encountered
    """
    pass

class RateLimitExceeded(HTTPException):
    """
    exception raised when a rate limit is hit.
    The exception results in ``abort(409)`` being called.
    """
    code = 429
    def __init__(self, limit):
        self.description = str(limit)
        super(RateLimitExceeded, self).__init__()
