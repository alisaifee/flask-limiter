"""
errors and exceptions
"""

import sys
from distutils.version import LooseVersion
from pkg_resources import get_distribution
from werkzeug import exceptions

PY2 = sys.version_info[0] == 2

if PY2:
    text_type = unicode
else:
    text_type = str


werkzeug_version = get_distribution("werkzeug").version
if LooseVersion(werkzeug_version) < LooseVersion("0.9"):  # pragma: no cover
    # sorry, for touching your internals :).
    import werkzeug._internal
    werkzeug._internal.HTTP_STATUS_CODES[429] = 'Too Many Requests'

    class RateLimitExceeded(exceptions.HTTPException):
        """
        exception raised when a rate limit is hit.
        The exception results in ``abort(429)`` being called.
        """
        code = 429

        def __init__(self, limit):
            self.description = text_type(limit)
            super(RateLimitExceeded, self).__init__()
else:
    # Werkzeug 0.9 and up have an existing exception for 429
    RateLimitExceeded = exceptions.TooManyRequests
