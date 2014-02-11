import unittest
import hiro
import mock
import time
from flask.ext.ratelimits.errors import ConfigurationError
from flask.ext.ratelimits.limits import Limiter, PER_MINUTE, PER_SECOND
from flask.ext.ratelimits.storage import MemoryStorage, RedisStorage
from flask_ratelimits import parser, limits

class StorageTests(unittest.TestCase):
    def test_in_memory(self):
        with hiro.Timeline().freeze() as timeline:
            storage = MemoryStorage()
            limiter = Limiter(storage)
            per_min = PER_MINUTE(10)
            for i in range(0,10):
                self.assertTrue(limiter.hit(per_min))
            self.assertFalse(limiter.hit(per_min))
            timeline.forward(61)
            self.assertTrue(limiter.hit(per_min))


    def test_redis_prerequisite_fail(self):
        with mock.patch("flask_ratelimits.storage.get_dependency") as dep_getter:
            dep_getter.return_value = None
            self.assertRaises(ConfigurationError, RedisStorage, "blah")

    def test_redis(self):
        storage = RedisStorage("redis://localhost:6379")
        limiter = Limiter(storage)
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

