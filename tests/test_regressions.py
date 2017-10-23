"""

"""
import time

import hiro

from flask_limiter.extension import C
from tests import FlaskLimiterTestCase


class RegressionTests(FlaskLimiterTestCase):
    def xest_redis_request_slower_than_fixed_window(self):
        app, limiter = self.build_app({
            C.GLOBAL_LIMITS: "5 per second",
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
            self.assertEqual(resp.headers["X-RateLimit-Remaining"], '5')

    def test_redis_request_slower_than_moving_window(self):
        app, limiter = self.build_app({
            C.GLOBAL_LIMITS: "5 per second",
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
            self.assertEqual(resp.headers["X-RateLimit-Remaining"], '5')

    def test_dynamic_limits(self):
        app, limiter = self.build_app({
            C.STRATEGY: "moving-window",
            C.HEADERS_ENABLED: True
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

    def test_invalid_ratelimit_key(self):
        app, limiter = self.build_app({C.HEADERS_ENABLED: True})

        def func(*a):
            return None

        @app.route("/t1")
        @limiter.limit("2/second", key_func=func)
        def t1():
            return "t1"

        with app.test_client() as cli:
            cli.get("/t1")
            cli.get("/t1")
            cli.get("/t1")
            self.assertEqual(cli.get("/t1").status_code, 200)
            limiter.limit("1/second", key_func=lambda: "key")(t1)
            cli.get("/t1")
            self.assertEqual(cli.get("/t1").status_code, 429)

    def test_custom_key_prefix_with_headers(self):
        app1, limiter1 = self.build_app(key_prefix="moo", storage_uri="redis://localhost:6379", headers_enabled=True)
        app2, limiter2 = self.build_app(key_prefix="cow", storage_uri="redis://localhost:6379", headers_enabled=True)

        @app1.route("/test")
        @limiter1.limit("1/minute")
        def t1():
            return "app1 test"

        @app2.route("/test")
        @limiter2.limit("1/minute")
        def t2():
            return "app2 test"

        with app1.test_client() as cli:
            resp = cli.get("/test")
            self.assertEqual(200, resp.status_code)
            resp = cli.get("/test")
            self.assertEqual(
                resp.headers.get('Retry-After'),
                str(60)
            )
            self.assertEqual(429, resp.status_code)
        with app2.test_client() as cli:
            resp = cli.get("/test")
            self.assertEqual(200, resp.status_code)
            resp = cli.get("/test")
            self.assertEqual(
                resp.headers.get('Retry-After'),
                str(60)
            )
            self.assertEqual(429, resp.status_code)
