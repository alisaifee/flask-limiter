import unittest
import time

import hiro
import mock
from flask.ext.limiter.util import get_dependency

from flask_limiter.errors import ConfigurationError
from flask_limiter.limits import RateLimitManager, PER_MINUTE, PER_SECOND
from flask_limiter.storage import MemoryStorage, RedisStorage, MemcachedStorage


class StorageTests(unittest.TestCase):
    def test_in_memory(self):
        with hiro.Timeline().freeze() as timeline:
            storage = MemoryStorage()
            limiter = RateLimitManager(storage)
            per_min = PER_MINUTE(10)
            for i in range(0,10):
                self.assertTrue(limiter.hit(per_min))
            self.assertFalse(limiter.hit(per_min))
            timeline.forward(61)
            self.assertTrue(limiter.hit(per_min))

    def test_redis(self):
        storage = RedisStorage("redis://localhost:6379")
        limiter = RateLimitManager(storage)
        per_min = PER_SECOND(10)
        start = time.time()
        count = 0
        while time.time() - start < 0.5 and count < 10:
            self.assertTrue(limiter.hit(per_min))
            count += 1
        self.assertFalse(limiter.hit(per_min))
        while time.time() - start < 1:
            time.sleep(0.1)
        self.assertTrue(limiter.hit(per_min))

    @unittest.skipIf(not get_dependency("memcache"), "run memcache tests only if installed")
    def test_memcached(self):
        storage = MemcachedStorage("localhost", 11211)
        limiter = RateLimitManager(storage)
        per_min = PER_SECOND(10)
        start = time.time()
        count = 0
        while time.time() - start < 0.5 and count < 10:
            self.assertTrue(limiter.hit(per_min))
            count += 1
        self.assertFalse(limiter.hit(per_min))
        while time.time() - start < 1:
            time.sleep(0.1)
        self.assertTrue(limiter.hit(per_min))
