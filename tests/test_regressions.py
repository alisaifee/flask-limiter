"""

"""
import time
import logging
import unittest

from flask import Flask
import hiro
import mock
import redis

from flask.ext.limiter.extension import C, Limiter


class RegressionTests(unittest.TestCase):
    def setUp(self):
        redis.Redis().flushall()

    def build_app(self, config={}, **limiter_args):
        app = Flask(__name__)
        for k,v in config.items():
            app.config.setdefault(k,v)
        limiter = Limiter(app, **limiter_args)
        mock_handler = mock.Mock()
        mock_handler.level = logging.INFO
        limiter._logger.addHandler(mock_handler)
        return app, limiter

    def test_redis_request_slower_than_fixed_window(self):
        app, limiter = self.build_app({
            C.GLOBAL_LIMITS : "5 per second",
            C.STORAGE_URL: "redis://localhost:6379",
            C.STRATEGY: "fixed-window",
            C.HEADERS_ENABLED: True
        })

        @app.route("/t1")
        def t1():
            time.sleep(1.1)
            return "t1"

        with app.test_client() as cli:
            resp = cli.get("/t1")
            self.assertEqual(
                resp.headers["X-RateLimit-Remaining"],
                '5'
            )

    def test_redis_request_slower_than_moving_window(self):
        app, limiter = self.build_app({
            C.GLOBAL_LIMITS : "5 per second",
            C.STORAGE_URL: "redis://localhost:6379",
            C.STRATEGY: "moving-window",
            C.HEADERS_ENABLED: True
        })

        @app.route("/t1")
        def t1():
            time.sleep(1.1)
            return "t1"

        with app.test_client() as cli:
            resp = cli.get("/t1")
            self.assertEqual(
                resp.headers["X-RateLimit-Remaining"],
                '5'
            )

    def test_dynamic_limits(self):
        app, limiter = self.build_app({
            C.STRATEGY: "moving-window",
            C.HEADERS_ENABLED : True
        })

        def func(*a):
            return "1/second; 2/minute"

        @app.route("/t1")
        @limiter.limit(func)
        def t1():
            return "t1"
        with hiro.Timeline().freeze() as timeline:
            with app.test_client() as cli:
                self.assertEqual(cli.get("/t1").status_code, 200)
                self.assertEqual(cli.get("/t1").status_code, 429)
                timeline.forward(2)
                self.assertEqual(cli.get("/t1").status_code, 200)
                self.assertEqual(cli.get("/t1").status_code, 429)

