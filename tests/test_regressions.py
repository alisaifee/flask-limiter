"""

"""
import time
import logging
import unittest

from flask import Flask
import mock

from flask.ext.limiter.extension import C, Limiter


class RegressionTests(unittest.TestCase):

    def build_app(self, config={}, **limiter_args):
        app = Flask(__name__)
        for k,v in config.items():
            app.config.setdefault(k,v)
        limiter = Limiter(app, **limiter_args)
        mock_handler = mock.Mock()
        mock_handler.level = logging.INFO
        limiter.logger.addHandler(mock_handler)
        return app, limiter

    def test_redis_request_slower_than_fixed_window(self):
        app, limiter = self.build_app({
            C.GLOBAL_LIMITS : "5 per second",
            C.STORAGE_URL: "redis://localhost:6379",
            C.STRATEGY: "fixed-window"
        })

        @app.route("/t1")
        def t1():
            time.sleep(1.1)
            return "t1"

        with app.test_client() as cli:
            resp = cli.get("/t1")
            self.assertEqual(
                resp.headers["X-RateLimit-Remaining"],
                5
            )

    def test_redis_request_slower_than_moving_window(self):
        app, limiter = self.build_app({
            C.GLOBAL_LIMITS : "5 per second",
            C.STORAGE_URL: "redis://localhost:6379",
            C.STRATEGY: "moving-window"
        })

        @app.route("/t1")
        def t1():
            time.sleep(1.1)
            return "t1"

        with app.test_client() as cli:
            resp = cli.get("/t1")
            self.assertEqual(
                resp.headers["X-RateLimit-Remaining"],
                5
            )
