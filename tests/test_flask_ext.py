"""

"""
import logging
import time

import hiro
import mock
from flask import Flask, request
from werkzeug.exceptions import BadRequest

from flask_limiter.extension import C, Limiter, HEADERS
from flask_limiter.util import get_remote_address


def test_reset(extension_factory):
    app, limiter = extension_factory({C.GLOBAL_LIMITS: "1 per day"})

    @app.route("/")
    def null():
        return "Hello Reset"

    with app.test_client() as cli:
        cli.get("/")
        assert "1 per 1 day" in cli.get("/").data.decode()
        limiter.reset()
        assert "Hello Reset" == cli.get("/").data.decode()
        assert "1 per 1 day" in cli.get("/").data.decode()


def test_reset_unsupported(extension_factory):
    app, limiter = extension_factory({
        C.GLOBAL_LIMITS: "1 per day",
        C.STORAGE_URL: 'memcached://localhost:31211'
    })

    @app.route("/")
    def null():
        return "Hello Reset"

    with app.test_client() as cli:
        cli.get("/")
        assert "1 per 1 day" in cli.get("/").data.decode()
        # no op with memcached but no error raised
        limiter.reset()
        assert "1 per 1 day" in cli.get("/").data.decode()


def test_combined_rate_limits(extension_factory):
    app, limiter = extension_factory({
        C.GLOBAL_LIMITS: "1 per hour; 10 per day"
    })

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
    app, limiter = extension_factory({
        C.DEFAULT_LIMITS: "1 per hour",
        C.DEFAULT_LIMITS_PER_METHOD: True
    })

    @app.route("/t1", methods=['GET', 'POST'])
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
        return request.headers.get('backdoor') == 'true'

    app, limiter = extension_factory({
        C.DEFAULT_LIMITS: "1 per hour",
        C.DEFAULT_LIMITS_EXEMPT_WHEN: is_backdoor
    })

    @app.route("/t1")
    def t1():
        return "test"

    with hiro.Timeline() as timeline:
        with app.test_client() as cli:
            assert cli.get(
                "/t1", headers={'backdoor': 'true'}
            ).status_code == 200
            assert cli.get(
                "/t1", headers={'backdoor': 'true'}
            ).status_code == 200
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 429
            timeline.forward(3600)
            assert cli.get("/t1").status_code == 200


def test_default_limit_with_conditional_deduction(
        extension_factory
):
    def failed_request(response):
        return response.status_code != 200

    app, limiter = extension_factory({
        C.DEFAULT_LIMITS: "1 per hour",
        C.DEFAULT_LIMITS_DEDUCT_WHEN: failed_request
    })

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
    @limiter.limit("100 per minute", lambda: "test")
    def t1():
        return "test"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            for i in range(0, 100):
                assert 200 == \
                    cli.get(
                        "/t1", headers={
                            "X_FORWARDED_FOR": "127.0.0.2"
                        }
                    ).status_code
            assert 429 == cli.get("/t1").status_code


def test_logging(caplog):
    app = Flask(__name__)
    limiter = Limiter(app, key_func=get_remote_address)

    @app.route("/t1")
    @limiter.limit("1/minute")
    def t1():
        return "test"

    with app.test_client() as cli:
        assert 200 == cli.get("/t1").status_code
        assert 429 == cli.get("/t1").status_code
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == 'WARNING'


def test_reuse_logging():
    app = Flask(__name__)
    app_handler = mock.Mock()
    app_handler.level = logging.INFO
    app.logger.addHandler(app_handler)
    limiter = Limiter(app, key_func=get_remote_address)
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
        config={C.ENABLED: False}, default_limits=["1/minute"]
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

    limiter = Limiter(
        default_limits=["1/second"], key_func=get_remote_address
    )
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
        app,
        default_limits=["10/minute"],
        headers_enabled=True,
        key_func=get_remote_address
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
            assert resp.headers.get('X-RateLimit-Limit') == '10'
            assert resp.headers.get('X-RateLimit-Remaining') == '9'
            assert resp.headers.get('X-RateLimit-Reset') == \
                str(int(time.time() + 61))
            assert resp.headers.get('Retry-After') == str(60)
            resp = cli.get("/t2")
            assert resp.headers.get('X-RateLimit-Limit') == '2'
            assert resp.headers.get('X-RateLimit-Remaining') == '1'
            assert resp.headers.get('X-RateLimit-Reset') == \
                str(int(time.time() + 2))

            assert resp.headers.get('Retry-After') == str(1)


def test_headers_breach():
    app = Flask(__name__)
    limiter = Limiter(
        app,
        default_limits=["10/minute"],
        headers_enabled=True,
        key_func=get_remote_address
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

            assert resp.headers.get('X-RateLimit-Limit') == '10'
            assert resp.headers.get('X-RateLimit-Remaining') == '0'
            assert resp.headers.get('X-RateLimit-Reset') == \
                str(int(time.time() + 50))
            assert resp.headers.get('Retry-After') == str(int(50))


def test_retry_after():
    app = Flask(__name__)
    _ = Limiter(
        app,
        default_limits=["1/minute"],
        headers_enabled=True,
        key_func=get_remote_address
    )

    @app.route("/t1")
    def t():
        return "test"

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            resp = cli.get("/t1")
            retry_after = int(resp.headers.get('Retry-After'))
            assert retry_after > 0
            timeline.forward(retry_after)
            resp = cli.get("/t1")
            assert resp.status_code == 200


def test_retry_after_exists_seconds():
    app = Flask(__name__)
    _ = Limiter(
        app,
        default_limits=["1/minute"],
        headers_enabled=True,
        key_func=get_remote_address
    )

    @app.route("/t1")
    def t():
        return "", 200, {'Retry-After': '1000000'}

    with app.test_client() as cli:
        resp = cli.get("/t1")

        retry_after = int(resp.headers.get('Retry-After'))
        assert retry_after > 1000


def test_retry_after_exists_rfc1123():
    app = Flask(__name__)
    _ = Limiter(
        app,
        default_limits=["1/minute"],
        headers_enabled=True,
        key_func=get_remote_address
    )

    @app.route("/t1")
    def t():
        return "", 200, {'Retry-After': 'Sun, 06 Nov 2032 01:01:01 GMT'}

    with app.test_client() as cli:
        resp = cli.get("/t1")

        retry_after = int(resp.headers.get('Retry-After'))
        assert retry_after > 1000


def test_custom_headers_from_setter():
    app = Flask(__name__)
    limiter = Limiter(
        app,
        default_limits=["10/minute"],
        headers_enabled=True,
        key_func=get_remote_address,
        retry_after='http-date'
    )
    limiter._header_mapping[HEADERS.RESET] = 'X-Reset'
    limiter._header_mapping[HEADERS.LIMIT] = 'X-Limit'
    limiter._header_mapping[HEADERS.REMAINING] = 'X-Remaining'

    @app.route("/t1")
    @limiter.limit("2/second; 10 per minute; 20/hour")
    def t():
        return "test"

    with hiro.Timeline().freeze(0) as timeline:
        with app.test_client() as cli:
            for i in range(11):
                resp = cli.get("/t1")
                timeline.forward(1)

            assert resp.headers.get('X-Limit') == '10'
            assert resp.headers.get('X-Remaining') == '0'
            assert resp.headers.get(
                'X-Reset'
            ) == str(int(time.time() + 50))
            assert resp.headers.get(
                'Retry-After'
            ) == 'Thu, 01 Jan 1970 00:01:01 GMT'


def test_custom_headers_from_config():
    app = Flask(__name__)
    app.config.setdefault(C.HEADER_LIMIT, "X-Limit")
    app.config.setdefault(C.HEADER_REMAINING, "X-Remaining")
    app.config.setdefault(C.HEADER_RESET, "X-Reset")
    limiter = Limiter(
        app,
        default_limits=["10/minute"],
        headers_enabled=True,
        key_func=get_remote_address
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

            assert resp.headers.get('X-Limit') == '10'
            assert resp.headers.get('X-Remaining') == '0'
            assert resp.headers.get(
                'X-Reset'
            ) == str(int(time.time() + 50))


def test_custom_headers_from_setter_and_config():
    app = Flask(__name__)
    app.config.setdefault(C.HEADER_LIMIT, "Limit")
    app.config.setdefault(C.HEADER_REMAINING, "Remaining")
    app.config.setdefault(C.HEADER_RESET, "Reset")
    limiter = Limiter(
        default_limits=["10/minute"],
        headers_enabled=True,
        key_func=get_remote_address
    )
    limiter._header_mapping[HEADERS.REMAINING] = 'Available'
    limiter.init_app(app)

    @app.route("/t1")
    def t():
        return "test"

    with app.test_client() as cli:
        for i in range(11):
            resp = cli.get("/t1")

        assert resp.headers.get('Limit') == '10'
        assert resp.headers.get('Available') == '0'
        assert resp.headers.get('Reset') is not None


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


def test_callable_default_limit(extension_factory):
    app, limiter = extension_factory(default_limits=[lambda: "1/minute"])

    @app.route("/t1")
    def t1():
        return "t1"

    @app.route("/t2")
    def t2():
        return "t2"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t2").status_code == 200
            assert cli.get("/t1").status_code == 429
            assert cli.get("/t2").status_code == 429


def test_callable_application_limit(extension_factory):

    app, limiter = extension_factory(
        application_limits=[lambda: "1/minute"]
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
            assert cli.get("/t2").status_code == 429


def test_no_auto_check(extension_factory):
    app, limiter = extension_factory(auto_check=False)

    @limiter.limit("1/second", per_method=True)
    @app.route("/", methods=["GET", "POST"])
    def root():
        return "root"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/").status_code
            assert 200 == cli.get("/").status_code

    # attach before_request to perform check
    @app.before_request
    def _():
        limiter.check()

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/").status_code
            assert 429 == cli.get("/").status_code


def test_custom_key_prefix(redis_connection, extension_factory):
    app1, limiter1 = extension_factory(
        key_prefix="moo", storage_uri="redis://localhost:36379"
    )
    app2, limiter2 = extension_factory(
        {C.KEY_PREFIX: "cow"},
        storage_uri="redis://localhost:36379"
    )
    app3, limiter3 = extension_factory(
        storage_uri="redis://localhost:36379"
    )

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
