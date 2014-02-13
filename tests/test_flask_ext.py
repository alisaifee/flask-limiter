"""

"""
import logging
import unittest
from flask import Flask
import hiro
import mock
from flask.ext.limiter.extension import Limiter


class FlaskExtTests(unittest.TestCase):
    def test_combined_rate_limits(self):
        app = Flask(__name__)
        app.config.setdefault("RATELIMIT_GLOBAL", "1 per hour;10 per day")
        limiter = Limiter(app)

        @app.route("/t1")
        @limiter.limit("100 per hour;10/minute")
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
                for i in range(0,100):
                    self.assertEqual(200, cli.get("/t1").status_code)
                    if not i % 10 == 0:
                        timeline.forward(60)
                self.assertEqual(429, cli.get("/t1").status_code)
                self.assertEqual(200, cli.get("/t2").status_code)
                self.assertEqual(429, cli.get("/t2").status_code)

    def test_key_func(self):
        app = Flask(__name__)
        limiter = Limiter(app)
        @app.route("/t1")
        @limiter.limit("100 per minute", lambda:"test")
        def t1():
            return "test"

        with hiro.Timeline().freeze() as timeline:
            with app.test_client() as cli:
                for i in range(0,100):
                    self.assertEqual(200,
                                     cli.get("/t1", headers = {"HTTP_X_FORWARDED_FOR":"127.0.0.2"}).status_code
                    )
                self.assertEqual(429, cli.get("/t1").status_code)

    def test_multiple_decorators(self):
        app = Flask(__name__)
        limiter = Limiter(app)
        @app.route("/t1")
        @limiter.limit("100 per minute", lambda:"test") # effectively becomes a limit for all users
        @limiter.limit("50/minute") # per ip as per default key_func
        def t1():
            return "test"

        with hiro.Timeline().freeze() as timeline:
            with app.test_client() as cli:
                for i in range(0,100):
                    self.assertEqual(200 if i < 50 else 429,
                                     cli.get("/t1", headers = {"HTTP_X_FORWARDED_FOR":"127.0.0.2"}).status_code
                    )
                self.assertEqual(429, cli.get("/t1").status_code)

    def test_logging(self):
        fake_logger = mock.Mock()
        app = Flask(__name__)
        mock_handler = mock.Mock()
        mock_handler.level = logging.INFO
        app.logger.setLevel(logging.INFO)
        app.logger.addHandler(mock_handler)
        limiter = Limiter(app)
        @app.route("/t1")
        @limiter.limit("1/minute")
        def t1():
            return "test"
        with app.test_client() as cli:
            self.assertEqual(200,cli.get("/t1").status_code)
            self.assertEqual(429,cli.get("/t1").status_code)
        self.assertEqual(mock_handler.handle.call_count, 1)
