"""

"""
from abc import abstractmethod, ABCMeta
try:
    from collections import Counter
except ImportError:
    from .backports.counter import Counter # pragma: no cover

import threading
import time

import six

from .errors import ConfigurationError
from .util import get_dependency


@six.add_metaclass(ABCMeta)
class Storage(object):
    def __init__(self):
        """


        """
        self.lock = threading.RLock()

    @abstractmethod
    def incr(self, key, expiry, elastic_expiry=False):
        """
        increments the counter for a given rate limit key

        :param str key: the key to increment
        :param int expiry: amount in seconds for the key to expire in
        :param bool elastic_expiry: whether to keep extending the rate limit
         window every hit.
        """
        raise NotImplementedError

    @abstractmethod
    def get(self, key):
        """
        :param str key: the key to get the counter value for
        """
        raise NotImplementedError

class LockableEntry(threading._RLock):
    __slots__ = ["atime", "expiry"]
    def __init__(self, expiry):
        self.atime = time.time()
        self.expiry = self.atime + expiry
        super(LockableEntry, self).__init__()

class MemoryStorage(Storage):
    """
    rate limit storage using :class:`collections.Counter`
    as an in memory storage.

    """

    def __init__(self):
        self.storage = Counter()
        self.expirations = {}
        self.events = {}
        self.timer = threading.Timer(0.01, self.__expire_events)
        self.timer.start()
        super(MemoryStorage, self).__init__()

    def __expire_events(self):
        for key in self.events:
            for event in list(self.events[key]):
                with event:
                    if event.expiry > time.time() and event in self.events[key]:
                        self.events[key].remove(event)
        for key in list(self.expirations.keys()):
            if self.expirations[key] <= time.time():
                self.storage.pop(key)
                self.expirations.pop(key)

    def __schedule_expiry(self):
        if not self.timer.is_alive:
            self.timer = threading.Timer(0.01, self.__expire_events)
            self.timer.start()

    def incr(self, key, expiry, elastic_expiry=False):
        """
        increments the counter for a given rate limit key

        :param str key: the key to increment
        :param int expiry: amount in seconds for the key to expire in
        :param bool elastic_expiry: whether to keep extending the rate limit
         window every hit.
        """
        self.get(key)
        self.storage[key] += 1
        if elastic_expiry or self.storage[key] == 1:
            self.expirations[key] = time.time() + expiry
        return self.storage.get(key, 0)

    def get(self, key):
        """
        :param str key: the key to get the counter value for
        """
        if self.expirations.get(key, 0) <= time.time():
            if key in self.storage:
                self.storage.pop(key)
            if key in self.expirations:
                self.expirations.pop(key)
        return self.storage.get(key, 0)

    def acquire_entry(self, key, limit, expiry, no_add=False):
        """
        :param str key: rate limit key to acquire an entry in
        :param int limit: amount of entries allowed
        :param int expiry: expiry of the entry
        :param bool no_add: if False an entry is not actually acquired but instead
         serves as a 'check'
        :return: True/False
        """
        self.events.setdefault(key, [])
        self.__schedule_expiry()
        timestamp = time.time()
        try:
            entry = self.events[key][limit - 1]
        except IndexError:
            entry = None
        if entry and entry.atime >= timestamp - expiry:
            with entry:
                if entry in self.events[key]:
                    self.events[key].remove(entry)
            return False
        else:
            if not no_add:
                self.events[key].insert(0, LockableEntry(expiry))
            return True

class RedisStorage(Storage):
    """
    rate limit storage with redis as backend
    """
    def __init__(self, redis_url):
        """
        :param str redis_url: url of the form 'redis://host:port'
        :raise ConfigurationError: when the redis library is not available
         or if the redis host cannot be pinged.
        """
        if not get_dependency("redis"):
            raise ConfigurationError("redis prerequisite not available") # pragma: no cover
        self.storage = get_dependency("redis").from_url(redis_url)
        if not self.storage.ping():
            raise ConfigurationError("unable to connect to redis at %s" % redis_url) # pragma: no cover
        super(RedisStorage, self).__init__()

    def incr(self, key, expiry, elastic_expiry=False):
        """
        increments the counter for a given rate limit key

        :param str key: the key to increment
        :param int expiry: amount in seconds for the key to expire in
        """
        value = self.storage.incr(key)
        if elastic_expiry or value == 1:
            self.storage.expire(key, expiry)
        return value

    def get(self, key):
        """
        :param str key: the key to get the counter value for
        """
        return int(self.storage.get(key))

    def acquire_entry(self, key, limit, expiry, no_add=False):
        """
        :param str key: rate limit key to acquire an entry in
        :param int limit: amount of entries allowed
        :param int expiry: expiry of the entry
        :param bool no_add: if False an entry is not actually acquired but instead
         serves as a 'check'
        :return: True/False
        """
        timestamp = time.time()
        with self.storage.lock("%s/LOCK" % key):
            entry = self.storage.lindex(key, limit - 1)
            if entry and float(entry) >= timestamp - expiry:
                return False
            else:
                if not no_add:
                    with self.storage.pipeline() as pipeline:
                        pipeline.lpush(key, timestamp)
                        pipeline.ltrim(key, 0, limit - 1)
                        pipeline.expire(key, expiry)
                        pipeline.execute()
                return True

class MemcachedStorage(Storage):
    """
    rate limit storage with memcached as backend
    """
    MAX_CAS_RETRIES = 10

    def __init__(self, host, port):
        """
        :param str host: memcached host
        :param int port: memcached port
        :raise ConfigurationError: when pymemcached is not available
        """
        if not get_dependency("pymemcache"):
            raise ConfigurationError("memcached prerequisite not available."
                                     " please install pymemcache")  # pragma: no cover
        self.host, self.port = host, port
        self.local_storage = threading.local()
        self.local_storage.storage = None

    @property
    def storage(self):
        """
        lazily creates a memcached client instance using a thread local
        """
        if not (hasattr(self.local_storage, "storage") and self.local_storage.storage):
            self.local_storage.storage = get_dependency(
                "pymemcache.client"
            ).client.Client((self.host, self.port))
        return self.local_storage.storage

    def get(self, key):
        """
        :param str key: the key to get the counter value for
        """
        return int(self.storage.get(key) or 0)

    def incr(self, key, expiry, elastic_expiry=False):
        """
        increments the counter for a given rate limit key

        :param str key: the key to increment
        :param int expiry: amount in seconds for the key to expire in
        :param bool elastic_expiry: whether to keep extending the rate limit
         window every hit.
        """
        if not self.storage.add(key, 1, expiry, noreply=False):
            if elastic_expiry:
                value, cas = self.storage.gets(key)
                retry = 0
                while (
                        not self.storage.cas(key, int(value)+1, cas, expiry)
                        and retry < self.MAX_CAS_RETRIES
                ):
                    value, cas = self.storage.gets(key)
                    retry += 1
                return int(value) + 1
            else:
                return self.storage.incr(key, 1)
        return 1
