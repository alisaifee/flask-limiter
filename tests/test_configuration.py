import pytest

from flask import Flask

from flask_limiter.extension import C, Limiter
from flask_limiter.util import get_remote_address

from limits.errors import ConfigurationError
from limits.storage import MemcachedStorage
from limits.strategies import MovingWindowRateLimiter


def test_invalid_strategy():
    app = Flask(__name__)
    app.config.setdefault(C.STRATEGY, "fubar")
    with pytest.raises(ConfigurationError):
        Limiter(app, key_func=get_remote_address)


def test_invalid_storage_string():
    app = Flask(__name__)
    app.config.setdefault(C.STORAGE_URL, "fubar://localhost:1234")
    with pytest.raises(ConfigurationError):
        Limiter(app, key_func=get_remote_address)


def test_constructor_arguments_over_config(redis_connection):
    app = Flask(__name__)
    app.config.setdefault(C.STRATEGY, "fixed-window-elastic-expiry")
    limiter = Limiter(
        strategy='moving-window', key_func=get_remote_address
    )
    limiter.init_app(app)
    app.config.setdefault(C.STORAGE_URL, "redis://localhost:36379")
    assert type(limiter._limiter) == MovingWindowRateLimiter
    limiter = Limiter(
        storage_uri='memcached://localhost:31211',
        key_func=get_remote_address
    )
    limiter.init_app(app)
    assert type(limiter._storage) == MemcachedStorage
