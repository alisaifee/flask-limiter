"""errors and exceptions."""

from werkzeug import exceptions

from .wrappers import Limit


class RateLimitExceeded(exceptions.TooManyRequests):
    """Exception raised when a rate limit is hit."""

    def __init__(self, limit: Limit) -> None:
        self.limit = limit

        if limit.error_message:
            description = (
                limit.error_message
                if not callable(limit.error_message)
                else limit.error_message()
            )
        else:
            description = str(limit.limit)
        super().__init__(description=description)
