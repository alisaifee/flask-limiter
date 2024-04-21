import asyncio
import logging
from functools import wraps
from unittest import mock

import hiro
from flask import Blueprint, Flask, current_app, g, make_response, request
from werkzeug.exceptions import BadRequest

from flask_limiter import ExemptionScope, Limiter
from flask_limiter.util import get_remote_address


def get_ip_from_header():
    return request.headers.get("Test-IP") or "127.0.0.1"


def test_multiple_decorators(extension_factory):
    app, limiter = extension_factory(key_func=get_ip_from_header)

    @app.route("/t1")
    @limiter.limit(
        "100 per minute", key_func=lambda: "test"
    )  # effectively becomes a limit for all users
    @limiter.limit("50/minute")  # per ip as per default key_func
    def t1():
        return "test"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            for i in range(0, 100):
                assert (200 if i < 50 else 429) == cli.get(
                    "/t1", headers={"Test-IP": "127.0.0.2"}
                ).status_code

            for i in range(50):
                assert 200 == cli.get("/t1").status_code
            assert 429 == cli.get("/t1").status_code
            assert 429 == cli.get("/t1", headers={"Test-IP": "127.0.0.3"}).status_code


def test_exempt_routes(extension_factory):
    app, limiter = extension_factory(
        default_limits=["1/minute"], application_limits=["2/minute"]
    )

    @app.route("/t1")
    def t1():
        return "test"

    @app.route("/t2")
    @limiter.exempt
    def t2():
        return "test"

    @app.route("/t3")
    @limiter.exempt(flags=ExemptionScope.APPLICATION)
    def t3():
        return "test"

    @app.route("/t4")
    def t4():
        return "test"

    with app.test_client() as cli:
        assert cli.get("/t1").status_code == 200
        assert cli.get("/t1").status_code == 429
        # exempt from default + application
        assert cli.get("/t2").status_code == 200
        assert cli.get("/t2").status_code == 200
        # exempt from application
        assert cli.get("/t3").status_code == 200
        assert cli.get("/t3").status_code == 429
        # 2/minute for application is now taken up
        assert cli.get("/t4").status_code == 429


def test_decorated_limit_with_scope(extension_factory):
    app, limiter = extension_factory()

    @app.route("/t/<path:path>")
    @limiter.limit("1/second", scope=lambda _: request.view_args["path"])
    def t(path):
        return "test"

    with hiro.Timeline():
        with app.test_client() as cli:
            assert cli.get("/t/1").status_code == 200
            assert cli.get("/t/1").status_code == 429
            assert cli.get("/t/2").status_code == 200
            assert cli.get("/t/2").status_code == 429


def test_decorated_limit_with_conditional_deduction(extension_factory):
    app, limiter = extension_factory()

    @app.route("/t/<path:path>")
    @limiter.limit("1/second", deduct_when=lambda resp: resp.status_code == 200)
    @limiter.limit("1/minute", deduct_when=lambda resp: resp.status_code == 400)
    def t(path):
        if path == "1":
            return "test"
        raise BadRequest()

    with hiro.Timeline() as timeline:
        with app.test_client() as cli:
            assert cli.get("/t/1").status_code == 200
            assert cli.get("/t/1").status_code == 429
            timeline.forward(1)
            assert cli.get("/t/2").status_code == 400
            timeline.forward(1)
            assert cli.get("/t/1").status_code == 429
            assert cli.get("/t/2").status_code == 429
            timeline.forward(60)
            assert cli.get("/t/1").status_code == 200


def test_shared_limit_with_conditional_deduction(extension_factory):
    app, limiter = extension_factory()

    bp = Blueprint("main", __name__)

    limit = limiter.shared_limit(
        "2/minute",
        "not_found",
        deduct_when=lambda response: response.status_code == 400,
    )

    @app.route("/test/<path:path>")
    @limit
    def app_test(path):
        if path != "1":
            raise BadRequest()

        return path

    @bp.route("/test/<path:path>")
    def bp_test(path):
        if path != "1":
            raise BadRequest()

        return path

    limit(bp)

    app.register_blueprint(bp, url_prefix="/bp")

    with hiro.Timeline() as timeline:
        with app.test_client() as cli:
            assert cli.get("/bp/test/1").status_code == 200
            assert cli.get("/bp/test/1").status_code == 200
            assert cli.get("/test/1").status_code == 200
            assert cli.get("/bp/test/2").status_code == 400
            assert cli.get("/test/2").status_code == 400
            assert cli.get("/bp/test/2").status_code == 429
            assert cli.get("/bp/test/1").status_code == 429
            assert cli.get("/test/1").status_code == 429
            assert cli.get("/test/2").status_code == 429
            timeline.forward(60)
            assert cli.get("/bp/test/1").status_code == 200
            assert cli.get("/test/1").status_code == 200


def test_header_ordering_with_conditional_deductions(extension_factory):
    app, limiter = extension_factory(default_limits=["3/second"], headers_enabled=True)

    @app.route("/test_combined/<path:path>")
    @limiter.limit(
        "1/hour",
        override_defaults=False,
        deduct_when=lambda response: response.status_code != 200,
    )
    @limiter.limit(
        "4/minute",
        override_defaults=False,
        deduct_when=lambda response: response.status_code == 200,
    )
    def app_test_combined(path):
        if path != "1":
            raise BadRequest()

        return path

    @app.route("/test/<path:path>")
    @limiter.limit("2/hour", deduct_when=lambda response: response.status_code != 200)
    def app_test(path):
        if path != "1":
            raise BadRequest()

        return path

    with hiro.Timeline() as timeline:
        with app.test_client() as cli:
            assert cli.get("/test_combined/1").status_code == 200
            resp = cli.get("/test_combined/1")
            assert resp.status_code == 200
            assert resp.headers.get("X-RateLimit-Limit") == "3"
            assert resp.headers.get("X-RateLimit-Remaining") == "1"
            assert cli.get("/test_combined/2").status_code == 400

            resp = cli.get("/test/1")
            assert resp.headers.get("X-RateLimit-Limit") == "2"
            assert resp.headers.get("X-RateLimit-Remaining") == "2"
            resp = cli.get("/test/2")
            assert resp.headers.get("X-RateLimit-Limit") == "2"
            assert resp.headers.get("X-RateLimit-Remaining") == "1"

            timeline.forward(1)

            resp = cli.get("/test_combined/1")
            assert resp.status_code == 429
            assert resp.headers.get("X-RateLimit-Limit") == "1"
            assert resp.headers.get("X-RateLimit-Remaining") == "0"
            assert cli.get("/test_combined/2").status_code == 429
            timeline.forward(60)
            assert cli.get("/test_combined/1").status_code == 429
            assert cli.get("/test_combined/2").status_code == 429
            timeline.forward(3600)
            assert cli.get("/test_combined/1").status_code == 200


def test_decorated_limits_with_combined_defaults(extension_factory):
    app, limiter = extension_factory(default_limits=["2/minute"])

    @app.route("/")
    @limiter.limit("1/second", override_defaults=False)
    def root():
        return "root"

    with hiro.Timeline() as timeline:
        with app.test_client() as cli:
            assert 200 == cli.get("/").status_code
            assert 429 == cli.get("/").status_code
            timeline.forward(60)
            assert 200 == cli.get("/").status_code
            timeline.forward(1)
            assert 200 == cli.get("/").status_code
            timeline.forward(1)
            assert 429 == cli.get("/").status_code


def test_decorated_limit_with_combined_defaults_per_method(extension_factory):
    app, limiter = extension_factory(
        default_limits=["2/minute"], default_limits_per_method=True
    )

    @app.route("/", methods=["GET", "PUT"])
    @limiter.limit("1/second", override_defaults=False, methods=["GET"])
    def root():
        return "root"

    with hiro.Timeline() as timeline:
        with app.test_client() as cli:
            assert 200 == cli.get("/").status_code
            assert 429 == cli.get("/").status_code
            assert 200 == cli.put("/").status_code
            assert 200 == cli.put("/").status_code
            assert 429 == cli.put("/").status_code
            timeline.forward(60)
            assert 200 == cli.get("/").status_code
            assert 200 == cli.put("/").status_code
            timeline.forward(1)
            assert 200 == cli.get("/").status_code
            assert 200 == cli.put("/").status_code
            timeline.forward(1)
            assert 429 == cli.get("/").status_code
            assert 429 == cli.put("/").status_code


def test_decorated_dynamic_limits(extension_factory):
    app, limiter = extension_factory({"X": "2 per second"}, default_limits=["1/second"])

    def request_context_limit():
        limits = {"127.0.0.1": "10 per minute", "127.0.0.2": "1 per minute"}
        remote_addr = request.headers.get("Test-IP").split(",")[0] or "127.0.0.1"
        limit = limits.setdefault(remote_addr, "1 per minute")

        return limit

    @app.route("/t1")
    @limiter.limit("20/day")
    @limiter.limit(lambda: current_app.config.get("X"))
    @limiter.limit(request_context_limit)
    def t1():
        return "42"

    @app.route("/t2")
    @limiter.limit(lambda: current_app.config.get("X"))
    def t2():
        return "42"

    R1 = {"Test-IP": "127.0.0.1, 127.0.0.0"}
    R2 = {"Test-IP": "127.0.0.2"}

    with app.test_client() as cli:
        with hiro.Timeline().freeze() as timeline:
            for i in range(0, 10):
                assert cli.get("/t1", headers=R1).status_code == 200
                timeline.forward(1)
            assert cli.get("/t1", headers=R1).status_code == 429
            assert cli.get("/t1", headers=R2).status_code == 200
            assert cli.get("/t1", headers=R2).status_code == 429
            timeline.forward(60)
            assert cli.get("/t1", headers=R2).status_code == 200
            assert cli.get("/t2").status_code == 200
            assert cli.get("/t2").status_code == 200
            assert cli.get("/t2").status_code == 429
            timeline.forward(1)
            assert cli.get("/t2").status_code == 200


def test_invalid_decorated_dynamic_limits(caplog):
    caplog.set_level(logging.INFO)
    app = Flask(__name__)
    app.config.setdefault("X", "2 per sec")
    limiter = Limiter(get_ip_from_header, app=app, default_limits=["1/second"])

    @app.route("/t1")
    @limiter.limit(lambda: current_app.config.get("X"))
    def t1():
        return "42"

    with app.test_client() as cli:
        with hiro.Timeline().freeze():
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 429
    # 2 for invalid limit, 1 for warning.
    assert len(caplog.records) == 3
    assert "failed to load ratelimit" in caplog.records[0].msg
    assert "failed to load ratelimit" in caplog.records[1].msg
    assert "exceeded at endpoint" in caplog.records[2].msg
    assert caplog.records[2].levelname == "INFO"


def test_decorated_limit_empty_exempt(caplog):
    app = Flask(__name__)
    limiter = Limiter(get_remote_address, app=app)

    @app.route("/t1")
    @limiter.limit(lambda: "")
    def t1():
        return "42"

    with app.test_client() as cli:
        with hiro.Timeline().freeze():
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 200

    assert not caplog.records


def test_invalid_decorated_static_limits(caplog):
    caplog.set_level(logging.INFO)
    app = Flask(__name__)
    limiter = Limiter(get_ip_from_header, app=app, default_limits=["1/second"])

    @app.route("/t1")
    @limiter.limit("2/sec")
    def t1():
        return "42"

    with app.test_client() as cli:
        with hiro.Timeline().freeze():
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 429
    assert "failed to load" in caplog.records[0].msg
    assert "exceeded at endpoint" in caplog.records[-1].msg


def test_named_shared_limit(extension_factory):
    app, limiter = extension_factory()
    shared_limit_a = limiter.shared_limit("1/minute", scope="a")
    shared_limit_b = limiter.shared_limit("1/minute", scope="b")

    @app.route("/t1")
    @shared_limit_a
    def route1():
        return "route1"

    @app.route("/t2")
    @shared_limit_a
    def route2():
        return "route2"

    @app.route("/t3")
    @shared_limit_b
    def route3():
        return "route3"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/t1").status_code
            assert 200 == cli.get("/t3").status_code
            assert 429 == cli.get("/t2").status_code


def test_dynamic_shared_limit(extension_factory):
    app, limiter = extension_factory()
    fn_a = mock.Mock()
    fn_b = mock.Mock()
    fn_a.return_value = "foo"
    fn_b.return_value = "bar"

    dy_limit_a = limiter.shared_limit("1/minute", scope=fn_a)
    dy_limit_b = limiter.shared_limit("1/minute", scope=fn_b)

    @app.route("/t1")
    @dy_limit_a
    def t1():
        return "route1"

    @app.route("/t2")
    @dy_limit_a
    def t2():
        return "route2"

    @app.route("/t3")
    @dy_limit_b
    def t3():
        return "route3"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/t1").status_code
            assert 200 == cli.get("/t3").status_code
            assert 429 == cli.get("/t2").status_code
            assert 429 == cli.get("/t3").status_code
            assert 2 == fn_a.call_count
            assert 2 == fn_b.call_count
            fn_b.assert_called_with("t3")
            fn_a.assert_has_calls([mock.call("t1"), mock.call("t2")])


def test_conditional_limits():
    """Test that the conditional activation of the limits work."""
    app = Flask(__name__)
    limiter = Limiter(get_ip_from_header, app=app)

    @app.route("/limited")
    @limiter.limit("1 per day")
    def limited_route():
        return "passed"

    @app.route("/unlimited")
    @limiter.limit("1 per day", exempt_when=lambda: True)
    def never_limited_route():
        return "should always pass"

    is_exempt = False

    @app.route("/conditional")
    @limiter.limit("1 per day", exempt_when=lambda: is_exempt)
    def conditionally_limited_route():
        return "conditional"

    with app.test_client() as cli:
        assert cli.get("/limited").status_code == 200
        assert cli.get("/limited").status_code == 429

        assert cli.get("/unlimited").status_code == 200
        assert cli.get("/unlimited").status_code == 200

        assert cli.get("/conditional").status_code == 200
        assert cli.get("/conditional").status_code == 429
        is_exempt = True
        assert cli.get("/conditional").status_code == 200
        is_exempt = False
        assert cli.get("/conditional").status_code == 429


def test_conditional_shared_limits():
    """Test that conditional shared limits work."""
    app = Flask(__name__)
    limiter = Limiter(get_ip_from_header, app=app)

    @app.route("/limited")
    @limiter.shared_limit("1 per day", "test_scope")
    def limited_route():
        return "passed"

    @app.route("/unlimited")
    @limiter.shared_limit("1 per day", "test_scope", exempt_when=lambda: True)
    def never_limited_route():
        return "should always pass"

    is_exempt = False

    @app.route("/conditional")
    @limiter.shared_limit("1 per day", "test_scope", exempt_when=lambda: is_exempt)
    def conditionally_limited_route():
        return "conditional"

    with app.test_client() as cli:
        assert cli.get("/unlimited").status_code == 200
        assert cli.get("/unlimited").status_code == 200

        assert cli.get("/limited").status_code == 200
        assert cli.get("/limited").status_code == 429

        assert cli.get("/conditional").status_code == 429
        is_exempt = True
        assert cli.get("/conditional").status_code == 200
        is_exempt = False
        assert cli.get("/conditional").status_code == 429


def test_whitelisting():
    app = Flask(__name__)
    limiter = Limiter(
        get_ip_from_header,
        app=app,
        default_limits=["1/minute"],
        headers_enabled=True,
    )

    @app.route("/")
    def t():
        return "test"

    @limiter.request_filter
    def w():
        if request.headers.get("internal", None) == "true":
            return True

        return False

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            assert cli.get("/").status_code == 200
            assert cli.get("/").status_code == 429
            timeline.forward(60)
            assert cli.get("/").status_code == 200

            for i in range(0, 10):
                assert cli.get("/", headers={"internal": "true"}).status_code == 200


def test_separate_method_limits(extension_factory):
    app, limiter = extension_factory()

    @app.route("/", methods=["GET", "POST"])
    @limiter.limit("1/second", per_method=True)
    def root():
        return "root"

    with hiro.Timeline():
        with app.test_client() as cli:
            assert 200 == cli.get("/").status_code
            assert 429 == cli.get("/").status_code
            assert 200 == cli.post("/").status_code
            assert 429 == cli.post("/").status_code


def test_explicit_method_limits(extension_factory):
    app, limiter = extension_factory(default_limits=["2/second"])

    @app.route("/", methods=["GET", "POST"])
    @limiter.limit("1/second", methods=["GET"])
    def root():
        return "root"

    with hiro.Timeline():
        with app.test_client() as cli:
            assert 200 == cli.get("/").status_code
            assert 429 == cli.get("/").status_code
            assert 200 == cli.post("/").status_code
            assert 200 == cli.post("/").status_code
            assert 429 == cli.post("/").status_code


def test_decorated_limit_immediate(extension_factory):
    app, limiter = extension_factory(default_limits=["1/minute"])

    def append_info(fn):
        @wraps(fn)
        def __inner(*args, **kwargs):
            g.rate_limit = "2/minute"

            return fn(*args, **kwargs)

        return __inner

    @app.route("/", methods=["GET", "POST"])
    @append_info
    @limiter.limit(lambda: g.rate_limit, per_method=True)
    def root():
        return "root"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/").status_code
            assert 200 == cli.get("/").status_code
            assert 429 == cli.get("/").status_code


def test_decorated_shared_limit_immediate(extension_factory):
    app, limiter = extension_factory(default_limits=["1/minute"])
    shared = limiter.shared_limit(lambda: g.rate_limit, "shared")

    def append_info(fn):
        @wraps(fn)
        def __inner(*args, **kwargs):
            g.rate_limit = "2/minute"

            return fn(*args, **kwargs)

        return __inner

    @app.route("/", methods=["GET", "POST"])
    @append_info
    @shared
    def root():
        return "root"

    @app.route("/other", methods=["GET", "POST"])
    def other():
        return "other"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/other").status_code
            assert 429 == cli.get("/other").status_code
            assert 200 == cli.get("/").status_code
            assert 200 == cli.get("/").status_code
            assert 429 == cli.get("/").status_code


def test_async_route(extension_factory):
    app, limiter = extension_factory()

    @app.route("/t1")
    @limiter.limit("1/minute")
    async def t1():
        await asyncio.sleep(0.01)

        return "test"

    @app.route("/t2")
    @limiter.limit("1/minute")
    @limiter.exempt
    async def t2():
        await asyncio.sleep(0.01)

        return "test"

    with app.test_client() as cli:
        assert cli.get("/t1").status_code == 200
        assert cli.get("/t1").status_code == 429
        assert cli.get("/t2").status_code == 200
        assert cli.get("/t2").status_code == 200


def test_on_breach_callback_swallow_errors(extension_factory, caplog):
    app, limiter = extension_factory(swallow_errors=True)

    callbacks = []

    def on_breach(request_limit):
        callbacks.append(request_limit)

    def failed_on_breach(request_limit):
        1 / 0

    @app.route("/")
    @limiter.limit("1/second", on_breach=on_breach)
    def root():
        return "root"

    @app.route("/other")
    @limiter.limit("1/second")
    def other():
        return "other"

    @app.route("/fail")
    @limiter.limit("1/second", on_breach=failed_on_breach)
    def fail():
        return "fail"

    with app.test_client() as cli:
        assert cli.get("/").status_code == 200
        assert cli.get("/").status_code == 429
        assert cli.get("/other").status_code == 200
        assert cli.get("/other").status_code == 429
        assert cli.get("/fail").status_code == 200
        assert cli.get("/fail").status_code == 429

    assert len(callbacks) == 1

    log = caplog.records[-1]
    assert log.message == "on_breach callback failed with error division by zero"
    assert log.levelname == "ERROR"


def test_on_breach_callback_custom_response(extension_factory):
    def on_breach_no_response(request_limit):
        pass

    def on_breach_with_response(request_limit):
        return make_response(
            f"custom response {request_limit.limit} @ {request.path}", 429
        )

    def default_on_breach_with_response(request_limit):
        return make_response(
            f"default custom response {request_limit.limit} @ {request.path}", 429
        )

    def on_breach_invalid(): ...

    def on_breach_fail(request_limit):
        1 / 0

    app, limiter = extension_factory(on_breach=default_on_breach_with_response)

    @app.route("/")
    @limiter.limit("1/second", on_breach=on_breach_no_response)
    def root():
        return "root"

    @app.route("/t1")
    @limiter.limit("1/second")
    def t1():
        return "t1"

    @app.route("/t2")
    @limiter.limit("1/second", on_breach=on_breach_with_response)
    def t2():
        return "t2"

    @app.route("/t3")
    @limiter.limit("1/second", on_breach=on_breach_invalid)
    def t3():
        return "t3"

    @app.route("/t4")
    @limiter.limit("1/second", on_breach=on_breach_fail)
    def t4():
        return "t4"

    with app.test_client() as cli:
        assert cli.get("/").status_code == 200
        resp = cli.get("/")
        assert resp.status_code == 429
        assert resp.text == "default custom response 1 per 1 second @ /"
        assert cli.get("/t1").status_code == 200
        resp = cli.get("/t1")
        assert resp.status_code == 429
        assert resp.text == "default custom response 1 per 1 second @ /t1"
        assert cli.get("/t2").status_code == 200
        resp = cli.get("/t2")
        assert resp.status_code == 429
        assert resp.text == "custom response 1 per 1 second @ /t2"
        resp = cli.get("/t3")
        assert resp.status_code == 200
        resp = cli.get("/t3")
        assert resp.status_code == 500
        resp = cli.get("/t4")
        assert resp.status_code == 200
        resp = cli.get("/t4")
        assert resp.status_code == 500


def test_limit_multiple_cost(extension_factory):
    app, limiter = extension_factory()

    @app.route("/root")
    @limiter.limit("4/second", cost=2)
    def root():
        return "root"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/root").status_code
            assert 200 == cli.get("/root").status_code
            assert 429 == cli.get("/root").status_code


def test_limit_multiple_cost_callable(extension_factory):
    app, limiter = extension_factory()

    @app.route("/root")
    @limiter.limit("4/second", cost=lambda: 2)
    def root():
        return "root"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/root").status_code
            assert 200 == cli.get("/root").status_code
            assert 429 == cli.get("/root").status_code


def test_shared_limit_multiple_cost(extension_factory):
    app, limiter = extension_factory()
    shared_limit = limiter.shared_limit("4/minute", scope="a", cost=2)

    @app.route("/t1")
    @shared_limit
    def route1():
        return "route1"

    @app.route("/t2")
    @shared_limit
    def route2():
        return "route2"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/t1").status_code
            assert 200 == cli.get("/t2").status_code
            assert 429 == cli.get("/t2").status_code


def test_shared_limit_multiple_cost_callable(extension_factory):
    app, limiter = extension_factory()
    shared_limit = limiter.shared_limit("4/minute", scope="a", cost=lambda: 2)

    @app.route("/t1")
    @shared_limit
    def route1():
        return "route1"

    @app.route("/t2")
    @shared_limit
    def route2():
        return "route2"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/t1").status_code
            assert 200 == cli.get("/t2").status_code
            assert 429 == cli.get("/t2").status_code


def test_non_route_decoration_static_limits_override_defaults(extension_factory):
    app, limiter = extension_factory(default_limits=["1/second"])

    @limiter.limit("2/second")
    def limited():
        return "limited"

    @app.route("/t1")
    def route1():
        return "t1"

    @app.route("/t2")
    @limiter.limit("2/second")
    def route2():
        return "t2"

    @app.route("/t3")
    def route3():
        return limited()

    @app.route("/t4")
    def route4():
        @limiter.limit("2/day", override_defaults=False)
        def __inner():
            return "inner"

        return __inner()

    @app.route("/t5/<int:param>")
    def route5(param: int):
        @limiter.limit("2/day", override_defaults=False)
        def __inner1():
            return "inner1"

        @limiter.limit("3/day")
        def __inner2():
            return "inner2"

        return __inner1() if param < 10 else __inner2()

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            assert 200 == cli.get("/t1").status_code
            assert 429 == cli.get("/t1").status_code
            for i in range(2):
                assert 200 == cli.get("/t2").status_code
            assert 429 == cli.get("/t2").status_code
            for i in range(2):
                assert 200 == cli.get("/t3").status_code, i
            assert 429 == cli.get("/t3").status_code
            assert 200 == cli.get("/t4").status_code
            assert 429 == cli.get("/t4").status_code
            timeline.forward(1)
            assert 200 == cli.get("/t4").status_code
            timeline.forward(1)
            assert 429 == cli.get("/t4").status_code
            assert 200 == cli.get("/t5/1").status_code
            assert 429 == cli.get("/t5/1").status_code
            timeline.forward(1)
            assert 200 == cli.get("/t5/1").status_code
            timeline.forward(1)
            assert 429 == cli.get("/t5/1").status_code
            timeline.forward(60 * 60 * 24)
            assert 200 == cli.get("/t5/11").status_code
            assert 200 == cli.get("/t5/11").status_code
            assert 200 == cli.get("/t5/11").status_code
            assert 429 == cli.get("/t5/11").status_code


def test_non_route_decoration_static_limits(extension_factory):
    app, limiter = extension_factory()

    @limiter.limit("1/second")
    def limited():
        return "limited"

    @app.route("/t1")
    def route1():
        return limited()

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/t1").status_code
            assert 429 == cli.get("/t1").status_code


def test_non_route_decoration_dynamic_limits(extension_factory):
    app, limiter = extension_factory()

    def dynamic_limit_provider():
        return "1/second"

    @limiter.limit(dynamic_limit_provider)
    def limited():
        return "limited"

    @app.route("/t1")
    def route1():
        return limited()

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/t1").status_code
            assert 429 == cli.get("/t1").status_code


def test_non_route_decoration_multiple_sequential_limits_per_request(extension_factory):
    app, limiter = extension_factory()

    @limiter.limit("10/second")
    def l1():
        return "l1"

    @limiter.limit("1/second")
    def l2():
        return "l2"

    @app.route("/t1")
    def route1():
        return l1() + l2()

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/t1").status_code
            assert 429 == cli.get("/t1").status_code


def test_inner_function_decoration(extension_factory):
    app, limiter = extension_factory()

    @app.route("/t1")
    def route1():
        @limiter.limit("5/second")
        def l1():
            return "l1"

        return l1()

    @app.route("/t2")
    def route2():
        @limiter.limit("1/second")
        def l1():
            return "l1"

        return l1()

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/t1").status_code
            assert 200 == cli.get("/t2").status_code
            for _ in range(4):
                assert 200 == cli.get("/t1").status_code
            assert 429 == cli.get("/t1").status_code
            assert 429 == cli.get("/t2").status_code
