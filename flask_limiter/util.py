"""

"""
import re
from six.moves import urllib
from flask import request
from .limits import GRANULARITIES

EXPR = re.compile(
    r"\s*([0-9]+)\s*(/|\s*per\s*)\s*([0-9]+)*\s*(hour|minute|second|day|month|year)[s]*",
    re.IGNORECASE
)

def get_dependency(dep):
    try:
        return __import__(dep)
    except ImportError: # pragma: no cover
        return None


def parse_many(limit_string):
    if not EXPR.match(limit_string):
        raise ValueError("couldn't parse rate limit string '%s'" % limit_string)
    for amount, _, multiples, granularity_string in  EXPR.findall(limit_string):
        granularity = granularity_from_string(granularity_string)
        yield granularity(amount, multiples)

def parse(limit_string):
    return list(parse_many(limit_string))[0]


def granularity_from_string(granularity_string):
    for granularity in GRANULARITIES:
        if granularity.check_granularity_string(granularity_string):
            return granularity
    raise ValueError("no granularity matched for %s" % granularity_string)


def storage_from_string(storage_string):
    from .storage import MemoryStorage, RedisStorage
    scheme = urllib.parse.urlparse(storage_string).scheme
    if scheme == 'memory':
        return MemoryStorage()
    elif scheme == 'redis':
        return RedisStorage(storage_string)
    else:
        return None


def get_ipaddr():
    return request.remote_addr or '127.0.0.1'