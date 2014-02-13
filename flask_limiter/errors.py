"""

"""
from werkzeug.exceptions import abort


class ConfigurationError(Exception):
    pass

class RateLimitExceeded(Exception):
    def __init__(self, limit):
        abort(429, str(limit))
