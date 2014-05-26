"""

"""
import threading
import time
import unittest

import hiro
import redis
import pymemcache.client

from flask.ext.limiter.limits import PER_SECOND, PER_MINUTE
from flask.ext.limiter.storage import MemoryStorage, RedisStorage, \
    MemcachedStorage
from flask.ext.limiter.strategies import MovingWindowRateLimiter, \
    FixedWindowElasticExpiryRateLimiter, FixedWindowRateLimiter


class WindowTests(unittest.TestCase):
    def setUp(self):
        redis.Redis().flushall()
        pymemcache.client.Client(('localhost', 11211)).flush_all()

    def test_fixed_window(self):
        storage = MemoryStorage()
        limiter = FixedWindowRateLimiter(storage)
        with hiro.Timeline().freeze() as timeline:
            start = int(time.time())
            limit = PER_SECOND(10, 2)
            self.assertTrue(all([limiter.hit(limit) for _ in range(0,10)]))
            timeline.forward(1)
            self.assertFalse(limiter.hit(limit))
            self.assertEqual(limiter.get_remaining(limit), 0)
            self.assertEqual(limiter.get_refresh(limit), start + 2)
            timeline.forward(1)
            self.assertEqual(limiter.get_remaining(limit), 10)
            self.assertTrue(limiter.hit(limit))

    def test_fixed_window_with_elastic_expiry_in_memory(self):
        storage = MemoryStorage()
        limiter = FixedWindowElasticExpiryRateLimiter(storage)
        with hiro.Timeline().freeze() as timeline:
            start = int(time.time())
            limit = PER_SECOND(10, 2)
            self.assertTrue(all([limiter.hit(limit) for _ in range(0,10)]))
            timeline.forward(1)
            self.assertFalse(limiter.hit(limit))
            self.assertEqual(limiter.get_remaining(limit), 0)
            # three extensions to the expiry
            self.assertEqual(limiter.get_refresh(limit), start + 3)
            timeline.forward(1)
            self.assertFalse(limiter.hit(limit))
            timeline.forward(3)
            start = int(time.time())
            self.assertTrue(limiter.hit(limit))
            self.assertEqual(limiter.get_remaining(limit), 9)
            self.assertEqual(limiter.get_refresh(limit), start + 2)

    def test_fixed_window_with_elastic_expiry_memcache(self):
        storage = MemcachedStorage('localhost', 11211)
        limiter = FixedWindowElasticExpiryRateLimiter(storage)
        limit = PER_SECOND(10, 2)
        self.assertTrue(all([limiter.hit(limit) for _ in range(0,10)]))
        self.assertEqual(limiter.get_remaining(limit), 0)
        time.sleep(1)
        self.assertFalse(limiter.hit(limit))
        time.sleep(1)
        self.assertFalse(limiter.hit(limit))

    def test_fixed_window_with_elastic_expiry_memcache_concurrency(self):
        storage = MemcachedStorage('localhost', 11211)
        limiter = FixedWindowElasticExpiryRateLimiter(storage)
        start = int(time.time())
        limit = PER_SECOND(100, 2)
        def _c():
            for i in range(0,50):
                limiter.hit(limit)
        t1, t2 = threading.Thread(target=_c), threading.Thread(target=_c)
        t1.start(), t2.start()
        [t1.join(), t2.join()]
        self.assertEqual(limiter.get_remaining(limit), 0)
        self.assertTrue(start + 2 <= limiter.get_refresh(limit) <= start + 3)
        self.assertEqual(storage.get(limit.key_for()), 100)

    def test_fixed_window_with_elastic_expiry_redis(self):
        storage = RedisStorage('redis://localhost:6379')
        limiter = FixedWindowElasticExpiryRateLimiter(storage)
        limit = PER_SECOND(10, 2)
        start = int(time.time())
        self.assertTrue(all([limiter.hit(limit) for _ in range(0,10)]))
        self.assertEqual(limiter.get_remaining(limit), 0)
        time.sleep(1)
        self.assertFalse(limiter.hit(limit))
        time.sleep(1)
        self.assertEqual(limiter.get_refresh(limit), start + 3)
        self.assertFalse(limiter.hit(limit))

    def test_moving_window_in_memory(self):
        storage = MemoryStorage()
        limiter = MovingWindowRateLimiter(storage)
        with hiro.Timeline().freeze() as timeline:
            limit = PER_MINUTE(10)
            for i in range(0,5):
                self.assertTrue(limiter.hit(limit))
                self.assertTrue(limiter.hit(limit))
                self.assertEqual(
                    limiter.get_remaining(limit),
                    10 - ((i + 1) * 2)
                )
                timeline.forward(10)
            self.assertEqual(limiter.get_remaining(limit), 0)
            self.assertFalse(limiter.hit(limit))
            timeline.forward(20)
            self.assertEqual(limiter.get_remaining(limit), 2)
            self.assertEqual(limiter.get_refresh(limit), int(time.time()) + 1)
            self.assertTrue(limiter.hit(limit))
            self.assertTrue(limiter.hit(limit))
            self.assertFalse(limiter.hit(limit))

    def test_moving_window_redis(self):
        storage = RedisStorage("redis://localhost:6379")
        limiter = MovingWindowRateLimiter(storage)
        limit = PER_SECOND(10, 2)
        start = time.time()
        for i in range(0,10):
            self.assertTrue(limiter.hit(limit))
            self.assertEqual(limiter.get_remaining(limit), 10 - (i + 1))
            time.sleep(0.095 * 2)
        self.assertFalse(limiter.hit(limit))
        time.sleep(0.4)
        self.assertTrue(limiter.hit(limit))
        self.assertTrue(limiter.hit(limit))
        self.assertFalse(limiter.hit(limit))
        self.assertTrue(storage.storage.llen(limit.key_for()) == 10)

    def test_moving_window_memcached(self):
        storage = MemcachedStorage('localhost', 11211)
        self.assertRaises(NotImplementedError, MovingWindowRateLimiter, storage)
