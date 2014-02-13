"""

"""
import re
from six.moves import urllib
from flask import request
from .limits import GRANULARITIES
from .errors import ConfigurationError

EXPR = re.compile(
    r"\s*([0-9]+)\s*(/|\s*per\s*)\s*([0-9]+)*\s*(hour|minute|second|day|month|year)[s]*",
    re.IGNORECASE
)

def get_dependency(dep):
    """
    safe function to import a module programmatically
    :return: module or None (if not importable)
    """
    try:
        return __import__(dep)
    except ImportError: # pragma: no cover
        return None


def parse_many(limit_string):
    """

    :param limit_string:
    :raise ValueError:
    """
    if not EXPR.match(limit_string):
        raise ValueError("couldn't parse rate limit string '%s'" % limit_string)
    for amount, _, multiples, granularity_string in  EXPR.findall(limit_string):
        granularity = granularity_from_string(granularity_string)
        yield granularity(amount, multiples)

def parse(limit_string):
    """

    :param limit_string:
    :return:
    """
    return list(parse_many(limit_string))[0]


def granularity_from_string(granularity_string):
    """

    :param granularity_string:
    :return: a :class:`flask_ratelimit.limits.Item`
    :raise ValueError:
    """
    for granularity in GRANULARITIES:
        if granularity.check_granularity_string(granularity_string):
            return granularity
    raise ValueError("no granularity matched for %s" % granularity_string)



def storage_from_string(storage_string):
    """

    :param storage_string: a string of the form method://host:port
    :return: a subclass of :class:`flask_limiter.storage.Storage`
    """
    from .storage import MemoryStorage, RedisStorage, MemcachedStorage
    parsed = urllib.parse.urlparse(storage_string)
    scheme = parsed.scheme
    if scheme == 'memory':
        return MemoryStorage()
    elif scheme == 'redis':
        return RedisStorage(storage_string)
    elif scheme == 'memcached':
        return MemcachedStorage(parsed.hostname, parsed.port or 11211)
    else:
        raise ConfigurationError("unknown storage scheme : %s" % storage_string)


def get_ipaddr():
    """
    :return: the ip address for the current request (or 127.0.0.1 if none found)
    """
    return request.remote_addr or '127.0.0.1'