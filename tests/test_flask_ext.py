"""

"""
import unittest
from flask import Flask
import hiro
from flask.ext.ratelimits.extension import RateLimits


class FlaskExtTests(unittest.TestCase):
    def test_global_rate_limits(self):
        app = Flask(__name__)
        app.config.setdefault("RATELIMIT_GLOBAL", "1 per hour;10 per day")
        ratelimits = RateLimits(app)

        @app.route("/t1")
        @ratelimits.limit("100 per hour;10/minute")
        def t1():
            return "t1"

        @app.route("/t2")
        def t2():
            return "t2"

        with hiro.Timeline().freeze() as timeline:
            with app.test_client() as cli:
                self.assertEqual(404, cli.get("/").status_code)
                self.assertEqual(429, cli.get("/").status_code)
                timeline.forward(60 * 60 + 1)
                self.assertEqual(404, cli.get("/").status_code)

                for i in range(0, 10):
                    self.assertEqual(200, cli.get("/t1").status_code)
                self.assertEqual(429, cli.get("/t1").status_code)
                self.assertEqual(200, cli.get("/t2").status_code)
                self.assertEqual(429, cli.get("/t2").status_code)
                timeline.forward(60)
                self.assertEqual(200, cli.get("/t1").status_code)

    def test_key_func(self):
        app = Flask(__name__)
        ratelimits = RateLimits(app)
        @app.route("/t1")
        @ratelimits.limit("100 per minute", lambda:"test")
        def t1():
            return "test"

        with hiro.Timeline().freeze() as timeline:
            with app.test_client() as cli:
                for i in range(0,100):
                    self.assertEqual(200,
                                     cli.get("/t1", headers = {"HTTP_X_FORWARDED_FOR":"127.0.0.2"}).status_code
                    )
                self.assertEqual(429, cli.get("/t1").status_code)

