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

    @abstractmethod
    def delete(self, key):
        raise NotImplementedError

    @contextmanager
    def ctx(self):
        self.lock.acquire()
        yield
        self.lock.release()


class MemoryStorage(Storage):
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

    def delete(self, key):
        if key in self.storage:
            self.storage.pop(key)

    def get(self, key):
        with self.ctx():
            if self.expirations.get(key, 0) <= time.time():
                self.delete(key)
            return self.storage.get(key, 0)

class RedisStorage(Storage):
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

    def delete(self, key):
        self.storage.delete(key)

    def get(self, key):
        return self.storage.get(key)
