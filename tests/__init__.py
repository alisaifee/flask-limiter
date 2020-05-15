import logging
import unittest
from functools import wraps
import platform

import redis
from flask import Flask
from mock import mock
from nose.plugins.skip import SkipTest

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


class FlaskLimiterTestCase(unittest.TestCase):
    def setUp(self):
        redis.Redis().flushall()

    def build_app(self, config={}, **limiter_args):
        app = Flask(__name__)
        for k, v in config.items():
            app.config.setdefault(k, v)
        limiter_args.setdefault('key_func', get_remote_address)
        limiter = Limiter(app, **limiter_args)
        mock_handler = mock.Mock()
        mock_handler.level = logging.INFO
        limiter.logger.addHandler(mock_handler)
        return app, limiter


def test_import():
    import flask_limiter  # noqa


def test_module_version():
    import flask_limiter
    assert flask_limiter.__version__ is not None


def skip_if_pypy(fn):
    @wraps(fn)
    def __inner(*a, **k):
        if platform.python_implementation().lower() == "pypy":
            raise SkipTest
        return fn(*a, **k)

    return __inner
