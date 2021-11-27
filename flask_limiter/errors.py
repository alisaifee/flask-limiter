"""errors and exceptions."""

from distutils.version import LooseVersion
from pkg_resources import get_distribution
from six import text_type
from werkzeug import exceptions


class RateLimitExceeded(exceptions.TooManyRequests):
    """exception raised when a rate limit is hit.

    The exception results in ``abort(429)`` being called.
    """

    code = 429
    limit = None

    def __init__(self, limit):
        self.limit = limit

        if limit.error_message:
            description = (
                limit.error_message

                if not callable(limit.error_message)
                else limit.error_message()
            )
        else:
            description = text_type(limit.limit)
        super(RateLimitExceeded, self).__init__(description=description)
