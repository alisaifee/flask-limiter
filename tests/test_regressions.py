""" """

import time

import hiro
from flask import Blueprint

from flask_limiter.constants import ConfigVars


def test_redis_request_slower_than_fixed_window(redis_connection, extension_factory):
    app, limiter = extension_factory(
        {
            ConfigVars.DEFAULT_LIMITS: "5 per second",
            ConfigVars.STORAGE_URI: "redis://localhost:46379",
            ConfigVars.STRATEGY: "fixed-window",
            ConfigVars.HEADERS_ENABLED: True,
        }
    )

    @app.route("/t1")
    def t1():
        time.sleep(1.1)
        return "t1"

    with app.test_client() as cli:
        resp = cli.get("/t1")
        assert resp.headers["X-RateLimit-Remaining"] == "5"


def test_redis_request_slower_than_moving_window(redis_connection, extension_factory):
    app, limiter = extension_factory(
        {
            ConfigVars.DEFAULT_LIMITS: "5 per second",
            ConfigVars.STORAGE_URI: "redis://localhost:46379",
            ConfigVars.STRATEGY: "moving-window",
            ConfigVars.HEADERS_ENABLED: True,
        }
    )

    @app.route("/t1")
    def t1():
        time.sleep(1.1)
        return "t1"

    with app.test_client() as cli:
        resp = cli.get("/t1")
        assert resp.headers["X-RateLimit-Remaining"] == "5"


def test_dynamic_limits(extension_factory):
    app, limiter = extension_factory(
        {ConfigVars.STRATEGY: "moving-window", ConfigVars.HEADERS_ENABLED: True}
    )

    def func(*a):
        return "1/second; 2/minute"

    @app.route("/t1")
    @limiter.limit(func)
    def t1():
        return "t1"

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 429
            timeline.forward(2)
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 429


def test_invalid_ratelimit_key(extension_factory):
    app, limiter = extension_factory({ConfigVars.HEADERS_ENABLED: True})

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
        assert cli.get("/t1").status_code == 200
        limiter.limit("1/second", key_func=lambda: "key")(t1)
        cli.get("/t1")
        assert cli.get("/t1").status_code == 429


def test_custom_key_prefix_with_headers(redis_connection, extension_factory):
    app1, limiter1 = extension_factory(
        key_prefix="moo", storage_uri="redis://localhost:46379", headers_enabled=True
    )
    app2, limiter2 = extension_factory(
        key_prefix="cow", storage_uri="redis://localhost:46379", headers_enabled=True
    )

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
        assert 200 == resp.status_code
        resp = cli.get("/test")
        assert resp.headers.get("Retry-After") == str(60)
        assert 429 == resp.status_code
    with app2.test_client() as cli:
        resp = cli.get("/test")
        assert 200 == resp.status_code
        resp = cli.get("/test")
        assert resp.headers.get("Retry-After") == str(60)
        assert 429 == resp.status_code


def test_default_limits_with_per_route_limit(extension_factory):
    app, limiter = extension_factory(application_limits=["3/minute"])

    @app.route("/explicit")
    @limiter.limit("1/minute")
    def explicit():
        return "explicit"

    @app.route("/default")
    def default():
        return "default"

    with app.test_client() as cli:
        with hiro.Timeline().freeze() as timeline:
            assert 200 == cli.get("/explicit").status_code
            assert 429 == cli.get("/explicit").status_code
            assert 200 == cli.get("/default").status_code
            assert 429 == cli.get("/default").status_code
            timeline.forward(60)
            assert 200 == cli.get("/explicit").status_code
            assert 200 == cli.get("/default").status_code


def test_application_limits_from_config(extension_factory):
    app, limiter = extension_factory(
        config={
            ConfigVars.APPLICATION_LIMITS: "4/second",
            ConfigVars.DEFAULT_LIMITS: "1/second",
            ConfigVars.DEFAULT_LIMITS_PER_METHOD: True,
        }
    )

    @app.route("/root")
    def root():
        return "null"

    @app.route("/test", methods=["GET", "PUT"])
    @limiter.limit("3/second", methods=["GET"])
    def test():
        return "test"

    with app.test_client() as cli:
        with hiro.Timeline() as timeline:
            assert cli.get("/root").status_code == 200
            assert cli.get("/root").status_code == 429
            assert cli.get("/test").status_code == 200
            assert cli.get("/test").status_code == 200
            assert cli.get("/test").status_code == 429
            timeline.forward(1)
            assert cli.get("/test").status_code == 200
            assert cli.get("/test").status_code == 200
            assert cli.get("/test").status_code == 200
            assert cli.get("/test").status_code == 429
            timeline.forward(1)
            assert cli.put("/test").status_code == 200
            assert cli.put("/test").status_code == 429
            assert cli.get("/test").status_code == 200
            assert cli.get("/root").status_code == 200
            assert cli.get("/test").status_code == 429


def test_endpoint_with_dot_but_not_blueprint(extension_factory):
    """
    https://github.com/alisaifee/flask-limiter/issues/336
    """
    app, limiter = extension_factory(default_limits=["2/day"])

    def route():
        return "42"

    app.add_url_rule("/teapot/iam", "_teapot.iam", route)
    bp = Blueprint("teapot", __name__, url_prefix="/teapot")

    @bp.route("/")
    def bp_route():
        return "43"

    app.register_blueprint(bp)
    limiter.limit("1/day")(bp)

    with app.test_client() as cli:
        assert cli.get("/teapot/iam").status_code == 200
        assert cli.get("/teapot/iam").status_code == 200
        assert cli.get("/teapot/iam").status_code == 429
        assert cli.get("/teapot/").status_code == 200
        assert cli.get("/teapot/").status_code == 429
