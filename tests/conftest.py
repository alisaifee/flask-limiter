import pytest
import redis


@pytest.fixture
def redis_connection():
    r = redis.from_url("redis://localhost:36379")
    r.flushall()
    return r
