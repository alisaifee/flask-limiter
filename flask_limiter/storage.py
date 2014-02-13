"""

"""
from abc import abstractmethod, ABCMeta
from collections import Counter
from contextlib import contextmanager
import threading
import time

import six

from .errors import ConfigurationError
from .util import get_dependency


@six.add_metaclass(ABCMeta)
class Storage(object):
    def __init__(self):
        self.lock = threading.RLock()

    @abstractmethod
    def set_and_get(self, key, expiry):
        raise NotImplementedError

    @abstractmethod
    def get(self, key):
        raise NotImplementedError

    @contextmanager
    def ctx(self):
        self.lock.acquire()
        yield
        self.lock.release()


class MemoryStorage(Storage):
    """
    rate limit storage using :class:`collections.Counter`
    as an in memory storage.

    """
    def __init__(self):
        self.storage = Counter()
        self.expirations = {}
        super(MemoryStorage, self).__init__()

    def set_and_get(self, key, expiry):
        with self.ctx():
            # touch the key to expire if necessary
            self.get(key)
            self.storage[key] += 1
            self.expirations[key] = time.time() + expiry
            return self.storage.get(key, 0)

    def get(self, key):
        with self.ctx():
            if self.expirations.get(key, 0) <= time.time():
                if key in self.storage:
                    self.storage.pop(key)
                if key in self.expirations:
                    self.expirations.pop(key)
            return self.storage.get(key, 0)

class RedisStorage(Storage):
    """
    rate limit storage with redis as backend
    """
    def __init__(self, redis_url):
        if not get_dependency("redis"):
            raise ConfigurationError("redis prerequisite not available") # pragma: no cover
        self.storage = get_dependency("redis").from_url(redis_url)
        if not self.storage.ping():
            raise ConfigurationError("unable to connect to redis at %s" % redis_url) # pragma: no cover
        super(RedisStorage, self).__init__()

    def set_and_get(self, key, expiry):
        try:
            return self.storage.incr(key)
        finally:
            self.storage.expire(key, expiry)

    def get(self, key):
        return int(self.storage.get(key))


class MemcachedStorage(Storage):
    """
    rate limit storage with memcached as backend
    """
    def __init__(self, host, port):
        if not get_dependency("pymemcache"):
            raise ConfigurationError("memcached prerequisite not available."
                                     " please install pymemcache") # pragma: no cover
        self.storage = get_dependency("pymemcache.client").client.Client((host, port))

    def get(self, key):
        return int(self.storage.get(key) or 0)

    def set_and_get(self, key, expiry):
        if not self.storage.add(key, 1, expiry, noreply=False):
            value, cas = self.storage.gets(key)
            while not self.storage.cas(key, int(value)+1, cas, expiry):
                value, cas = self.storage.gets(key)
            return int(value) + 1
        return 1