import pytest
import redis

from flask import Flask

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


@pytest.fixture
def redis_connection():
    r = redis.from_url("redis://localhost:36379")
    r.flushall()
    return r


@pytest.fixture
def extension_factory():
    def _build_app_and_extension(config={}, **limiter_args):
        app = Flask(__name__)
        for k, v in config.items():
            app.config.setdefault(k, v)
        limiter_args.setdefault('key_func', get_remote_address)
        limiter = Limiter(app, **limiter_args)
        return app, limiter
    return _build_app_and_extension
