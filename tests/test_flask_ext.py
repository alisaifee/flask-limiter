""" """

import logging
import time
from collections import Counter
from unittest import mock

import hiro
from flask import Flask, abort, make_response, request
from werkzeug.exceptions import BadRequest

from flask_limiter.constants import ConfigVars
from flask_limiter.extension import Limiter
from flask_limiter.util import get_remote_address


def test_reset(extension_factory):
    app, limiter = extension_factory({ConfigVars.DEFAULT_LIMITS: "1 per day"})

    @app.route("/")
    def null():
        return "Hello Reset"

    with app.test_client() as cli:
        cli.get("/")
        assert "1 per 1 day" in cli.get("/").data.decode()
        limiter.reset()
        assert "Hello Reset" == cli.get("/").data.decode()
        assert "1 per 1 day" in cli.get("/").data.decode()


def test_reset_unsupported(extension_factory, memcached_connection):
    app, limiter = extension_factory(
        {
            ConfigVars.DEFAULT_LIMITS: "1 per day",
            ConfigVars.STORAGE_URI: "memcached://localhost:31211",
        }
    )

    @app.route("/")
    def null():
        return "Hello Reset"

    with app.test_client() as cli:
        cli.get("/")
        assert "1 per 1 day" in cli.get("/").data.decode()
        # no op with memcached but no error raised
        limiter.reset()
        assert "1 per 1 day" in cli.get("/").data.decode()


def test_static_exempt(extension_factory):
    app, limiter = extension_factory(default_limits=["1/minute"])

    @app.route("/")
    def root():
        return "root"

    with app.test_client() as cli:
        assert cli.get("/").status_code == 200
        assert cli.get("/").status_code == 429
        assert cli.get("/static/image.png").status_code == 200
        assert cli.get("/static/image.png").status_code == 200


def test_combined_rate_limits(extension_factory):
    app, limiter = extension_factory(
        {ConfigVars.DEFAULT_LIMITS: "1 per hour; 10 per day"}
    )

    @app.route("/t1")
    @limiter.limit("100 per hour;10/minute")
    def t1():
        return "t1"

    @app.route("/t2")
    def t2():
        return "t2"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/t1").status_code
            assert 200 == cli.get("/t2").status_code
            assert 429 == cli.get("/t2").status_code


def test_defaults_per_method(extension_factory):
    app, limiter = extension_factory(
        {
            ConfigVars.DEFAULT_LIMITS: "1 per hour",
            ConfigVars.DEFAULT_LIMITS_PER_METHOD: True,
        }
    )

    @app.route("/t1", methods=["GET", "POST"])
    def t1():
        return "t1"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/t1").status_code
            assert 429 == cli.get("/t1").status_code
            assert 200 == cli.post("/t1").status_code
            assert 429 == cli.post("/t1").status_code


def test_default_limit_with_exemption(extension_factory):
    def is_backdoor():
        return request.headers.get("backdoor") == "true"

    app, limiter = extension_factory(
        {
            ConfigVars.DEFAULT_LIMITS: "1 per hour",
            ConfigVars.DEFAULT_LIMITS_EXEMPT_WHEN: is_backdoor,
        }
    )

    @app.route("/t1")
    def t1():
        return "test"

    with hiro.Timeline() as timeline:
        with app.test_client() as cli:
            assert cli.get("/t1", headers={"backdoor": "true"}).status_code == 200
            assert cli.get("/t1", headers={"backdoor": "true"}).status_code == 200
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 429
            timeline.forward(3600)
            assert cli.get("/t1").status_code == 200


def test_default_limit_with_variable_cost(extension_factory):
    def cost_fn():
        if request.headers.get("suspect"):
            return 2
        return 1

    app, limiter = extension_factory(
        {
            ConfigVars.APPLICATION_LIMITS: "10 per day",
            ConfigVars.DEFAULT_LIMITS: "2 per hour",
            ConfigVars.DEFAULT_LIMITS_COST: cost_fn,
            ConfigVars.APPLICATION_LIMITS_COST: cost_fn,
        }
    )

    @app.route("/t1")
    def t1():
        return "test"

    @app.route("/t2")
    def t2():
        return "test"

    with hiro.Timeline() as timeline:
        with app.test_client() as cli:
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 429
            timeline.forward(3600)
            assert cli.get("/t1", headers={"suspect": 1}).status_code == 200
            assert cli.get("/t1", headers={"suspect": 1}).status_code == 429
            assert cli.get("/t2", headers={"suspect": 1}).status_code == 200
            timeline.forward(3600)
            assert cli.get("/t2", headers={"suspect": 1}).status_code == 200
            timeline.forward(3600)
            assert cli.get("/t2", headers={"suspect": 1}).status_code == 200
            timeline.forward(3600)
            assert cli.get("/t2", headers={"suspect": 1}).status_code == 429


def test_default_limit_with_conditional_deduction(extension_factory):
    def failed_request(response):
        return response.status_code != 200

    app, limiter = extension_factory(
        {
            ConfigVars.DEFAULT_LIMITS: "1 per hour",
            ConfigVars.DEFAULT_LIMITS_DEDUCT_WHEN: failed_request,
        }
    )

    @app.route("/t1/<path:path>")
    def t1(path):
        if path != "1":
            raise BadRequest()

        return path

    with hiro.Timeline() as timeline:
        with app.test_client() as cli:
            assert cli.get("/t1/1").status_code == 200
            assert cli.get("/t1/1").status_code == 200
            assert cli.get("/t1/2").status_code == 400
            assert cli.get("/t1/1").status_code == 429
            assert cli.get("/t1/2").status_code == 429
            timeline.forward(3600)
            assert cli.get("/t1/1").status_code == 200
            assert cli.get("/t1/2").status_code == 400


def test_key_func(extension_factory):
    app, limiter = extension_factory()

    @app.route("/t1")
    @limiter.limit("100 per minute", key_func=lambda: "test")
    def t1():
        return "test"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            for i in range(0, 100):
                assert (
                    200
                    == cli.get(
                        "/t1", headers={"X_FORWARDED_FOR": "127.0.0.2"}
                    ).status_code
                )
            assert 429 == cli.get("/t1").status_code


def test_logging(caplog):
    caplog.set_level(logging.INFO)
    app = Flask(__name__)
    limiter = Limiter(get_remote_address, app=app)

    @app.route("/t1")
    @limiter.limit("1/minute")
    def t1():
        return "test"

    with app.test_client() as cli:
        assert 200 == cli.get("/t1").status_code
        assert 429 == cli.get("/t1").status_code
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "INFO"


def test_reuse_logging(caplog):
    caplog.set_level(logging.INFO)
    app = Flask(__name__)
    app_handler = mock.Mock()
    app_handler.level = logging.INFO
    app.logger.addHandler(app_handler)
    limiter = Limiter(get_remote_address, app=app)

    for handler in app.logger.handlers:
        limiter.logger.addHandler(handler)

    @app.route("/t1")
    @limiter.limit("1/minute")
    def t1():
        return "42"

    with app.test_client() as cli:
        cli.get("/t1")
        cli.get("/t1")

    assert app_handler.handle.call_count == 1


def test_disabled_flag(extension_factory):
    app, limiter = extension_factory(
        config={ConfigVars.ENABLED: False}, default_limits=["1/minute"]
    )

    @app.route("/t1")
    def t1():
        return "test"

    @app.route("/t2")
    @limiter.limit("10 per minute")
    def t2():
        return "test"

    with app.test_client() as cli:
        assert cli.get("/t1").status_code == 200
        assert cli.get("/t1").status_code == 200

        for i in range(0, 10):
            assert cli.get("/t2").status_code == 200
        assert cli.get("/t2").status_code == 200


def test_multiple_apps():
    app1 = Flask(__name__)
    app2 = Flask(__name__)

    limiter = Limiter(get_remote_address, default_limits=["1/second"])
    limiter.init_app(app1)
    limiter.init_app(app2)

    @app1.route("/ping")
    def ping():
        return "PONG"

    @app1.route("/slowping")
    @limiter.limit("1/minute")
    def slow_ping():
        return "PONG"

    @app2.route("/ping")
    @limiter.limit("2/second")
    def ping_2():
        return "PONG"

    @app2.route("/slowping")
    @limiter.limit("2/minute")
    def slow_ping_2():
        return "PONG"

    with hiro.Timeline().freeze() as timeline:
        with app1.test_client() as cli:
            assert cli.get("/ping").status_code == 200
            assert cli.get("/ping").status_code == 429
            timeline.forward(1)
            assert cli.get("/ping").status_code == 200
            assert cli.get("/slowping").status_code == 200
            timeline.forward(59)
            assert cli.get("/slowping").status_code == 429
            timeline.forward(1)
            assert cli.get("/slowping").status_code == 200
        with app2.test_client() as cli:
            assert cli.get("/ping").status_code == 200
            assert cli.get("/ping").status_code == 200
            assert cli.get("/ping").status_code == 429
            timeline.forward(1)
            assert cli.get("/ping").status_code == 200
            assert cli.get("/slowping").status_code == 200
            timeline.forward(59)
            assert cli.get("/slowping").status_code == 200
            assert cli.get("/slowping").status_code == 429
            timeline.forward(1)
            assert cli.get("/slowping").status_code == 200


def test_headers_no_breach():
    app = Flask(__name__)
    limiter = Limiter(
        get_remote_address,
        app=app,
        application_limits=["60/minute"],
        default_limits=["10/minute"],
        headers_enabled=True,
    )

    @app.route("/t1")
    def t1():
        return "test"

    @app.route("/t2")
    @limiter.limit("2/second; 5 per minute; 10/hour")
    def t2():
        return "test"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            resp = cli.get("/t1")
            assert resp.headers.get("X-RateLimit-Limit") == "10"
            assert resp.headers.get("X-RateLimit-Remaining") == "9"
            assert resp.headers.get("X-RateLimit-Reset") == str(int(time.time() + 61))
            assert resp.headers.get("Retry-After") == str(60)
            resp = cli.get("/t2")
            assert resp.headers.get("X-RateLimit-Limit") == "2"
            assert resp.headers.get("X-RateLimit-Remaining") == "1"
            assert resp.headers.get("X-RateLimit-Reset") == str(int(time.time() + 2))

            assert resp.headers.get("Retry-After") == str(1)


def test_headers_application_limits():
    app = Flask(__name__)
    limiter = Limiter(
        get_remote_address,
        app=app,
        application_limits=["60/minute"],
        headers_enabled=True,
    )

    @app.route("/t1")
    def t1():
        return "test"

    @app.route("/t2")
    @limiter.limit("2/second; 5 per minute; 10/hour")
    def t2():
        return "test"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            resp = cli.get("/t1")
            assert resp.headers.get("X-RateLimit-Limit") == "60"
            assert resp.headers.get("X-RateLimit-Remaining") == "59"
            assert resp.headers.get("X-RateLimit-Reset") == str(int(time.time() + 61))
            assert resp.headers.get("Retry-After") == str(60)
            resp = cli.get("/t2")
            assert resp.headers.get("X-RateLimit-Limit") == "2"
            assert resp.headers.get("X-RateLimit-Remaining") == "1"
            assert resp.headers.get("X-RateLimit-Reset") == str(int(time.time() + 2))

            assert resp.headers.get("Retry-After") == str(1)


def test_headers_breach():
    app = Flask(__name__)
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["10/minute"],
        headers_enabled=True,
    )

    @app.route("/t1")
    @limiter.limit("2/second; 10 per minute; 20/hour")
    def t():
        return "test"

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            for i in range(10):
                cli.get("/t1")
                timeline.forward(1)

            resp = cli.get("/t1")
            timeline.forward(1)

            assert resp.headers.get("X-RateLimit-Limit") == "10"
            assert resp.headers.get("X-RateLimit-Remaining") == "0"
            assert resp.headers.get("X-RateLimit-Reset") == str(int(time.time() + 50))
            assert resp.headers.get("Retry-After") == str(int(50))


def test_retry_after():
    app = Flask(__name__)
    _ = Limiter(
        get_remote_address,
        app=app,
        default_limits=["1/minute"],
        headers_enabled=True,
    )

    @app.route("/t1")
    def t():
        return "test"

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            resp = cli.get("/t1")
            retry_after = int(resp.headers.get("Retry-After"))
            assert retry_after > 0
            timeline.forward(retry_after)
            resp = cli.get("/t1")
            assert resp.status_code == 200


def test_retry_after_exists_seconds():
    app = Flask(__name__)
    _ = Limiter(
        get_remote_address,
        app=app,
        default_limits=["1/minute"],
        headers_enabled=True,
    )

    @app.route("/t1")
    def t():
        return "", 200, {"Retry-After": "1000000"}

    with app.test_client() as cli:
        resp = cli.get("/t1")

        retry_after = int(resp.headers.get("Retry-After"))
        assert retry_after > 1000


def test_retry_after_exists_rfc1123():
    app = Flask(__name__)
    _ = Limiter(
        get_remote_address,
        app=app,
        default_limits=["1/minute"],
        headers_enabled=True,
    )

    @app.route("/t1")
    def t():
        return "", 200, {"Retry-After": "Sun, 06 Nov 2032 01:01:01 GMT"}

    with app.test_client() as cli:
        resp = cli.get("/t1")

        retry_after = int(resp.headers.get("Retry-After"))
        assert retry_after > 1000


def test_custom_headers_from_config():
    app = Flask(__name__)
    app.config.setdefault(ConfigVars.HEADER_LIMIT, "X-Limit")
    app.config.setdefault(ConfigVars.HEADER_REMAINING, "X-Remaining")
    app.config.setdefault(ConfigVars.HEADER_RESET, "X-Reset")
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["10/minute"],
        headers_enabled=True,
    )

    @app.route("/t1")
    @limiter.limit("2/second; 10 per minute; 20/hour")
    def t():
        return "test"

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            for i in range(11):
                resp = cli.get("/t1")
                timeline.forward(1)

            assert resp.headers.get("X-Limit") == "10"
            assert resp.headers.get("X-Remaining") == "0"
            assert resp.headers.get("X-Reset") == str(int(time.time() + 50))


def test_application_shared_limit(extension_factory):
    app, limiter = extension_factory(application_limits=["2/minute"])

    @app.route("/t1")
    def t1():
        return "route1"

    @app.route("/t2")
    def t2():
        return "route2"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/t1").status_code
            assert 200 == cli.get("/t2").status_code
            assert 429 == cli.get("/t1").status_code


def test_application_limit_conditional(extension_factory):
    def app_limit_exempt():
        return "X" in request.headers

    def app_limit_deduct(response):
        return response.status_code == 400

    app, limiter = extension_factory(
        application_limits=["2/minute"],
        application_limits_exempt_when=app_limit_exempt,
        application_limits_deduct_when=app_limit_deduct,
    )

    @app.route("/t1", methods=["GET", "POST"])
    def t1():
        return "route1"

    @app.route("/t2")
    def t2():
        abort(400)

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/t1").status_code
            assert 400 == cli.get("/t2").status_code
            assert 200 == cli.get("/t1").status_code
            assert 400 == cli.get("/t2").status_code
            assert 429 == cli.get("/t1").status_code
            assert 429 == cli.get("/t2").status_code


def test_application_limit_per_method(extension_factory):
    app, limiter = extension_factory(
        application_limits=["2/minute"],
        application_limits_per_method=True,
    )

    @app.route("/t1", methods=["GET", "POST"])
    def t1():
        return "route1"

    @app.route("/t2", methods=["GET", "POST"])
    def t2():
        return "route2"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/t1").status_code
            assert 200 == cli.get("/t2").status_code
            assert 429 == cli.get("/t1").status_code
            assert 429 == cli.get("/t2").status_code
            assert 200 == cli.post("/t1").status_code
            assert 200 == cli.post("/t2").status_code
            assert 429 == cli.post("/t1").status_code
            assert 429 == cli.post("/t2").status_code


def test_callable_default_limit(extension_factory):
    app, limiter = extension_factory(
        default_limits=[
            lambda: request.headers.get("suspect", 0) and "1/minute" or "2/minute"
        ]
    )

    @app.route("/t1")
    def t1():
        return "t1"

    @app.route("/t2")
    def t2():
        return "t2"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 429
            assert cli.get("/t2", headers={"suspect": "1"}).status_code == 200
            assert cli.get("/t2", headers={"suspect": "1"}).status_code == 429


def test_callable_application_limit(extension_factory):
    app, limiter = extension_factory(
        application_limits=[
            lambda: request.headers.get("suspect", 0) and "1/minute" or "2/minute"
        ]
    )

    @app.route("/t1")
    def t1():
        return "t1"

    @app.route("/t2")
    def t2():
        return "t2"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t2").status_code == 429
            assert cli.get("/t1", headers={"suspect": 1}).status_code == 200
            assert cli.get("/t2", headers={"suspect": 1}).status_code == 429


def test_no_auto_check(extension_factory):
    app, limiter = extension_factory(auto_check=False)

    @app.route("/", methods=["GET", "POST"])
    @limiter.limit("1/second", per_method=True)
    def root():
        return "root"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/").status_code
            assert 200 == cli.get("/").status_code


def test_no_auto_check_custom_before_request(extension_factory):
    app, limiter = extension_factory(auto_check=False)

    @app.route("/", methods=["GET", "POST"])
    @limiter.limit("1/second", per_method=True)
    def root():
        return "root"

    @app.before_request
    def _():
        limiter.check()

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/").status_code
            assert 429 == cli.get("/").status_code


def test_fail_on_first_breach(extension_factory):
    app, limiter = extension_factory(fail_on_first_breach=True)
    current_limits = []

    @app.route("/", methods=["GET", "POST"])
    @limiter.limit("1/second", per_method=True)
    @limiter.limit("2/minute", per_method=True)
    def root():
        return "root"

    @app.after_request
    def collect_current_limits(r):
        current_limits.extend(limiter.current_limits)
        return r

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            assert 200 == cli.get("/").status_code
            assert 429 == cli.get("/").status_code
            timeline.forward(1)
            assert 200 == cli.get("/").status_code
            timeline.forward(1)
            assert 429 == cli.get("/").status_code
    assert not current_limits[0].breached
    assert not current_limits[1].breached
    assert current_limits[2].breached


def test_no_fail_on_first_breach(extension_factory):
    app, limiter = extension_factory(fail_on_first_breach=False)

    @app.route("/", methods=["GET", "POST"])
    @limiter.limit("1/second", per_method=True)
    @limiter.limit("2/minute", per_method=True)
    def root():
        return "root"

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            assert 200 == cli.get("/").status_code
            assert 429 == cli.get("/").status_code
            timeline.forward(1)
            assert 429 == cli.get("/").status_code


def test_default_on_breach_callback(extension_factory):
    collected = Counter()

    def on_breach(limit):
        collected[limit.key] += 1

    app, limiter = extension_factory(on_breach=on_breach, default_limits=["2/second"])

    @app.route("/")
    def root():
        return "groot"

    @app.route("/sub")
    @limiter.limit("1/second")
    def sub_path():
        return "subgroot"

    with app.test_client() as cli:
        cli.get("/")
        cli.get("/")
        cli.get("/")
        cli.get("/sub")
        cli.get("/sub")
        cli.get("/sub")

    assert collected["LIMITER/127.0.0.1/root/2/1/second"] == 1
    assert collected["LIMITER/127.0.0.1/sub_path/1/1/second"] == 2


def test_custom_key_prefix(redis_connection, extension_factory):
    app1, limiter1 = extension_factory(
        key_prefix="moo", storage_uri="redis://localhost:46379"
    )
    app2, limiter2 = extension_factory(
        {ConfigVars.KEY_PREFIX: "cow"}, storage_uri="redis://localhost:46379"
    )
    app3, limiter3 = extension_factory(storage_uri="redis://localhost:46379")

    @app1.route("/test")
    @limiter1.limit("1/day")
    def app1_test():
        return "app1 test"

    @app2.route("/test")
    @limiter2.limit("1/day")
    def app2_test():
        return "app1 test"

    @app3.route("/test")
    @limiter3.limit("1/day")
    def app3_test():
        return "app1 test"

    with app1.test_client() as cli:
        resp = cli.get("/test")
        assert 200 == resp.status_code
        resp = cli.get("/test")
        assert 429 == resp.status_code
    with app2.test_client() as cli:
        resp = cli.get("/test")
        assert 200 == resp.status_code
        resp = cli.get("/test")
        assert 429 == resp.status_code
    with app3.test_client() as cli:
        resp = cli.get("/test")
        assert 200 == resp.status_code
        resp = cli.get("/test")
        assert 429 == resp.status_code


def test_multiple_instances_no_key_prefix():
    app = Flask(__name__)
    limiter1 = Limiter(get_remote_address, app=app)

    limiter2 = Limiter(get_remote_address, app=app)

    @app.route("/test1")
    @limiter2.limit("1/second")
    def app_test1():
        return "app test1"

    @app.route("/test2")
    @limiter1.limit("10/minute")
    @limiter2.limit("1/second")
    def app_test2():
        return "app test2"

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            assert cli.get("/test1").status_code == 200
            assert cli.get("/test1").status_code == 429
            assert cli.get("/test2").status_code == 200
            assert cli.get("/test2").status_code == 429

            for i in range(8):
                timeline.forward(1)
                assert cli.get("/test1").status_code == 200
                assert cli.get("/test2").status_code == 200
            timeline.forward(1)
            assert cli.get("/test1").status_code == 200
            assert cli.get("/test2").status_code == 429
            timeline.forward(59)
            assert cli.get("/test2").status_code == 200


def test_independent_instances_by_key_prefix():
    app = Flask(__name__)
    limiter1 = Limiter(get_remote_address, key_prefix="lmt1", app=app)

    limiter2 = Limiter(get_remote_address, key_prefix="lmt2", app=app)

    @app.route("/test1")
    @limiter2.limit("1/second")
    def app_test1():
        return "app test1"

    @app.route("/test2")
    @limiter1.limit("10/minute")
    @limiter2.limit("1/second")
    def app_test2():
        return "app test2"

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            assert cli.get("/test1").status_code == 200
            assert cli.get("/test2").status_code == 200

            resp = cli.get("/test1")
            assert resp.status_code == 429
            assert "1 per 1 second" in resp.data.decode()

            resp = cli.get("/test2")
            assert resp.status_code == 429
            assert "1 per 1 second" in resp.data.decode()

            for i in range(8):
                assert cli.get("/test1").status_code == 429
                assert cli.get("/test2").status_code == 429
            assert cli.get("/test2").status_code == 429
            timeline.forward(1)
            assert cli.get("/test1").status_code == 200
            assert cli.get("/test2").status_code == 429
            timeline.forward(59)
            assert cli.get("/test1").status_code == 200
            assert cli.get("/test2").status_code == 200


def test_multiple_limiters_default_limits():
    app = Flask(__name__)
    Limiter(get_remote_address, key_prefix="lmt1", app=app, default_limits=["1/second"])
    Limiter(
        get_remote_address,
        key_prefix="lmt2",
        default_limits=["10/minute"],
        app=app,
    )

    @app.route("/test1")
    def app_test1():
        return "app test1"

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            assert cli.get("/test1").status_code == 200
            assert cli.get("/test1").status_code == 429
            for _ in range(9):
                timeline.forward(1)
                assert cli.get("/test1").status_code == 200
            timeline.forward(1)
            assert cli.get("/test1").status_code == 429
            timeline.forward(50)
            assert cli.get("/test1").status_code == 200


def test_meta_limits(extension_factory):
    def meta_breach_cb(limit):
        return make_response("Would you like some tea?", 429)

    app, limiter = extension_factory(
        default_limits=["2/second"],
        meta_limits=["2/minute; 3/hour", lambda: "4/day"],
        on_meta_breach=meta_breach_cb,
        headers_enabled=True,
    )

    @app.route("/")
    def root():
        return "root"

    @app.route("/exempt")
    @limiter.exempt
    def exempt():
        return "exempt"

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            for _ in range(2):
                assert cli.get("/").status_code == 200
                assert cli.get("/").status_code == 200
                assert cli.get("/").status_code == 429
                timeline.forward(1)

            # blocked because of max 2 breaches/minute
            assert cli.get("/").status_code == 429
            assert cli.get("/exempt").status_code == 200
            timeline.forward(59)
            assert cli.get("/").status_code == 200
            assert cli.get("/").status_code == 200
            assert cli.get("/").status_code == 429
            assert cli.get("/exempt").status_code == 200
            timeline.forward(59)
            # blocked because of max 3 breaches/hour
            response = cli.get("/")
            assert response.text == "Would you like some tea?"
            assert response.status_code == 429
            assert response.headers.get("X-RateLimit-Limit") == "3"
            assert response.headers.get("X-RateLimit-Remaining") == "0"
            assert cli.get("/exempt").status_code == 200

            # forward to 1 hour since start
            timeline.forward(60 * 58)
            assert cli.get("/").status_code == 200
            assert cli.get("/").status_code == 200
            assert cli.get("/").status_code == 429
            # forward another hour and it should now be blocked for the day
            timeline.forward(60 * 60)
            response = cli.get("/")
            assert response.status_code == 429
            assert response.headers.get("X-RateLimit-Limit") == "4"
            assert response.headers.get("X-RateLimit-Remaining") == "0"

            # forward 22 hours
            timeline.forward(60 * 60 * 22)
            assert cli.get("/").status_code == 200
