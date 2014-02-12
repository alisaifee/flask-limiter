"""

"""
from werkzeug.exceptions import abort


class ConfigurationError(Exception):
    pass

class RateLimitExceeded(Exception):
    def __init__(self, msg=None):
        abort(429, msg)
