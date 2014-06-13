"""
errors and exceptions
"""

from werkzeug.exceptions import HTTPException

def _patch_werkzeug():
    import pkg_resources
    if pkg_resources.get_distribution("werkzeug").version < "0.9":
        # sorry, for touching your internals :).
        import werkzeug._internal
        werkzeug._internal.HTTP_STATUS_CODES[429] = 'Too Many Requests'

_patch_werkzeug()
del _patch_werkzeug

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
