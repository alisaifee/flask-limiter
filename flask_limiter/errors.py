"""errors and exceptions."""

from werkzeug import exceptions


class RateLimitExceeded(exceptions.TooManyRequests):
    """exception raised when a rate limit is hit.

    The exception results in ``abort(429)`` being called.
    """

    def __init__(self, limit):
        self.limit = limit

        if limit.error_message:
            description = (
                limit.error_message
                if not callable(limit.error_message)
                else limit.error_message()
            )
        else:
            description = str(limit.limit)
        super(RateLimitExceeded, self).__init__(description=description)
