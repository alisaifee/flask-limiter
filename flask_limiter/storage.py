"""

"""
from abc import abstractmethod, ABCMeta

from six.moves import urllib


try:
    from collections import Counter
except ImportError: # pragma: no cover
    from .backports.counter import Counter # pragma: no cover

import threading
import time

import six

from .errors import ConfigurationError
from .util import get_dependency

SCHEMES = {}

def storage_from_string(storage_string):
    """

    :param storage_string: a string of the form method://host:port
    :return: a subclass of :class:`flask_limiter.storage.Storage`
    """
    scheme = urllib.parse.urlparse(storage_string).scheme
    if not scheme in SCHEMES:
        raise ConfigurationError("unknown storage scheme : %s" % storage_string)
    return SCHEMES[scheme](storage_string)

class StorageRegistry(type):
    def __new__(mcs, name, bases, dct):
        storage_scheme = dct.get('STORAGE_SCHEME', None)
        if not bases == (object,) and not storage_scheme:
            raise ConfigurationError("%s is not configured correctly, it must specify a STORAGE_SCHEME class attribute"  % name)
        cls = super(StorageRegistry, mcs).__new__(mcs, name, bases, dct)
        SCHEMES[storage_scheme] = cls
        return cls


@six.add_metaclass(StorageRegistry)
@six.add_metaclass(ABCMeta)
class Storage(object):
    def __init__(self, uri=None):
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

    @abstractmethod
    def get_expiry(self, key):
        """
        :param str key: the key to get the expiry for
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
    STORAGE_SCHEME = "memory"

    def __init__(self, uri=None):
        self.storage = Counter()
        self.expirations = {}
        self.events = {}
        self.timer = threading.Timer(0.01, self.__expire_events)
        self.timer.start()
        super(MemoryStorage, self).__init__(uri)

    def __expire_events(self):
        for key in self.events.keys():
            for event in list(self.events[key]):
                with event:
                    if event.expiry <= time.time() and event in self.events[key]:
                        self.events[key].remove(event)
        for key in list(self.expirations.keys()):
            if self.expirations[key] <= time.time():
                self.storage.pop(key, None)
                self.expirations.pop(key, None)

    def __schedule_expiry(self):
        if not self.timer.is_alive():
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
        self.__schedule_expiry()
        self.storage[key] += 1
        if elastic_expiry or self.storage[key] == 1:
            self.expirations[key] = time.time() + expiry
        return self.storage.get(key, 0)

    def get(self, key):
        """
        :param str key: the key to get the counter value for
        """
        if self.expirations.get(key, 0) <= time.time():
            self.storage.pop(key, None)
            self.expirations.pop(key, None)
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
            return False
        else:
            if not no_add:
                self.events[key].insert(0, LockableEntry(expiry))
            return True

    def get_expiry(self, key):
        """
        :param str key: the key to get the expiry for
        """
        return int(self.expirations.get(key, -1))

    def get_num_acquired(self, key, expiry):
        """
        returns the number of entries already acquired

        :param str key: rate limit key to acquire an entry in
        :param int expiry: expiry of the entry
        """
        timestamp = time.time()
        return len(
            [k for k in self.events[key] if k.atime >= timestamp - expiry]
        ) if self.events.get(key) else 0

    def get_moving_window(self, key, limit, expiry):
        """
        returns the starting point and the number of entries in the moving window

        :param str key: rate limit key
        :param int expiry: expiry of entry
        """
        timestamp = time.time()
        acquired = self.get_num_acquired(key, expiry)
        for item in self.events.get(key):
            if item.atime >= timestamp - expiry:
                return int(item.atime), acquired
        return int(timestamp), acquired

class RedisStorage(Storage):
    """
    rate limit storage with redis as backend
    """

    STORAGE_SCHEME = "redis"
    SCRIPT_MOVING_WINDOW = """
        local items = redis.call('lrange', KEYS[1], 0, tonumber(ARGV[2]))
        local expiry = tonumber(ARGV[1])
        local a = 0
        local oldest = nil
        for idx=1,#items do
            if tonumber(items[idx]) >= expiry then
                a = a + 1
                if oldest == nil then
                    oldest = tonumber(items[idx])
                end
            else
                break
            end
        end
        return {oldest, a}
        """

    def __init__(self, uri):
        """
        :param str redis_url: url of the form 'redis://host:port'
        :raise ConfigurationError: when the redis library is not available
         or if the redis host cannot be pinged.
        """
        if not get_dependency("redis"):
            raise ConfigurationError("redis prerequisite not available") # pragma: no cover
        self.storage = get_dependency("redis").from_url(uri)
        self.initialize_storage(uri)
        super(RedisStorage, self).__init__()

    def initialize_storage(self, uri):
        if not self.storage.ping():
            raise ConfigurationError("unable to connect to redis at %s" % uri) # pragma: no cover
        self.lua_moving_window = self.storage.register_script(
            RedisStorage.SCRIPT_MOVING_WINDOW
        )
        self.lock_impl = self.storage.lock

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
        return int(self.storage.get(key) or 0)

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
        with self.lock_impl("%s/LOCK" % key):
            entry = self.storage.lindex(key, limit - 1)
            if entry and float(entry) >= timestamp - expiry:
                return False
            else:
                if not no_add:
                    with self.storage.pipeline(transaction=False) as pipeline:
                        pipeline.lpush(key, timestamp)
                        pipeline.ltrim(key, 0, limit - 1)
                        pipeline.expire(key, expiry)
                        pipeline.execute()
                return True

    def get_moving_window(self, key, limit, expiry):
        """
        returns the starting point and the number of entries in the moving window

        :param str key: rate limit key
        :param int expiry: expiry of entry
        """
        timestamp = time.time()
        window = self.lua_moving_window(
            [key], [int(timestamp - expiry), limit]
        )
        return window or (timestamp, 0)

    def get_expiry(self, key):
        """
        :param str key: the key to get the expiry for
        """
        return int((self.storage.ttl(key) or 0) + time.time())

class MemcachedStorage(Storage):
    """
    rate limit storage with memcached as backend
    """
    MAX_CAS_RETRIES = 10
    STORAGE_SCHEME = "memcached"

    def __init__(self, uri):
        """
        :param str host: memcached host
        :param int port: memcached port
        :raise ConfigurationError: when pymemcached is not available
        """
        parsed = urllib.parse.urlparse(uri)
        self.cluster = []
        for loc in parsed.netloc.split(","):
            host, port = loc.split(":")
            self.cluster.append((host, int(port)))

        if not get_dependency("pymemcache"):
            raise ConfigurationError("memcached prerequisite not available."
                                     " please install pymemcache")  # pragma: no cover
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
            ).Client(*self.cluster)
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
                        not self.storage.cas(key, int(value or 0)+1, cas, expiry)
                        and retry < self.MAX_CAS_RETRIES
                ):
                    value, cas = self.storage.gets(key)
                    retry += 1
                self.storage.set(key + "/expires", expiry + time.time(), expire=expiry, noreply=False)
                return int(value or 0) + 1
            else:
                return self.storage.incr(key, 1)
        self.storage.set(key + "/expires", expiry + time.time(), expire=expiry, noreply=False)
        return 1

    def get_expiry(self, key):
        """
        :param str key: the key to get the expiry for
        """
        return int(float(self.storage.get(key + "/expires") or time.time()))

